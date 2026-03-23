"""Arrival notice extraction API."""

from PIL import UnidentifiedImageError

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.config.logger import logger
from src.core.arrival_notice_extract import (
    extract_arrival_notice_from_pages,
    upload_to_png_pages,
    validate_upload_type,
)
from src.core.document_processor import read_upload_to_bytes
from src.schemas.arrival_notice import ArrivalNoticeExtractResponse

router = APIRouter(prefix="/arrival-notice", tags=["arrival-notice"])


@router.post(
    "/extract",
    response_model=ArrivalNoticeExtractResponse,
    summary="Extract arrival date and free retention days from arrival notice (PDF all pages or image)",
)
async def arrival_notice_extract(
    file: UploadFile = File(
        ...,
        description="Arrival notice or related document: PDF (all pages) or image (JPEG/PNG).",
    ),
) -> ArrivalNoticeExtractResponse:
    """
    Vision extraction of `arrival_on` (YYYY-MM-DD) and `free_retension_days` (e.g. \"14 days\")
    from shipping/arrival paperwork. PDFs are rasterized page-by-page and sent in one request.
    """
    logger.debug("Processing arrival-notice extract API")
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="A file must be provided.")

    content, filename = read_upload_to_bytes(file)
    try:
        validate_upload_type(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        png_pages = upload_to_png_pages(content, filename)
    except ValueError as e:
        logger.warning(f"Arrival notice PDF/image conversion failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Could not read document: {e}",
        ) from e
    except UnidentifiedImageError as e:
        logger.warning(f"Arrival notice image unreadable: {e}")
        raise HTTPException(
            status_code=400,
            detail="Could not decode image file. Use a valid JPEG or PNG.",
        ) from e
    except Exception as e:
        logger.warning(f"Arrival notice file load failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Could not process file: {e}",
        ) from e

    try:
        return await extract_arrival_notice_from_pages(png_pages)
    except ValueError as e:
        logger.warning(f"Arrival notice LLM output invalid: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"LLM response could not be validated: {e}",
        ) from e
    except RuntimeError as e:
        logger.warning(f"Arrival notice configuration error: {e}")
        raise HTTPException(
            status_code=503,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Arrival notice extraction failed")
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {e}",
        ) from e
