"""Purchase tracker APIs."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from src.dispatchers.i_document_workflow_dispatcher import (
    DocumentWorkflowDispatcherInterface,
)
from src.models.api.response import EnhancedBillNoExtractionResponse
from src.routers.dependencies import dispatcher
from src.routers.error_mapping import run_http

router = APIRouter(prefix="/purchase-tracker", tags=["purchase-tracker"])


@router.post(
    "/fetch-details",
    response_model=EnhancedBillNoExtractionResponse,
    summary="Extract structured Bill of Lading and Packaging List data",
)
async def extract_bill_no_from_document(
    file: UploadFile = File(
        ...,
        description="Bill of Lading document: PDF or image.",
    ),
    packaging_list_file: Optional[UploadFile] = File(
        None,
        description="Packaging List document: PDF or image. Optional.",
    ),
    packaging_brand: Optional[str] = Form(
        None,
        description="Target brand name to extract from packaging list.",
    ),
    workflow_dispatcher: DocumentWorkflowDispatcherInterface = Depends(dispatcher),
) -> EnhancedBillNoExtractionResponse:
    return await run_http(
        workflow_dispatcher.purchase_tracker_fetch_details(
            file=file,
            packaging_list_file=packaging_list_file,
            packaging_brand=packaging_brand,
        ),
        failure_detail="Bill extraction failed",
    )
