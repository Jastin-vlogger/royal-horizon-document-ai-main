"""Vision checks for stock-sheet documents (signature + orientation)."""

import json
import re

from PIL import Image

from src.core.llm import invoke_vision_extraction
from src.prompts.stock_sheet import (
    STOCK_SHEET_ORIENTATION_PROMPT,
    STOCK_SHEET_SIGNATURE_PROMPT,
)
from src.schemas.response import ExtractionMetadata


def _strip_json_fence(text: str) -> str:
    return re.sub(r"```(?:json)?\s*", "", text).strip().strip("`")


def _image_to_png_bytes(img: Image.Image) -> bytes:
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    from io import BytesIO

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def verify_signatures(page_png_bytes: bytes) -> tuple[dict, ExtractionMetadata]:
    """Verify Prepared/Reviewed/Approved signatures on first page."""
    raw, meta = await invoke_vision_extraction(
        system_prompt=STOCK_SHEET_SIGNATURE_PROMPT,
        image_bytes=page_png_bytes,
        user_text="Check all three signature fields and return JSON.",
    )
    try:
        parsed = json.loads(_strip_json_fence(raw))
    except Exception:
        parsed = {
            "prepared_by_signed": False,
            "reviewed_by_signed": False,
            "approved_by_signed": False,
            "all_signed": False,
            "notes": "Unable to parse signature response",
        }
    return parsed, meta


async def detect_orientation(page_png_bytes: bytes) -> tuple[int, ExtractionMetadata]:
    """Detect clockwise rotation angle for one page."""
    raw, meta = await invoke_vision_extraction(
        system_prompt=STOCK_SHEET_ORIENTATION_PROMPT,
        image_bytes=page_png_bytes,
        user_text="Analyze the orientation and return the JSON.",
    )
    angle = 0
    try:
        parsed = json.loads(_strip_json_fence(raw))
        maybe_angle = int(parsed.get("rotation_degrees_needed", 0))
        if maybe_angle in (0, 90, 180, 270):
            angle = maybe_angle
    except Exception:
        angle = 0
    return angle, meta
