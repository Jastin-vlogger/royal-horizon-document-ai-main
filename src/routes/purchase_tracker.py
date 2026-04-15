"""Purchase tracker APIs: B/L number and structured bill extraction."""

from typing import Optional

from PIL import UnidentifiedImageError

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.config.logger import logger
from src.core.document_processor import (
    detect_file_type,
    load_bill_document_pages,
    load_packaging_list_pages,
    read_upload_to_bytes,
)
from src.core.packaging_list_extractor import extract_packaging_list_structured
from src.core.purchase_tracker_bill_no import (
    build_bill_no_api_response,
    extract_bill_structured,
)
from src.schemas.response import BillNoExtractionResponse, EnhancedBillNoExtractionResponse
from src.utils.container_matcher import filter_containers_by_packaging_list
from src.utils.metadata_aggregator import aggregate_metadata

router = APIRouter(prefix="/purchase-tracker", tags=["purchase-tracker"])

ALLOWED_TYPES = {"pdf", "image"}


@router.post(
    "/fetch-details",
    response_model=EnhancedBillNoExtractionResponse,
    summary="Extract structured Bill of Loading and Packaging List data from shipping documents",
)
async def extract_bill_no_from_document(
    file: UploadFile = File(
        ...,
        description="Bill of Lading document: PDF (pages 1–2 used) or image (PNG/JPEG).",
    ),
    packaging_list_file: Optional[UploadFile] = File(
        None,
        description="Packaging List document: PDF (max 2 pages) or image (PNG/JPEG). Optional.",
    ),
    packaging_brand: Optional[str] = Form(
        None,
        description="Target brand name to extract from packaging list. Required if packaging_list_file is provided.",
    ),
) -> EnhancedBillNoExtractionResponse:
    """
    Enhanced API that extracts Bill of Lading data and optionally Packaging List data.
    
    When packaging_list_file is provided:
    - Extracts data from both documents
    - Filters bill containers to only include those in packaging list
    - Returns aggregated metadata from both extractions
    
    When packaging_list_file is NOT provided:
    - Works like the original API
    - Returns only bill extraction data
    
    Returns a structured JSON with:
    - bill_extracted_data: Bill of Lading fields with filtered containers
    - packaging_list: Packaging list data (null if not provided)
    - metadata: Aggregated token usage and cost
    """
    logger.debug("Processing Purchase Tracker fetch-details API")
    
    # Validate inputs
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Bill document file must be provided.")
    
    # If packaging list is provided, brand must also be provided
    if packaging_list_file and not packaging_brand:
        raise HTTPException(
            status_code=400,
            detail="packaging_brand is required when packaging_list_file is provided.",
        )
    
    if not packaging_list_file and packaging_brand:
        logger.warning("packaging_brand provided but packaging_list_file is missing. Ignoring brand.")
    
    # Process Bill document
    logger.debug("Processing Bill of Lading document")
    bill_content, bill_filename = read_upload_to_bytes(file)
    bill_ftype = detect_file_type(bill_filename)
    if bill_ftype not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Bill file must be PDF or image (jpg, jpeg, png). Got: {bill_filename}",
        )
    
    try:
        bill_page_images = load_bill_document_pages(bill_content, bill_filename)
    except ValueError as e:
        logger.warning("Bill document pages unavailable: %s", e)
        raise HTTPException(
            status_code=400,
            detail=f"Could not read bill document pages: {e}",
        ) from e
    except UnidentifiedImageError as e:
        logger.warning("Bill document image unreadable: %s", e)
        raise HTTPException(
            status_code=400,
            detail="Could not decode bill image file. Use a valid JPEG or PNG.",
        ) from e
    except Exception as e:
        logger.warning("Bill document load failed: %s", e)
        raise HTTPException(
            status_code=400, detail=f"Could not process bill file: {e}"
        ) from e

    if not bill_page_images:
        raise HTTPException(
            status_code=400, detail="No readable pages found in the bill document."
        )

    try:
        bill_extraction, bill_metadata, bill_parse_error = await extract_bill_structured(
            bill_page_images
        )
        logger.debug(f"Bill Extracted Details: {bill_extraction}")
    except Exception as e:
        logger.exception("B/L structured extraction failed")
        raise HTTPException(status_code=500, detail=f"Bill extraction failed: {e}") from e

    if bill_parse_error:
        logger.warning(
            "Bill parse/validation failed (returning null fields): %s", bill_parse_error
        )
    
    # Build initial bill response
    bill_response = build_bill_no_api_response(bill_extraction, bill_metadata)
    
    # Validate bill container count vs declared count
    declared_count = bill_response.number_of_containers
    extracted_count = len(bill_response.containers)
    if declared_count is not None and declared_count != extracted_count:
        logger.warning(
            f"Bill container count mismatch: declared={declared_count}, "
            f"extracted={extracted_count}. Containers: "
            f"{[c.container_no for c in bill_response.containers]}"
        )
    else:
        logger.debug(
            f"Bill containers OK: {extracted_count} extracted, "
            f"numbers={[c.container_no for c in bill_response.containers]}"
        )
    
    # Process Packaging List if provided
    packaging_extraction = None
    packaging_metadata = None
    
    if packaging_list_file and packaging_brand:
        logger.debug(f"Processing Packaging List document for brand: {packaging_brand}")
        
        pkg_content, pkg_filename = read_upload_to_bytes(packaging_list_file)
        pkg_ftype = detect_file_type(pkg_filename)
        
        if pkg_ftype not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Packaging list file must be PDF or image. Got: {pkg_filename}",
            )
        
        try:
            pkg_page_images = load_packaging_list_pages(pkg_content, pkg_filename)
        except ValueError as e:
            logger.warning("Packaging list document validation failed: %s", e)
            raise HTTPException(
                status_code=400,
                detail=f"Packaging list error: {e}",
            ) from e
        except UnidentifiedImageError as e:
            logger.warning("Packaging list image unreadable: %s", e)
            raise HTTPException(
                status_code=400,
                detail="Could not decode packaging list image. Use a valid JPEG or PNG.",
            ) from e
        except Exception as e:
            logger.warning("Packaging list load failed: %s", e)
            raise HTTPException(
                status_code=400, detail=f"Could not process packaging list file: {e}"
            ) from e
        
        if not pkg_page_images:
            raise HTTPException(
                status_code=400, detail="No readable pages found in packaging list."
            )
        
        try:
            packaging_extraction, packaging_metadata, pkg_parse_error = (
                await extract_packaging_list_structured(pkg_page_images, packaging_brand)
            )
            logger.debug(f"Packaging List Extracted: {packaging_extraction}")
        except Exception as e:
            logger.exception("Packaging list extraction failed")
            raise HTTPException(
                status_code=500, detail=f"Packaging list extraction failed: {e}"
            ) from e
        
        if pkg_parse_error:
            logger.warning(
                f"Packaging list parse/validation failed: {pkg_parse_error}"
            )
    
    # Filter containers if packaging list was successfully extracted
    if packaging_extraction and packaging_extraction.container_number_list:
        pkg_container_numbers = packaging_extraction.container_number_list
        bill_container_numbers = [c.container_no for c in bill_response.containers]

        logger.info(
            f"Pre-filter comparison: "
            f"bill_containers({len(bill_container_numbers)})={bill_container_numbers}, "
            f"pkg_containers({len(pkg_container_numbers)})={pkg_container_numbers}"
        )

        if len(bill_container_numbers) != len(pkg_container_numbers):
            logger.warning(
                f"Container count divergence: bill={len(bill_container_numbers)} "
                f"vs packaging_list={len(pkg_container_numbers)}"
            )

        original_container_count = len(bill_response.containers)

        filtered_containers = filter_containers_by_packaging_list(
            bill_containers=bill_response.containers,
            packaging_container_numbers=pkg_container_numbers,
            fuzzy_threshold=0.85,
        )

        bill_response.containers = filtered_containers
        logger.info(
            f"Container filtering: {len(filtered_containers)}/{original_container_count} "
            f"containers retained"
        )

        if len(filtered_containers) < len(pkg_container_numbers):
            logger.warning(
                f"Some packaging containers had no bill match: "
                f"matched={len(filtered_containers)}, expected={len(pkg_container_numbers)}"
            )
    
    # Aggregate metadata
    if packaging_metadata:
        aggregated_metadata = aggregate_metadata(bill_metadata, packaging_metadata)
    else:
        aggregated_metadata = bill_metadata
    
    # Build final response
    bill_data_dict = bill_response.model_dump(exclude={"metadata"})
    packaging_data_dict = (
        packaging_extraction.model_dump() if packaging_extraction else None
    )
    
    return EnhancedBillNoExtractionResponse(
        bill_extracted_data=bill_data_dict,
        packaging_list=packaging_data_dict,
        metadata=aggregated_metadata,
    )
