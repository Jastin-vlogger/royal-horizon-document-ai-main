"""Purchase tracker APIs: B/L number and structured bill extraction."""

from PIL import UnidentifiedImageError

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.config.logger import logger
from src.core.document_processor import (
    detect_file_type,
    load_bill_document_pages,
    read_upload_to_bytes,
)
from src.core.purchase_tracker_bill_no import (
    build_bill_no_api_response,
    extract_bill_structured,
)
from src.schemas.response import BillNoExtractionResponse

router = APIRouter(prefix="/purchase-tracker", tags=["purchase-tracker"])

ALLOWED_TYPES = {"pdf", "image"}


@router.post(
    "/fetch-details",
    response_model=BillNoExtractionResponse,
    summary="Extract structured Bill of Loading data from shipping document",
)
async def extract_bill_no_from_document(
    file: UploadFile = File(
        ...,
        description="Shipping document: PDF (pages 1–2 used) or image (PNG/JPEG).",
    ),
) -> BillNoExtractionResponse:
    """
    Accepts PDF or image. Multi-page PDFs: only page 1 and page 2 are sent to the model.

    Returns a flat JSON object: all extracted fields plus `metadata` (tokens, cost, latency).
    If the model output cannot be parsed or validated, scalar fields are null and `containers` is [].
    """
    logger.debug("Processing Purchase Tracker bill-no API")
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="A file must be provided.")
    content, filename = read_upload_to_bytes(file)
    ftype = detect_file_type(filename)
    if ftype not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File must be PDF or image (jpg, jpeg, png). Got: {filename}",
        )
    try:
        page_images = load_bill_document_pages(content, filename)
    except ValueError as e:
        logger.warning("Bill document pages unavailable: %s", e)
        raise HTTPException(
            status_code=400,
            detail=f"Could not read document pages: {e}",
        ) from e
    except UnidentifiedImageError as e:
        logger.warning("Bill document image unreadable: %s", e)
        raise HTTPException(
            status_code=400,
            detail="Could not decode image file. Use a valid JPEG or PNG.",
        ) from e
    except Exception as e:
        logger.warning("Bill-no document load failed: %s", e)
        raise HTTPException(
            status_code=400, detail=f"Could not process file: {e}"
        ) from e

    if not page_images:
        raise HTTPException(
            status_code=400, detail="No readable pages found in the document."
        )

    try:
        extraction, metadata, parse_error = await extract_bill_structured(page_images)
        logger.debug(f"Extracted Details: {extraction}")
    except Exception as e:
        logger.exception("B/L structured extraction failed")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}") from e

    if parse_error:
        logger.warning(
            "Bill-no parse/validation failed (returning null fields): %s", parse_error
        )

    return build_bill_no_api_response(extraction, metadata)
