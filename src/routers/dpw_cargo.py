"""DPW cargo receipt extraction API."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.dispatchers.i_document_workflow_dispatcher import (
    DocumentWorkflowDispatcherInterface,
)
from src.models.api.dpw_cargo import DpwCargoExtractorResponse
from src.routers.dependencies import dispatcher
from src.routers.error_mapping import run_http

router = APIRouter(prefix="", tags=["dpw-cargo"])


@router.post(
    "/dpw-cargo-extractor",
    response_model=DpwCargoExtractorResponse,
    summary="Extract date, receipt number, and containers from a DPW cargo receipt PDF",
)
async def dpw_cargo_extractor(
    file: UploadFile = File(
        ...,
        description="DPW cargo receipt PDF file.",
    ),
    workflow_dispatcher: DocumentWorkflowDispatcherInterface = Depends(dispatcher),
) -> DpwCargoExtractorResponse | JSONResponse:
    try:
        return await run_http(
            workflow_dispatcher.dpw_cargo_extract(file),
            failure_detail="DPW cargo extraction failed",
        )
    except HTTPException as exc:
        error = DpwCargoExtractorResponse.failure(str(exc.detail))
        return JSONResponse(status_code=exc.status_code, content=error.model_dump())
