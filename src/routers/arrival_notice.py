"""Arrival notice extraction API."""

from fastapi import APIRouter, Depends, File, UploadFile

from src.dispatchers.i_document_workflow_dispatcher import (
    DocumentWorkflowDispatcherInterface,
)
from src.models.api.arrival_notice import ArrivalNoticeExtractResponse
from src.routers.dependencies import dispatcher
from src.routers.error_mapping import run_http

router = APIRouter(prefix="/arrival-notice", tags=["arrival-notice"])


@router.post(
    "/extract",
    response_model=ArrivalNoticeExtractResponse,
    summary="Extract arrival date and free retention days from arrival notice",
)
async def arrival_notice_extract(
    file: UploadFile = File(
        ...,
        description="Arrival notice or related document: PDF or image.",
    ),
    workflow_dispatcher: DocumentWorkflowDispatcherInterface = Depends(dispatcher),
) -> ArrivalNoticeExtractResponse:
    return await run_http(
        workflow_dispatcher.arrival_notice_extract(file),
        failure_detail="Extraction failed",
    )
