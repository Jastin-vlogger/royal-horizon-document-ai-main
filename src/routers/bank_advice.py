"""Bank advice document APIs."""

from fastapi import APIRouter, Depends, File, UploadFile

from src.dispatchers.i_document_workflow_dispatcher import (
    DocumentWorkflowDispatcherInterface,
)
from src.models.api.bank_advice_is_signed import BankAdviceIsSignedResponse
from src.routers.dependencies import dispatcher
from src.routers.error_mapping import run_http

router = APIRouter(prefix="/bank-advice-doc", tags=["bank-advice"])


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
    workflow_dispatcher: DocumentWorkflowDispatcherInterface = Depends(dispatcher),
) -> BankAdviceIsSignedResponse:
    return await run_http(
        workflow_dispatcher.bank_advice_is_signed(file),
        failure_detail="Signature detection failed",
    )
