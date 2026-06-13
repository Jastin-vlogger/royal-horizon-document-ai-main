"""BOE extraction parsing and normalization utilities."""

import json
import re
import io
from datetime import datetime
from typing import Any, Iterable, Optional

from PIL import Image
from pydantic import ValidationError

from src.models.api.boe import BoeExtractData, BoeExtractResponse, BoeLLMOutput
from src.models.api.response import ExtractionMetadata

_CONTAINER_LABEL_RE = re.compile(r"^.*?container\s*nos?\s*:?", re.IGNORECASE)
_CONTAINER_SHAPED_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z]{4}(?:\s*[A-Za-z0-9]){7})(?![A-Za-z0-9])"
)
_CONTAINER_COMPACT_RE = re.compile(r"^[A-Za-z]{4}[A-Za-z0-9]{7}$")
_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?!\d)")
_BOE_CROP_REGIONS = (
    (0.15, 0.06, 0.84, 0.16),
    (0.03, 0.27, 0.36, 0.41),
)


def _strip_json_from_llm_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
        return text.strip()
    match = re.search(r"\{[\s\S]*\}\s*$", text)
    if match:
        return match.group(0).strip()
    return text


def _clean_container_token(value: str) -> Optional[str]:
    token = value.strip().strip(" ,;:.|")
    if not token:
        return None

    token = _CONTAINER_LABEL_RE.sub("", token).strip().strip(" ,;:.|")
    if not token:
        return None

    compact_whitespace = re.sub(r"\s+", "", token)
    if _CONTAINER_COMPACT_RE.fullmatch(compact_whitespace):
        return compact_whitespace

    return token if _CONTAINER_COMPACT_RE.fullmatch(token) else None


def _container_candidates_from_text(value: str) -> list[str]:
    candidates: list[str] = []
    for match in _CONTAINER_SHAPED_RE.finditer(value):
        cleaned = _clean_container_token(match.group(1))
        if cleaned:
            candidates.append(cleaned)

    for segment in re.split(r"[,;\r\n]+", value):
        cleaned = _clean_container_token(segment)
        if cleaned:
            candidates.append(cleaned)

    return candidates


def normalize_container_values(value: Any) -> list[str]:
    """Return de-duplicated, trimmed container numbers without inventing characters."""

    if value is None:
        return []
    raw_values: Iterable[Any]
    if isinstance(value, list):
        raw_values = value
    elif isinstance(value, tuple):
        raw_values = value
    else:
        raw_values = [value]

    seen: set[str] = set()
    containers: list[str] = []
    for raw_value in raw_values:
        if raw_value is None:
            continue
        for candidate in _container_candidates_from_text(str(raw_value)):
            dedupe_key = re.sub(r"\s+", "", candidate).upper()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            containers.append(candidate)
    return containers


def normalize_boe_date(value: Optional[str]) -> Optional[str]:
    """Normalize DD/MM/YYYY or DD-MM-YYYY to DD/MM/YYYY."""

    if value is None:
        return None
    text = value.strip()
    if not text or text.lower() == "null":
        return None
    match = _DATE_RE.search(text)
    if not match:
        return None

    day, month, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    try:
        parsed = datetime(year=year, month=month, day=day)
    except ValueError:
        return None
    return parsed.strftime("%d/%m/%Y")


def parse_boe_response(
    content: str,
    metadata: ExtractionMetadata,
) -> BoeExtractResponse:
    """Parse and normalize model JSON into the BOE API response contract."""

    stripped = _strip_json_from_llm_text(content)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM output is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("LLM JSON root must be an object")

    try:
        parsed = BoeLLMOutput.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"LLM JSON failed schema validation: {exc}") from exc

    return BoeExtractResponse(
        success=True,
        data=BoeExtractData(
            containers=normalize_container_values(parsed.containers),
            date=normalize_boe_date(parsed.date),
        ),
        metadata=metadata,
    )


def build_boe_vision_images(page_images: list[bytes]) -> list[bytes]:
    """Return full BOE pages plus focused zoom crops for fragile fields."""

    images: list[bytes] = []
    for page_image in page_images:
        images.append(page_image)
        try:
            image = Image.open(io.BytesIO(page_image))
            width, height = image.size
            for left, top, right, bottom in _BOE_CROP_REGIONS:
                crop = image.crop(
                    (
                        int(width * left),
                        int(height * top),
                        int(width * right),
                        int(height * bottom),
                    )
                )
                crop = crop.resize(
                    (crop.width * 3, crop.height * 3),
                    Image.Resampling.LANCZOS,
                )
                if crop.mode in ("RGBA", "P"):
                    crop = crop.convert("RGB")
                buffer = io.BytesIO()
                crop.save(buffer, format="PNG")
                images.append(buffer.getvalue())
        except Exception:
            continue
    return images
