"""Tax invoice extraction API."""

from PIL import UnidentifiedImageError

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.config.logger import logger
from src.core.document_processor import read_upload_to_bytes
from src.core.tax_invoice_extractor import extract_tax_invoice, load_tax_invoice_input
from src.schemas.tax_invoice import TaxInvoiceExtractionResponse

router = APIRouter(prefix="", tags=["tax-invoice"])


@router.post(
    "/tax_invoice_extraction",
    response_model=TaxInvoiceExtractionResponse,
    summary="Extract key fields from tax invoice (PDF first page or image)",
)
async def tax_invoice_extraction(
    file: UploadFile = File(
        ...,
        description="Tax invoice file: PDF (first page only) or image (JPEG/PNG).",
    ),
) -> TaxInvoiceExtractionResponse:
    """
    Extract `po_number`, `invoice_id`, `invoice_date`, and `bill_to` from a tax invoice.
    Supports file upload only.
    For PDFs, only the first page is processed.
    """
    logger.debug("Processing tax_invoice_extraction API")

    file_content, file_name = read_upload_to_bytes(file)

    try:
        image_png = load_tax_invoice_input(file_content, file_name)
    except ValueError as exc:
        logger.warning("Tax invoice input validation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UnidentifiedImageError as exc:
        logger.warning("Tax invoice image decode failed: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Could not decode image file. Use a valid JPEG or PNG.",
        ) from exc
    except Exception as exc:
        logger.exception("Tax invoice file processing failed")
        raise HTTPException(
            status_code=400,
            detail=f"Could not process input document: {exc}",
        ) from exc

    try:
        extraction_result, metadata = await extract_tax_invoice(image_png)
    except ValueError as exc:
        logger.warning("Tax invoice model output invalid: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"LLM response could not be validated: {exc}",
        ) from exc
    except RuntimeError as exc:
        logger.warning("Tax invoice extraction configuration issue: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Tax invoice extraction failed")
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {exc}",
        ) from exc

    return TaxInvoiceExtractionResponse(
        tax_invoice_extraction_result=extraction_result,
        metadata=metadata,
    )
