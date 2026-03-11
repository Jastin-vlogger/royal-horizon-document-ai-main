"""Business logic for purchase_tracker B/L number extraction: prompt + LLM + parse."""

import json
import re
from typing import Optional, Tuple

from src.config.logger import logger
from src.core.llm import invoke_vision_extraction
from src.prompts.purchase_tracker_bill_no import (
    get_bill_no_system_prompt,
    get_bill_no_user_prompt,
)
from src.schemas.response import ExtractionMetadata


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


async def extract_bill_no(image_bytes: bytes) -> Tuple[Optional[str], Optional[ExtractionMetadata]]:
    """
    Extract the Bill of Lading number from the given document image bytes.
    Returns (bill_no string or None, metadata). bill_no is None if not found or parsing failed.
    """
    logger.debug("Extracting B/L number from purchase/shipping document")
    system_prompt = get_bill_no_system_prompt()
    user_prompt = get_bill_no_user_prompt()
    content, metadata = await invoke_vision_extraction(
        system_prompt=system_prompt,
        image_bytes=image_bytes,
        user_text=user_prompt,
    )
    logger.debug("B/L extraction raw content: %s", content[:200] if content else "")
    data = _parse_json_from_content(content)
    if data is None:
        logger.warning("B/L extraction parse failed, returning bill_no=None")
        return None, metadata
    bill_no = data.get("bill_no")
    if bill_no is not None and not isinstance(bill_no, str):
        bill_no = str(bill_no).strip() or None
    elif bill_no is not None:
        bill_no = bill_no.strip() or None
    logger.debug("B/L extraction result bill_no=%s", bill_no)
    return bill_no, metadata
