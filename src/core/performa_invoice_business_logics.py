"""Business logic for Performa Invoice extraction: prompt + LLM + parse."""

import json
import re
from typing import Any, List, Optional, Tuple

from src.core.llm import invoke_vision_extraction
from src.prompts.performa_invoice import get_performa_invoice_system_prompt
from src.schemas.response import ExtractionMetadata, PerformaInvoiceResult
from src.config.logger import logger


def _normalize_inco_terms(value: Optional[str]) -> Optional[str]:
    """Normalize C&F variants (C & F, C AND F) to C&F."""
    if not value or not isinstance(value, str):
        return value
    s = value.strip().upper()
    normalized = re.sub(r"\s*&\s*", "&", s)
    normalized = re.sub(r"\s+AND\s+", "&", normalized)
    if normalized == "C&F":
        return "C&F"
    return value.strip()


def _extract_container_size_from_packaging(packaging: Optional[str]) -> Optional[int]:
    """
    Extract master/outer bag weight in KG from packaging text.
    Examples: "20KG POUCH BAG..." -> 20; "4*10 kg ... IN 40KG MASTER PP BAGS" -> 40.
    """
    if not packaging or not isinstance(packaging, str):
        return None
    text = packaging.strip().upper()
    # Prefer patterns like "XKG MASTER", "IN XKG", or standalone XKG (take largest)
    patterns = [
        r"IN\s+(\d+)\s*KG",  # "IN 40KG MASTER"
        r"(\d+)\s*KG\s*(?:MASTER|OUTER|POUCH|BAG)",  # "40KG MASTER", "20KG POUCH"
        r"(\d+)\s*KG",  # any "XKG"
    ]
    candidates: List[int] = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            try:
                candidates.append(int(m.group(1)))
            except (ValueError, IndexError):
                pass
    # Also handle "4*10" style - take the product as inner, look for master
    mult_match = re.search(r"(\d+)\s*[*xX]\s*(\d+)\s*(?:kg|KG)?", text)
    if mult_match:
        inner = int(mult_match.group(1)) * int(mult_match.group(2))
        candidates.append(inner)
    if not candidates:
        return None
    return max(candidates)


def _parse_json_from_content(content: str) -> Optional[dict]:
    """Extract JSON object from model output (may be wrapped in markdown)."""
    if not content or not content.strip():
        return None
    text = content.strip()
    if "```json" in text:
        text = re.sub(r"^.*?```json\s*", "", text, flags=re.DOTALL)
    if "```" in text:
        text = re.sub(r"```\s*.*$", "", text, flags=re.DOTALL)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def extract_performa_invoice(
    image_bytes: bytes,
    inco_terms_list: List[str],
    suppliers: List[str],
) -> Tuple[Optional[PerformaInvoiceResult], Optional[ExtractionMetadata]]:
    """
    Run Performa Invoice extraction on the given image bytes.
    inco_terms_list and suppliers are injected into the prompt for validation/matching.
    Returns (parsed result, metadata). Result is None if parsing failed.
    """
    logger.debug("Extracting Performa Invoice")
    system_prompt = get_performa_invoice_system_prompt(
        inco_terms_list=inco_terms_list,
        suppliers=suppliers,
    )
    content, metadata = await invoke_vision_extraction(
        system_prompt=system_prompt,
        image_bytes=image_bytes,
        user_text="Extract the required fields and return only valid JSON.",
    )
    logger.debug(f"Performa Invoice Extracted: {content}")
    data = _parse_json_from_content(content)
    if data is None:
        logger.warning("Performa Invoice Parsed Failed, returning None")
        return None, metadata

    # Post-process: normalize inco_terms (C & F -> C&F)
    if data.get("inco_terms"):
        data["inco_terms"] = _normalize_inco_terms(data["inco_terms"])

    # Ensure container_size is int (LLM may return string)
    if data.get("container_size") is not None:
        try:
            data["container_size"] = int(data["container_size"])
        except (TypeError, ValueError):
            data["container_size"] = None

    try:
        result = PerformaInvoiceResult(**data)
    except Exception:
        logger.warning("Performa Invoice Parsed Failed, returning None")
        result = PerformaInvoiceResult()
    logger.debug(f"Performa Invoice Result: {result}")
    return result, metadata
