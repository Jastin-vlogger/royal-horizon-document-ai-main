"""Shipment-form document extraction APIs."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from src.dispatchers.i_document_workflow_dispatcher import (
    DocumentWorkflowDispatcherInterface,
)
from src.models.api.response import ShipmentFormResponse
from src.routers.dependencies import dispatcher
from src.routers.error_mapping import run_http

router = APIRouter(prefix="", tags=["extraction"])


@router.post(
    "/shipment-form",
    response_model=ShipmentFormResponse,
    summary="Classify and extract LPO and Rice Quality Report",
)
async def shipment_form(
    lpo_invoice: Optional[UploadFile] = File(
        None,
        description="LPO Invoice (PDF or image)",
    ),
    rice_quality_report: Optional[UploadFile] = File(
        None,
        description="Rice Quality Report (PDF or image)",
    ),
    inco_terms_list: Optional[str] = Form(
        None,
        description='JSON array of allowed INCO terms, e.g. ["CIF","FOB","EXWORKS"]',
    ),
    suppliers: Optional[str] = Form(
        None,
        description='JSON array of supplier names, e.g. ["LEKH RAJ"]',
    ),
    workflow_dispatcher: DocumentWorkflowDispatcherInterface = Depends(dispatcher),
) -> ShipmentFormResponse:
    return await run_http(
        workflow_dispatcher.shipment_form(
            lpo_invoice=lpo_invoice,
            rice_quality_report=rice_quality_report,
            inco_terms_list=inco_terms_list,
            suppliers=suppliers,
        ),
        failure_detail="Document extraction failed",
    )
