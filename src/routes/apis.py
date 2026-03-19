"""Shipment-form and other document extraction APIs."""

import asyncio
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
from src.core.rice_quality_report_business_logics import extract_rice_quality_report
from src.core.shipment_calculations import calculate_shipment_logistics
from src.core.shipment_document_classification import classify_shipment_documents
from src.schemas.response import (
    ExtractionMetadata,
    ShipmentFormResponse,
)

router = APIRouter(prefix="", tags=["extraction"])

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


def _upload_to_png_bytes(upload: UploadFile, label: str) -> bytes:
    """Read upload, validate type, return PNG bytes (PDF first page only)."""
    content, filename = read_upload_to_bytes(upload)
    ftype = detect_file_type(filename)
    if ftype not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"{label} must be PDF or image (jpg, jpeg, png). Got: {filename}",
        )
    try:
        return load_image_bytes(content, filename)
    except Exception as e:
        logger.warning(f"{label} image load failed: {e}")
        raise HTTPException(
            status_code=400, detail=f"Could not process {label} file: {e}"
        ) from e


def _aggregate_metadata(meta_list: List[ExtractionMetadata]) -> Optional[ExtractionMetadata]:
    if not meta_list:
        return None
    return ExtractionMetadata(
        input_tokens=sum(m.input_tokens for m in meta_list),
        output_tokens=sum(m.output_tokens for m in meta_list),
        total_tokens=sum(m.total_tokens for m in meta_list),
        cost_incurred=round(sum(m.cost_incurred for m in meta_list), 6),
        cost_currency=meta_list[0].cost_currency if meta_list else "USD",
        latency_ms=sum(m.latency_ms for m in meta_list),
        model=meta_list[0].model if meta_list else "",
    )


@router.post(
    "/shipment-form",
    response_model=ShipmentFormResponse,
    summary="Classify LPO, Performa Invoice, and Rice Quality Report; then extract all three",
)
async def shipment_form(
    performa_invoice: Optional[UploadFile] = File(
        None, description="Performa Invoice (PDF or image)"
    ),
    lpo_invoice: Optional[UploadFile] = File(
        None, description="LPO Invoice (PDF or image)"
    ),
    rice_quality_report: Optional[UploadFile] = File(
        None, description="Rice Quality Report (PDF or image)"
    ),
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
    Requires three uploads. Runs classification first; on success runs LPO, Performa, and
    Rice Quality extraction in parallel. PDFs use the first page only.
    """
    logger.debug("Processing Shipment Form API")
    inco_list = _parse_list_form(inco_terms_list)
    if not inco_list:
        inco_list = ["CIF", "FOB", "EXWORKS", "C&F"]
    supplier_list = _parse_list_form(suppliers)

    if not (
        lpo_invoice
        and lpo_invoice.filename
        and performa_invoice
        and performa_invoice.filename
        and rice_quality_report
        and rice_quality_report.filename
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "All three files are required: lpo_invoice, performa_invoice, "
                "rice_quality_report"
            ),
        )

    lpo_png = _upload_to_png_bytes(lpo_invoice, "LPO")
    performa_png = _upload_to_png_bytes(performa_invoice, "Performa Invoice")
    rice_png = _upload_to_png_bytes(rice_quality_report, "Rice Quality Report")

    meta_list: List[ExtractionMetadata] = []

    try:
        classified_data, cls_meta = await classify_shipment_documents(
            [lpo_png, performa_png, rice_png]
        )
    except Exception as e:
        logger.exception("Shipment classification failed")
        raise HTTPException(
            status_code=500, detail=f"Document classification failed: {e}"
        ) from e

    meta_list.append(cls_meta)

    if not classified_data.get("is_valid_document"):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "document_classification_failed",
                "reason": classified_data.get("reason", ""),
                "has_lpo": classified_data.get("has_lpo", False),
                "has_performa_invoice": classified_data.get(
                    "has_performa_invoice", False
                ),
                "has_ricequality_doc": classified_data.get("has_ricequality_doc", False),
                "is_valid_document": False,
                "classified_data": classified_data,
            },
        )

    try:
        (lpo_result, lpo_meta), (performa_result, perf_meta), (rice_data, rice_meta) = (
            await asyncio.gather(
                extract_lpo_invoice(lpo_png),
                extract_performa_invoice(
                    performa_png,
                    inco_terms_list=inco_list,
                    suppliers=supplier_list,
                ),
                extract_rice_quality_report(rice_png),
            )
        )
    except ValueError as e:
        logger.exception("Rice quality extraction failed")
        raise HTTPException(
            status_code=500, detail=f"Rice Quality Report extraction failed: {e}"
        ) from e
    except Exception as e:
        logger.exception("Parallel shipment extraction failed")
        raise HTTPException(
            status_code=500, detail=f"Document extraction failed: {e}"
        ) from e

    for m in (lpo_meta, perf_meta, rice_meta):
        if m is not None:
            meta_list.append(m)

    aggregated = _aggregate_metadata(meta_list)

    combined = {
        "lpo_invoice": lpo_result.model_dump(exclude_none=False)
        if lpo_result
        else None,
        "performa_invoice": performa_result.model_dump(exclude_none=False)
        if performa_result
        else None,
        "metadata": aggregated.model_dump() if aggregated else None,
    }
    with_calcs = calculate_shipment_logistics(combined)
    shipment_calculations = with_calcs.get("shipment_calculations")
    logger.debug(f"Shipment Calculations: {shipment_calculations}")

    return ShipmentFormResponse(
        lpo_invoice=lpo_result,
        performa_invoice=performa_result,
        metadata=aggregated,
        shipment_calculations=shipment_calculations,
        classified_data=classified_data,
        s1_quality_report=rice_data,
    )
