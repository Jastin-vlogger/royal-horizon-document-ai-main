"""Pure extraction parsing, validation, and response shaping."""

import json
import re
from typing import Any, Optional

from pydantic import ValidationError

from src.models.api.arrival_notice import (
    ArrivalNoticeExtractResponse,
    ArrivalNoticeLLMOutput,
)
from src.models.api.bank_advice_is_signed import (
    BankAdviceIsSignedMetadata,
    BankAdviceIsSignedResponse,
    BankAdviceSignatureLLMOutput,
)
from src.models.api.costsheet_is_signed import (
    CostSheetIsSignedMetadata,
    CostSheetIsSignedResponse,
    CostSheetSignatureLLMOutput,
)
from src.models.api.packaging_list import PackagingListExtraction
from src.models.api.response import (
    BillNoExtractionResponse,
    BillOfLadingStructuredExtraction,
    ExtractionMetadata,
    LPOInvoiceResult,
    LPOLineItem,
)
from src.models.api.tax_invoice import TaxInvoiceExtractionResult, TaxInvoiceLLMOutput
from src.processing.shared.json_utils import parse_json_from_content
from src.processing.shipment.commodity_normalizer import normalize_commodity


def strip_json_from_llm_text(raw: str) -> str:
    """Extract JSON object text and remove optional markdown fences."""

    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
        return text.strip()
    match = re.search(r"\{[\s\S]*\}\s*$", text)
    if match:
        return match.group(0).strip()
    return text


def _metadata_as_bank(metadata: ExtractionMetadata) -> BankAdviceIsSignedMetadata:
    return BankAdviceIsSignedMetadata(**metadata.model_dump())


def _metadata_as_costsheet(metadata: ExtractionMetadata) -> CostSheetIsSignedMetadata:
    return CostSheetIsSignedMetadata(**metadata.model_dump())


def parse_bank_advice_response(
    content: str,
    metadata: ExtractionMetadata,
) -> BankAdviceIsSignedResponse:
    stripped = strip_json_from_llm_text(content)
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM output is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("LLM JSON root must be an object")
    try:
        llm_part = BankAdviceSignatureLLMOutput.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"LLM JSON does not match schema: {exc}") from exc
    return BankAdviceIsSignedResponse(
        is_signed=llm_part.is_signed,
        is_sealed=llm_part.is_sealed,
        metadata=_metadata_as_bank(metadata),
    )


def _normalize_costsheet_signature_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("LLM JSON root must be an object")

    out = dict(data)
    signed_by = out.get("signed_by")
    if isinstance(signed_by, dict):
        for key in ("is_ap_signed", "is_fc_signed", "is_cfo_signed", "is_md_signed"):
            out.pop(key, None)
        return out

    legacy_keys = ("is_ap_signed", "is_fc_signed", "is_cfo_signed", "is_md_signed")
    if all(key in out for key in legacy_keys):
        out["signed_by"] = {
            "ap": bool(out.pop("is_ap_signed")),
            "fc": bool(out.pop("is_fc_signed")),
            "cfo": bool(out.pop("is_cfo_signed")),
            "md": bool(out.pop("is_md_signed")),
        }
    return out


def parse_costsheet_response(
    content: str,
    metadata: ExtractionMetadata,
) -> CostSheetIsSignedResponse:
    stripped = strip_json_from_llm_text(content)
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM output is not valid JSON: {exc}") from exc
    try:
        llm_part = CostSheetSignatureLLMOutput.model_validate(
            _normalize_costsheet_signature_payload(raw)
        )
    except ValidationError as exc:
        raise ValueError(f"LLM JSON does not match schema: {exc}") from exc
    return CostSheetIsSignedResponse(
        is_all_signed=llm_part.is_all_signed,
        signed_by=llm_part.signed_by,
        metadata=_metadata_as_costsheet(metadata),
    )


def parse_arrival_notice_response(
    content: str,
    metadata: ExtractionMetadata,
) -> ArrivalNoticeExtractResponse:
    stripped = strip_json_from_llm_text(content)
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM output is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("LLM JSON root must be an object")
    try:
        parsed = ArrivalNoticeLLMOutput.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"LLM JSON failed schema validation: {exc}") from exc
    return ArrivalNoticeExtractResponse(
        print_date=parsed.print_date,
        arrival_on=parsed.arrival_on,
        free_retension_days=parsed.free_retension_days,
        metadata=metadata,
    )


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() == "null":
        return None
    return normalized


def parse_tax_invoice_response(content: str) -> TaxInvoiceExtractionResult:
    stripped = strip_json_from_llm_text(content)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM output is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("LLM JSON root must be an object")
    try:
        parsed = TaxInvoiceLLMOutput.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"LLM JSON failed schema validation: {exc}") from exc
    return TaxInvoiceExtractionResult(
        po_number=_normalize_optional_text(parsed.po_number),
        invoice_id=_normalize_optional_text(parsed.invoice_id),
        invoice_date=_normalize_optional_text(parsed.invoice_date),
        bill_to=_normalize_optional_text(parsed.bill_to),
    )


def normalize_packaging_uom(value: Optional[str]) -> Optional[str]:
    """Normalize packaging UOM to values such as 1X10KG or 4X10KG."""

    if value is None or not isinstance(value, str) or not value.strip():
        return value if value is None else None
    text = value.strip().upper()
    text = re.sub(r"^[A-Z/]+\s*", "", text)
    mult_match = re.search(r"(\d+)\s*[xX*]\s*(\d+)\s*(?:kg|KG)?", text)
    if mult_match:
        left, right = int(mult_match.group(1)), int(mult_match.group(2))
        return f"{left}X{right}KG"
    single_match = re.search(r"(\d+\.?\d*)\s*(?:kg|KG)?", text)
    if single_match:
        return f"{int(float(single_match.group(1)))}KG"
    return value.strip() or value


def _normalize_inco_text_for_match(text: str) -> str:
    normalized = text.strip().upper().rstrip(".;:, ")
    normalized = re.sub(r"\s*&\s*", "&", normalized)
    normalized = re.sub(r"\s+AND\s+", "&", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def normalize_inco_terms_to_allowed(
    extracted: Optional[str],
    allowed: list[str],
) -> Optional[str]:
    if not extracted or not isinstance(extracted, str) or not extracted.strip():
        return None
    cleaned = [item.strip() for item in allowed if isinstance(item, str) and item.strip()]
    if not cleaned:
        return None
    normalized_extracted = _normalize_inco_text_for_match(extracted)
    if not normalized_extracted:
        return None
    for term in sorted(cleaned, key=len, reverse=True):
        normalized_term = _normalize_inco_text_for_match(term)
        if not normalized_term:
            continue
        if normalized_extracted == normalized_term:
            return term
        if normalized_extracted.startswith(normalized_term + " "):
            return term
        if f" {normalized_term} " in f" {normalized_extracted} ":
            return term
        if len(normalized_extracted) > len(normalized_term) and normalized_extracted.startswith(
            normalized_term
        ):
            if normalized_extracted[len(normalized_term)] in " \t.,;:/":
                return term
    first = normalized_extracted.split()[0].rstrip(".;:, ") if normalized_extracted.split() else ""
    for term in sorted(cleaned, key=len, reverse=True):
        if first == _normalize_inco_text_for_match(term):
            return term
    return None


def normalize_payment_terms(value: Optional[str]) -> Optional[str]:
    if value is None or not isinstance(value, str) or not value.strip():
        return value
    return re.sub(r"(\d+(?:[.,]\d+)?)\s+%", r"\1%", value)


def canonical_buying_unit_from_uom(uom: Optional[str]) -> Optional[str]:
    if not uom or not isinstance(uom, str):
        return None
    prefix = uom.strip().split("/")[0].strip().upper()
    if not prefix:
        return None
    if prefix in ("BAGS", "BAG"):
        return "BAG"
    if prefix.endswith("S") and len(prefix) > 1:
        singular = prefix[:-1]
        if singular in ("BAG", "TON", "BOX", "SACK", "DRUM"):
            return singular
    return prefix


def parse_lpo_invoice_response(
    content: str,
    inco_terms_list: list[str],
) -> Optional[LPOInvoiceResult]:
    data = parse_json_from_content(content)
    if data is None:
        return None
    if isinstance(data, list):
        data = data[0] if data and isinstance(data[0], dict) else {}

    raw_inco = data.get("inco_terms")
    if raw_inco is not None and inco_terms_list:
        data["inco_terms"] = normalize_inco_terms_to_allowed(
            raw_inco if isinstance(raw_inco, str) else str(raw_inco),
            inco_terms_list,
        )

    raw_payment = data.get("payment_terms")
    if raw_payment is not None:
        data["payment_terms"] = normalize_payment_terms(
            raw_payment if isinstance(raw_payment, str) else str(raw_payment)
        )

    for key in (
        "vendor_email",
        "port_of_loading",
        "port_of_discharge",
        "bank_name",
        "pi_number",
        "pi_date",
    ):
        data.setdefault(key, None)
        if isinstance(data.get(key), str) and not data[key].strip():
            data[key] = None

    items_raw = data.get("items", [])
    if not isinstance(items_raw, list):
        items_raw = []

    processed_items: list[LPOLineItem] = []
    for item_data in items_raw:
        if not isinstance(item_data, dict):
            continue
        uom_raw = item_data.pop("uom_raw", None)
        if isinstance(uom_raw, str) and uom_raw.strip():
            uom_raw = uom_raw.strip()
            item_data["packaging"] = normalize_packaging_uom(uom_raw)
            item_data["buying_unit"] = canonical_buying_unit_from_uom(uom_raw)
        elif item_data.get("packaging"):
            item_data["packaging"] = normalize_packaging_uom(item_data["packaging"])
        if item_data.get("buying_unit") and isinstance(item_data["buying_unit"], str):
            buying_unit = item_data["buying_unit"].strip()
            item_data["buying_unit"] = canonical_buying_unit_from_uom(
                f"{buying_unit}/" if "/" not in buying_unit else buying_unit
            )
        if item_data.get("commodity"):
            item_data["commodity"] = normalize_commodity(item_data["commodity"])
        try:
            processed_items.append(LPOLineItem(**item_data))
        except Exception:
            continue
    data["items"] = processed_items

    try:
        return LPOInvoiceResult(**data)
    except Exception:
        return LPOInvoiceResult()


def parse_rice_quality_response(content: str) -> dict[str, Any]:
    data = parse_json_from_content(content)
    if data is None:
        raise ValueError("Rice Quality Report extraction did not return valid JSON object")
    return data


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def parse_shipment_classification_response(content: str) -> dict[str, Any]:
    raw = parse_json_from_content(content)
    if not raw:
        return {
            "is_valid_document": False,
            "has_lpo": False,
            "has_ricequality_doc": False,
            "reason": "Classification response could not be parsed as JSON.",
        }
    out = {
        "is_valid_document": _coerce_bool(raw.get("is_valid_document")),
        "has_lpo": _coerce_bool(raw.get("has_lpo")),
        "has_ricequality_doc": _coerce_bool(raw.get("has_ricequality_doc")),
        "reason": raw.get("reason") if isinstance(raw.get("reason"), str) else "",
    }
    for key, value in raw.items():
        if key not in out:
            out[key] = value
    return out


def validation_error_summary(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg', 'validation error')}")
    return "; ".join(parts) if parts else "Schema validation failed."


def parse_packaging_list_response(
    content: str,
) -> tuple[Optional[PackagingListExtraction], Optional[str]]:
    data = parse_json_from_content(content)
    if data is None:
        return None, "Model output was empty or not valid JSON."
    try:
        return PackagingListExtraction.model_validate(data), None
    except ValidationError as exc:
        return None, validation_error_summary(exc)


def _coerce_legacy_bill_no_fields(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    bl_number = out.get("bl_number")
    legacy = out.get("bill_no")
    bl_empty = bl_number is None or (isinstance(bl_number, str) and not bl_number.strip())
    if bl_empty and legacy is not None:
        if isinstance(legacy, str):
            out["bl_number"] = legacy.strip() or None
        else:
            out["bl_number"] = str(legacy).strip() or None
    return out


def parse_bill_structured_response(
    content: str,
) -> tuple[Optional[BillOfLadingStructuredExtraction], Optional[str]]:
    data = parse_json_from_content(content)
    if data is None:
        return None, "Model output was empty or not valid JSON."
    try:
        return (
            BillOfLadingStructuredExtraction.model_validate(
                _coerce_legacy_bill_no_fields(data)
            ),
            None,
        )
    except ValidationError as exc:
        return None, validation_error_summary(exc)


def build_bill_no_api_response(
    extraction: Optional[BillOfLadingStructuredExtraction],
    metadata: ExtractionMetadata,
) -> BillNoExtractionResponse:
    if extraction is None:
        return BillNoExtractionResponse(containers=[], metadata=metadata)
    return BillNoExtractionResponse(
        bill_no=extraction.bl_number,
        shipped_on_board_date=extraction.shipped_on_board_date,
        port_of_loading=extraction.port_of_loading,
        port_of_discharge=extraction.port_of_discharge,
        number_of_containers=extraction.number_of_containers,
        number_of_bags=extraction.number_of_bags,
        quantity_mt=extraction.quantity_mt,
        shipping_line=extraction.shipping_line,
        free_detention_days=extraction.free_detention_days,
        maximum_detention_days=extraction.maximum_detention_days,
        freight_prepaid=extraction.freight_prepaid,
        vessel_name=extraction.vessel_name,
        invoice_number=extraction.invoice_number,
        containers=list(extraction.containers),
        metadata=metadata,
    )


def parse_stock_sheet_signature(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(strip_json_from_llm_text(content))
    except Exception:
        return {
            "prepared_by_signed": False,
            "reviewed_by_signed": False,
            "approved_by_signed": False,
            "all_signed": False,
            "notes": "Unable to parse signature response",
        }
    return parsed if isinstance(parsed, dict) else {}


def parse_stock_sheet_orientation(content: str) -> int:
    try:
        parsed = json.loads(strip_json_from_llm_text(content))
        angle = int(parsed.get("rotation_degrees_needed", 0))
        return angle if angle in (0, 90, 180, 270) else 0
    except Exception:
        return 0


def sanitize_cleaned_rows(
    parsed_content: str,
    *,
    fallback_headers: list[str],
    fallback_rows: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        cleaned = json.loads(parsed_content)
    except json.JSONDecodeError:
        return fallback_headers, fallback_rows
    if not isinstance(cleaned, dict):
        return fallback_headers, fallback_rows
    headers = cleaned.get("headers")
    rows = cleaned.get("rows")
    parsed_headers = fallback_headers
    if isinstance(headers, list) and len(headers) == len(fallback_headers):
        parsed_headers = [str(header) for header in headers]
    if not isinstance(rows, list) or len(rows) != len(fallback_rows):
        return parsed_headers, fallback_rows
    sanitized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        sanitized.append(
            {
                str(key): _coerce_cleaned_value(value)
                for key, value in row.items()
            }
        )
    return parsed_headers, sanitized or fallback_rows


def _coerce_cleaned_value(value: Any) -> int | float | str | None:
    if value is None or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)
