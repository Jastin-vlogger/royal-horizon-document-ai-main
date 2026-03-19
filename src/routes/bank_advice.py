"""Bank advice document APIs."""

from PIL import UnidentifiedImageError

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.config.logger import logger
from src.core.bank_advice_is_signed import run_bank_advice_signature_detection
from src.core.document_processor import (
    detect_file_type,
    load_image_bytes,
    read_upload_to_bytes,
)
from src.schemas.bank_advice_is_signed import BankAdviceIsSignedResponse

router = APIRouter(prefix="/bank-advice-doc", tags=["bank-advice"])

ALLOWED_TYPES = {"pdf", "image"}


@router.post(
    "/is-signed",
    response_model=BankAdviceIsSignedResponse,
    summary="Detect handwritten signature and seal on bank advice (PDF first page or image)",
)
async def bank_advice_is_signed(
    file: UploadFile = File(
        ...,
        description="Bank advice: PDF (only first page is analyzed) or image (JPEG/PNG).",
    ),
) -> BankAdviceIsSignedResponse:
    """
    Vision-based detection of handwritten signature and stamp/seal on trade finance
    bank advice style documents. PDFs are rasterized to an image for the first page only.
    """
    logger.debug("Processing bank-advice is-signed API")
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
    except ValueError as e:
        logger.warning(f"Bank advice PDF/image conversion failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Could not read document (PDF or image): {e}",
        ) from e
    except UnidentifiedImageError as e:
        logger.warning(f"Bank advice image unreadable: {e}")
        raise HTTPException(
            status_code=400,
            detail="Could not decode image file. Use a valid JPEG or PNG.",
        ) from e
    except Exception as e:
        logger.warning(f"Bank advice file load failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Could not process file: {e}",
        ) from e

    try:
        return await run_bank_advice_signature_detection(image_bytes)
    except ValueError as e:
        logger.warning(f"Bank advice LLM output invalid: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"LLM response could not be validated: {e}",
        ) from e
    except RuntimeError as e:
        logger.warning(f"Bank advice LLM runtime error: {e}")
        raise HTTPException(
            status_code=502,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception(f"Bank advice signature detection failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Signature detection failed: {e}",
        ) from e
