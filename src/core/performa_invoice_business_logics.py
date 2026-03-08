"""Business logic for Performa Invoice extraction: prompt + LLM + parse."""

import json
import re
from typing import List, Optional, Tuple

from src.core.llm import invoke_vision_extraction
from src.prompts.performa_invoice import get_performa_invoice_system_prompt
from src.schemas.response import ExtractionMetadata, PerformaInvoiceResult


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
    system_prompt = get_performa_invoice_system_prompt(
        inco_terms_list=inco_terms_list,
        suppliers=suppliers,
    )
    content, metadata = await invoke_vision_extraction(
        system_prompt=system_prompt,
        image_bytes=image_bytes,
        user_text="Extract the required fields and return only valid JSON.",
    )
    data = _parse_json_from_content(content)
    if data is None:
        return None, metadata
    try:
        result = PerformaInvoiceResult(**data)
    except Exception:
        result = PerformaInvoiceResult()
    return result, metadata
