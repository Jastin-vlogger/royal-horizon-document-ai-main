"""Stock-sheet extraction API."""

from fastapi import APIRouter, Depends, File, UploadFile

from src.dispatchers.i_document_workflow_dispatcher import (
    DocumentWorkflowDispatcherInterface,
)
from src.models.api.stock_sheet import StockSheetResponse
from src.routers.dependencies import dispatcher
from src.routers.error_mapping import run_http

router = APIRouter(prefix="", tags=["stock-sheet"])


@router.post(
    "/extract/stock-sheet",
    response_model=StockSheetResponse,
    summary="Extract stock-sheet table rows from PDF or image",
)
async def extract_stock_sheet(
    file: UploadFile = File(
        ...,
        description="Stock-sheet input file (PDF/JPG/JPEG/PNG).",
    ),
    workflow_dispatcher: DocumentWorkflowDispatcherInterface = Depends(dispatcher),
) -> StockSheetResponse:
    return await run_http(
        workflow_dispatcher.stock_sheet_extract(file),
        failure_detail="Stock-sheet extraction failed",
    )
