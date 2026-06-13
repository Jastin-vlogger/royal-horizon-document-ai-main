"""BOE extraction API."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.dispatchers.i_document_workflow_dispatcher import (
    DocumentWorkflowDispatcherInterface,
)
from src.models.api.boe import BoeExtractResponse, BoeValidationErrorResponse
from src.routers.dependencies import dispatcher
from src.routers.error_mapping import run_http

router = APIRouter(prefix="/boe", tags=["boe"])


@router.post(
    "/extract",
    response_model=BoeExtractResponse,
    summary="Extract container numbers and DCE DATE from a BOE document",
    responses={
        200: {
            "description": "BOE fields extracted successfully.",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "Successful extraction",
                            "value": {
                                "success": True,
                                "data": {
                                    "containers": [
                                        "CBHU3475526",
                                        "CLHU3820005",
                                        "DVRU1599581",
                                    ],
                                    "date": "19/01/2026",
                                },
                                "metadata": {
                                    "input_tokens": 600,
                                    "output_tokens": 80,
                                    "total_tokens": 680,
                                    "cost_incurred": 0.0023,
                                    "cost_currency": "USD",
                                    "latency_ms": 1500.0,
                                    "model": "gpt-4o",
                                },
                            },
                        },
                        "empty": {
                            "summary": "No BOE fields found",
                            "value": {
                                "success": True,
                                "data": {"containers": [], "date": None},
                                "metadata": {
                                    "input_tokens": 600,
                                    "output_tokens": 40,
                                    "total_tokens": 640,
                                    "cost_incurred": 0.0021,
                                    "cost_currency": "USD",
                                    "latency_ms": 1400.0,
                                    "model": "gpt-4o",
                                },
                            },
                        },
                    }
                }
            },
        },
        400: {
            "model": BoeValidationErrorResponse,
            "description": "Input validation failed.",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "message": "PDF exceeds maximum allowed pages",
                    }
                }
            },
        },
    },
)
async def boe_extract(
    file: UploadFile = File(
        ...,
        description="BOE input file (PDF/JPG/JPEG/PNG).",
    ),
    workflow_dispatcher: DocumentWorkflowDispatcherInterface = Depends(dispatcher),
) -> BoeExtractResponse | JSONResponse:
    try:
        return await run_http(
            workflow_dispatcher.boe_extract(file),
            failure_detail="BOE extraction failed",
        )
    except HTTPException as exc:
        if exc.status_code == 400:
            error = BoeValidationErrorResponse(
                success=False,
                message=str(exc.detail),
            )
            return JSONResponse(status_code=400, content=error.model_dump())
        raise
