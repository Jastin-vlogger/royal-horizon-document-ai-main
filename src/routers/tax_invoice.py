"""Tax invoice extraction API."""

from fastapi import APIRouter, Depends, File, UploadFile

from src.dispatchers.i_document_workflow_dispatcher import (
    DocumentWorkflowDispatcherInterface,
)
from src.models.api.tax_invoice import TaxInvoiceExtractionResponse
from src.routers.dependencies import dispatcher
from src.routers.error_mapping import run_http

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
    workflow_dispatcher: DocumentWorkflowDispatcherInterface = Depends(dispatcher),
) -> TaxInvoiceExtractionResponse:
    return await run_http(
        workflow_dispatcher.tax_invoice_extraction(file),
        failure_detail="Extraction failed",
    )
