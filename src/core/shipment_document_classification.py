"""Multi-image shipment document classification (LPO, Performa, Rice Quality)."""

import json
import re
from typing import Any, Tuple

from src.config.logger import logger
from src.core.llm import invoke_multi_image_vision_extraction
from src.prompts.shipment_classification import CLASSIFICATION_SYSTEM_PROMPT
from src.schemas.response import ExtractionMetadata


def _parse_json_from_content(content: str) -> dict[str, Any] | None:
    if not content or not content.strip():
        return None
    text = content.strip()
    if "```json" in text:
        text = re.sub(r"^.*?```json\s*", "", text, flags=re.DOTALL)
    if "```" in text:
        text = re.sub(r"```\s*.*$", "", text, flags=re.DOTALL)
    text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def _normalize_classification_dict(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Ensure required keys exist; treat incomplete JSON as invalid."""
    if not raw:
        return {
            "is_valid_document": False,
            "has_lpo": False,
            "has_performa_invoice": False,
            "has_ricequality_doc": False,
            "reason": "Classification response could not be parsed as JSON.",
        }
    out = {
        "is_valid_document": _coerce_bool(raw.get("is_valid_document")),
        "has_lpo": _coerce_bool(raw.get("has_lpo")),
        "has_performa_invoice": _coerce_bool(raw.get("has_performa_invoice")),
        "has_ricequality_doc": _coerce_bool(raw.get("has_ricequality_doc")),
        "reason": raw.get("reason") if isinstance(raw.get("reason"), str) else "",
    }
    for key, val in raw.items():
        if key not in out:
            out[key] = val
    return out


async def classify_shipment_documents(
    image_bytes_ordered: list[bytes],
) -> Tuple[dict[str, Any], ExtractionMetadata]:
    """
    Run classification on three images: LPO, Performa Invoice, Rice Quality Report.
    Returns normalized dict (always includes the five contract fields) and LLM metadata.
    """
    if len(image_bytes_ordered) != 3:
        raise ValueError("classify_shipment_documents requires exactly three images")

    content, metadata = await invoke_multi_image_vision_extraction(
        system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
        image_bytes_list=image_bytes_ordered,
        user_text="Analyze these three images. Classify these document"
    )
    logger.debug(f"Shipment classification raw: {content[:500]!r}...")

    parsed = _parse_json_from_content(content)
    normalized = _normalize_classification_dict(parsed)
    if parsed is None:
        logger.warning("Shipment classification JSON parse failed")

    return normalized, metadata
