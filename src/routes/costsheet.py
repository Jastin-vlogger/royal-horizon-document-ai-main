"""Cost sheet document APIs."""

from PIL import UnidentifiedImageError

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.config.logger import logger
from src.core.costsheet_is_signed import run_costsheet_signature_detection
from src.core.document_processor import (
    detect_file_type,
    load_image_bytes,
    read_upload_to_bytes,
)
from src.schemas.costsheet_is_signed import CostSheetIsSignedResponse

router = APIRouter(prefix="/costsheet", tags=["costsheet"])

ALLOWED_TYPES = {"pdf", "image"}


@router.post(
    "/is-signed",
    response_model=CostSheetIsSignedResponse,
    summary="Detect handwritten signatures on a cost sheet (PDF first page or image)",
)
async def costsheet_is_signed(
    file: UploadFile = File(
        ...,
        description="Cost sheet: PDF (only first page is analyzed) or image (JPEG/PNG).",
    ),
) -> CostSheetIsSignedResponse:
    """
    Runs vision-based signature detection on the left-margin AP / FC / CFO / MD blocks.
    PDFs are rasterized to an image for the first page only.
    """
    logger.debug("Processing cost sheet is-signed API")
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
        logger.warning("Cost sheet PDF/image conversion failed: %s", e)
        raise HTTPException(
            status_code=400,
            detail=f"Could not read document (PDF or image): {e}",
        ) from e
    except UnidentifiedImageError as e:
        logger.warning("Cost sheet image unreadable: %s", e)
        raise HTTPException(
            status_code=400,
            detail="Could not decode image file. Use a valid JPEG or PNG.",
        ) from e
    except Exception as e:
        logger.warning("Cost sheet file load failed: %s", e)
        raise HTTPException(
            status_code=400,
            detail=f"Could not process file: {e}",
        ) from e

    try:
        return await run_costsheet_signature_detection(image_bytes)
    except ValueError as e:
        logger.warning("Cost sheet LLM output invalid: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"LLM response could not be validated: {e}",
        ) from e
    except Exception as e:
        logger.exception("Cost sheet signature detection failed")
        raise HTTPException(
            status_code=500,
            detail=f"Signature detection failed: {e}",
        ) from e
