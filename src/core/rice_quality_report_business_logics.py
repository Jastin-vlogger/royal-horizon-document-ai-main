"""Rice Quality Report extraction: user-message-only vision + JSON parse."""

import json
import re
from typing import Any, Tuple

from src.config.logger import logger
from src.core.llm import invoke_vision_extraction
from src.prompts.rice_quality_report import RICE_QUALITY_SYSTEM_PROMPT
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


async def extract_rice_quality_report(
    image_bytes: bytes,
) -> Tuple[dict[str, Any], ExtractionMetadata]:
    """
    Extract structured rice quality fields from a single page image.
    Raises ValueError if the model output is not a JSON object.
    """
    content, metadata = await invoke_vision_extraction(
        system_prompt=RICE_QUALITY_SYSTEM_PROMPT, 
        image_bytes=image_bytes, 
        user_text="Extract the required fields and return only valid JSON from the rice quality report."
    )

    data = _parse_json_from_content(content)
    if data is None:
        logger.warning("Rice quality report JSON parse failed")
        raise ValueError("Rice Quality Report extraction did not return valid JSON object")

    return data, metadata
