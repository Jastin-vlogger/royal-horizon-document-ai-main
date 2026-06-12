"""Cost sheet document APIs."""

from fastapi import APIRouter, Depends, File, UploadFile

from src.dispatchers.i_document_workflow_dispatcher import (
    DocumentWorkflowDispatcherInterface,
)
from src.models.api.costsheet_is_signed import CostSheetIsSignedResponse
from src.routers.dependencies import dispatcher
from src.routers.error_mapping import run_http

router = APIRouter(prefix="/costsheet", tags=["costsheet"])


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
    workflow_dispatcher: DocumentWorkflowDispatcherInterface = Depends(dispatcher),
) -> CostSheetIsSignedResponse:
    return await run_http(
        workflow_dispatcher.costsheet_is_signed(file),
        failure_detail="Signature detection failed",
    )
