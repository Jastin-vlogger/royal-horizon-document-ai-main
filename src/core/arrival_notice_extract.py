"""Arrival notice extraction: multi-page PDF or image → vision LLM → validated JSON."""

import io
import json
import re
from typing import List

from PIL import Image
from pdf2image import convert_from_bytes
from pydantic import ValidationError

from src.core.document_processor import detect_file_type, is_image, is_pdf
from src.core.llm import invoke_multi_image_vision_extraction
from src.prompts.arrival_notice import arrival_notice_system_prompt
from src.schemas.arrival_notice import (
    ArrivalNoticeExtractResponse,
    ArrivalNoticeLLMOutput,
)

USER_MESSAGE_ARRIVAL_NOTICE = "Extract the two fields from these shipping document images and Return only the JSON object as instructed"

_ARRIVAL_ALLOWED = {"pdf", "image"}


def _pil_image_to_png_bytes(pil_img: Image.Image) -> bytes:
    if pil_img.mode in ("RGBA", "P"):
        pil_img = pil_img.convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


def upload_to_png_pages(content: bytes, filename: str) -> List[bytes]:
    """
    PDF → all pages as PNG bytes; image → single PNG (RGB).
    Mirrors experiments/features.ipynb (pdf2image for PDF, one image per page).
    """
    if is_pdf(filename):
        pages = convert_from_bytes(content, dpi=150)
        if not pages:
            raise ValueError("PDF has no readable pages")
        return [_pil_image_to_png_bytes(p) for p in pages]
    if is_image(filename):
        pil_img = Image.open(io.BytesIO(content))
        return [_pil_image_to_png_bytes(pil_img)]
    raise ValueError("File must be PDF or supported image (jpg, jpeg, png)")


def _strip_json_from_llm_text(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```\s*$", "", s)
        return s.strip()
    m = re.search(r"\{[\s\S]*\}\s*$", s)
    if m:
        return m.group(0).strip()
    return s


def parse_arrival_notice_llm_json(content: str) -> ArrivalNoticeLLMOutput:
    stripped = _strip_json_from_llm_text(content)
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM output is not valid JSON: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError("LLM JSON root must be an object")
    try:
        return ArrivalNoticeLLMOutput.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"LLM JSON failed schema validation: {e}") from e


async def extract_arrival_notice_from_pages(
    png_pages: List[bytes],
) -> ArrivalNoticeExtractResponse:
    """
    Run one vision call with all pages. Raises ValueError on bad model output.
    """
    if not png_pages:
        raise ValueError("At least one page image is required")

    system = arrival_notice_system_prompt.strip()
    if not system:
        raise RuntimeError(
            "arrival_notice_system_prompt is empty; set it in src/prompts/arrival_notice.py"
        )

    raw_text, meta = await invoke_multi_image_vision_extraction(
        system_prompt=system,
        image_bytes_list=png_pages,
        user_text=USER_MESSAGE_ARRIVAL_NOTICE,
    )

    parsed = parse_arrival_notice_llm_json(raw_text)
    return ArrivalNoticeExtractResponse(
        arrival_on=parsed.arrival_on,
        free_retension_days=parsed.free_retension_days,
        metadata=meta,
    )


def validate_upload_type(filename: str) -> None:
    if detect_file_type(filename) not in _ARRIVAL_ALLOWED:
        raise ValueError(
            f"File must be PDF or image (jpg, jpeg, png). Got: {filename or 'unknown'}"
        )
