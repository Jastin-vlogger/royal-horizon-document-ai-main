"""Business logic for LPO document extraction: prompt + LLM + parse."""

import json
import re
from typing import Optional, Tuple

from src.core.llm import invoke_vision_extraction
from src.prompts.lpo_invoice import get_lpo_invoice_system_prompt
from src.schemas.response import ExtractionMetadata, LPOInvoiceResult
from src.config.logger import logger


def normalize_packaging_uom(value: Optional[str]) -> Optional[str]:
    """
    Normalize packaging UOM to format like 1X10KG, 4X10KG.
    Input: "10kg", "1x10kg", "BAG/1x10kg", "4*10 kg"
    Output: "1X10KG", "4X10KG", "10KG"
    """
    if value is None or not isinstance(value, str) or not value.strip():
        return value if value is None else None
    s = value.strip().upper()
    # Remove prefix like "BAG/"
    s = re.sub(r"^[A-Z/]+\s*", "", s)
    # NxM or N*M pattern -> NXMKG
    mult_match = re.search(r"(\d+)\s*[xX*]\s*(\d+)\s*(?:kg|KG)?", s)
    if mult_match:
        n, m = int(mult_match.group(1)), int(mult_match.group(2))
        return f"{n}X{m}KG"
    # Single number + optional KG -> NKG
    single_match = re.search(r"(\d+\.?\d*)\s*(?:kg|KG)?", s)
    if single_match:
        return f"{int(float(single_match.group(1)))}KG"
    return value.strip() or value


def _parse_json_from_content(content: str) -> Optional[dict]:
    """Extract JSON object from model output (may be wrapped in markdown)."""
    if not content or not content.strip():
        return None
    text = content.strip()
    # Remove optional markdown code block
    if "```json" in text:
        text = re.sub(r"^.*?```json\s*", "", text, flags=re.DOTALL)
    if "```" in text:
        text = re.sub(r"```\s*.*$", "", text, flags=re.DOTALL)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def extract_lpo_invoice(
    image_bytes: bytes,
) -> Tuple[Optional[LPOInvoiceResult], Optional[ExtractionMetadata]]:
    """
    Run LPO extraction on the given image bytes.
    Returns (parsed result, metadata). Result is None if parsing failed.
    """
    logger.debug("Extracting LPO Invoice")
    system_prompt = get_lpo_invoice_system_prompt()
    content, metadata = await invoke_vision_extraction(
        system_prompt=system_prompt,
        image_bytes=image_bytes,
        user_text="Extract the required fields and return only valid JSON.",
    )
    logger.debug(f"LPO Invoice Extracted: {content}")
    data = _parse_json_from_content(content)
    if data is None:
        logger.warning("LPO Invoice Parsed Failed, returning None")
        return None, metadata
    # If model returned a list (multiple line items), take first and flatten
    if isinstance(data, list) and len(data) > 0:
        data = data[0] if isinstance(data[0], dict) else data

    # Post-process: normalize packaging UOM to 1X10KG format
    if data.get("packaging"):
        data["packaging"] = normalize_packaging_uom(data["packaging"])

    try:
        result = LPOInvoiceResult(**data)
    except Exception:
        logger.warning("LPO Invoice Parsed Failed, returning None")
        result = LPOInvoiceResult()
    logger.debug(f"LPO Invoice Result: {result}")
    return result, metadata
