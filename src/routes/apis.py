"""Shipment-form and other document extraction APIs."""

import json
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.config.logger import logger
from src.core.document_processor import (
    detect_file_type,
    load_image_bytes,
    read_upload_to_bytes,
)
from src.core.lpo_invoice_business_logics import extract_lpo_invoice
from src.core.performa_invoice_business_logics import extract_performa_invoice
from src.core.shipment_calculations import calculate_shipment_logistics
from src.schemas.response import (
    ExtractionMetadata,
    LPOInvoiceResult,
    PerformaInvoiceResult,
    ShipmentFormResponse,
)

router = APIRouter(prefix="", tags=["extraction"])

# Form field names for the two document types
PERFORMA_INVOICE_FIELD = "performa_invoice"
LPO_INVOICE_FIELD = "lpo_invoice"

ALLOWED_TYPES = {"pdf", "image"}


def _parse_list_form(value: Optional[str]) -> List[str]:
    """Parse optional form field as JSON list of strings; default to empty list."""
    if not value or not value.strip():
        return []
    try:
        data = json.loads(value)
        if isinstance(data, list):
            return [str(x) for x in data]
        return []
    except json.JSONDecodeError:
        return [s.strip() for s in value.split(",") if s.strip()]


@router.post(
    "/shipment-form",
    response_model=ShipmentFormResponse,
    summary="Extract key-value data from Performa Invoice and LPO documents",
)
async def shipment_form(
    performa_invoice: Optional[UploadFile] = File(None, description="Performa Invoice (PDF or image)"),
    lpo_invoice: Optional[UploadFile] = File(None, description="LPO Invoice (PDF or image)"),
    inco_terms_list: Optional[str] = Form(
        None,
        description='JSON array of allowed INCO terms, e.g. ["CIF","FOB","EXWORKS"]',
    ),
    suppliers: Optional[str] = Form(
        None,
        description='JSON array of supplier names, e.g. ["LEKH RAJ","M RAHEEM RICE PROCESSING MILLS"]',
    ),
):
    """
    Accepts two document uploads (Performa Invoice and LPO) plus optional metadata lists.
    Converts PDFs to first-page images, runs document-specific extraction with GPT Vision,
    and returns combined structured JSON with optional usage metadata.
    """
    logger.debug("Processing Shipment Form API")
    inco_list = _parse_list_form(inco_terms_list)
    if not inco_list:
        inco_list = ["CIF", "FOB", "EXWORKS"]
    supplier_list = _parse_list_form(suppliers)

    lpo_result: Optional[LPOInvoiceResult] = None
    performa_result: Optional[PerformaInvoiceResult] = None
    meta_list: List[ExtractionMetadata] = []

    if lpo_invoice and lpo_invoice.filename:
        content, filename = read_upload_to_bytes(lpo_invoice)
        ftype = detect_file_type(filename)
        if ftype not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"LPO file must be PDF or image (jpg, jpeg, png). Got: {filename}",
            )
        try:
            image_bytes = load_image_bytes(content, filename)
        except Exception as e:
            logger.warning(f"LPO image load failed: {e}")
            raise HTTPException(status_code=400, detail=f"Could not process LPO file: {e}") from e
        try:
            lpo_result, lpo_meta = await extract_lpo_invoice(image_bytes)
            if lpo_meta:
                meta_list.append(lpo_meta)
        except Exception as e:
            logger.exception("LPO extraction failed")
            raise HTTPException(status_code=500, detail=f"LPO extraction failed: {e}") from e

    if performa_invoice and performa_invoice.filename:
        content, filename = read_upload_to_bytes(performa_invoice)
        ftype = detect_file_type(filename)
        if ftype not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Performa file must be PDF or image (jpg, jpeg, png). Got: {filename}",
            )
        try:
            image_bytes = load_image_bytes(content, filename)
        except Exception as e:
            logger.warning(f"Performa image load failed: {e}")
            raise HTTPException(status_code=400, detail=f"Could not process Performa file: {e}") from e
        try:
            performa_result, perf_meta = await extract_performa_invoice(
                image_bytes, inco_terms_list=inco_list, suppliers=supplier_list
            )
            if perf_meta:
                meta_list.append(perf_meta)
        except Exception as e:
            logger.exception("Performa extraction failed")
            raise HTTPException(status_code=500, detail=f"Performa extraction failed: {e}") from e

    if not (lpo_invoice and lpo_invoice.filename) and not (performa_invoice and performa_invoice.filename):
        raise HTTPException(
            status_code=400,
            detail="At least one file must be provided: performa_invoice or lpo_invoice",
        )

    # Aggregate metadata (sum tokens and cost)
    aggregated: Optional[ExtractionMetadata] = None
    if meta_list:
        aggregated = ExtractionMetadata(
            input_tokens=sum(m.input_tokens for m in meta_list),
            output_tokens=sum(m.output_tokens for m in meta_list),
            total_tokens=sum(m.total_tokens for m in meta_list),
            cost_incurred=round(sum(m.cost_incurred for m in meta_list), 6),
            cost_currency=meta_list[0].cost_currency if meta_list else "USD",
            latency_ms=sum(m.latency_ms for m in meta_list),
            model=meta_list[0].model if meta_list else "",
        )

    # Post-process: shipment logistics and price reconciliation
    combined = {
        "lpo_invoice": lpo_result.model_dump(exclude_none=False) if lpo_result else None,
        "performa_invoice": performa_result.model_dump(exclude_none=False) if performa_result else None,
        "metadata": aggregated.model_dump() if aggregated else None,
    }
    with_calcs = calculate_shipment_logistics(combined)
    shipment_calculations = with_calcs.get("shipment_calculations")

    return ShipmentFormResponse(
        lpo_invoice=lpo_result,
        performa_invoice=performa_result,
        metadata=aggregated,
        shipment_calculations=shipment_calculations,
    )
