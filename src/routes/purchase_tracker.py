"""Purchase tracker APIs: B/L number and future extraction endpoints."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.config.logger import logger
from src.core.document_processor import (
    detect_file_type,
    load_image_bytes,
    read_upload_to_bytes,
)
from src.core.purchase_tracker_bill_no import extract_bill_no
from src.schemas.response import BillNoExtractionResponse

router = APIRouter(prefix="/purchase-tracker", tags=["purchase-tracker"])

ALLOWED_TYPES = {"pdf", "image"}


@router.post(
    "/bill-no",
    response_model=BillNoExtractionResponse,
    summary="Extract Bill of Lading number from shipping document",
)
async def extract_bill_no_from_document(
    file: UploadFile = File(..., description="Shipping document (image or single-page PDF)"),
) -> BillNoExtractionResponse:
    """
    Accepts one file (image or single-page PDF) of a purchase/shipping bill.
    Extracts the Bill of Lading number (B/L NUMBER) and returns it with usage metadata.
    Returns bill_no as null if not found.
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
        image_bytes = load_image_bytes(content, filename)
    except Exception as e:
        logger.warning("Bill-no document load failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Could not process file: {e}") from e
    try:
        bill_no, metadata = await extract_bill_no(image_bytes)
    except Exception as e:
        logger.exception("B/L extraction failed")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}") from e
    return BillNoExtractionResponse(bill_no=bill_no, metadata=metadata)
