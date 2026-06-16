"""DPW cargo receipt parsing, normalization, and image-prep utilities."""

import io
import json
import re
from datetime import datetime
from typing import Any, Iterable, Optional

from PIL import Image
from pydantic import ValidationError

from src.models.api.dpw_cargo import (
    DpwCargoContainer,
    DpwCargoContainerLLMOutput,
    DpwCargoExtractorResponse,
    DpwCargoLLMOutput,
)
from src.models.api.response import ExtractionMetadata

_CONTAINER_LABEL_RE = re.compile(r"^.*?\bcontainer\b\s*:?", re.IGNORECASE)
_CONTAINER_SHAPED_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z]{4}[\s-]*\d{6,7})(?![A-Za-z0-9])"
)
_CONTAINER_BLOCK_RE = re.compile(
    r"\bcontainer\s+([A-Za-z]{4}[\s-]*\d{6,7})(.*?)(?=\bcontainer\s+[A-Za-z]{4}[\s-]*\d{6,7}|$)",
    re.IGNORECASE | re.DOTALL,
)
_CONTAINER_COMPACT_RE = re.compile(r"^[A-Z]{4}\d{6,7}$")
_DATE_DMY_RE = re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?!\d)")
_DATE_ISO_RE = re.compile(r"(?<!\d)(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?!\d)")
_DATE_VALUE_RE = r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})"
_DATE_RANGE_RE = re.compile(
    rf"\bfrom\s+({_DATE_VALUE_RE})\s+to\s+({_DATE_VALUE_RE})",
    re.IGNORECASE,
)
_RECEIPT_LABEL_RE = re.compile(
    r"^(?:receipt\s*(?:no|number)?|bol\s*no|b/l\s*no|bl\s*no)\s*:?",
    re.IGNORECASE,
)
_DPW_HEADER_CROP_REGION = (0.03, 0.04, 0.97, 0.54)
_DPW_CONTAINER_CROP_REGION_FIRST = (0.03, 0.48, 0.48, 0.96)
_DPW_CONTAINER_CROP_REGION_CONTINUATION = (0.03, 0.02, 0.48, 0.96)


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

    compact = re.sub(r"[^A-Za-z0-9]", "", token).upper()
    if _CONTAINER_COMPACT_RE.fullmatch(compact):
        return compact
    return None


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


def _first_container_from_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    candidates = _container_candidates_from_text(str(value))
    return candidates[0] if candidates else None


def _date_range_from_text(value: str) -> tuple[Optional[str], Optional[str]]:
    match = _DATE_RANGE_RE.search(value)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _container_items_from_text(
    value: str,
) -> list[tuple[str, Optional[str], Optional[str]]]:
    items: list[tuple[str, Optional[str], Optional[str]]] = []
    for match in _CONTAINER_BLOCK_RE.finditer(value):
        container = _clean_container_token(match.group(1))
        if not container:
            continue
        from_value, to_value = _date_range_from_text(match.group(2))
        items.append((container, from_value, to_value))
    return items


def normalize_dpw_container_values(value: Any) -> list[str]:
    """Return unique DPW container references in first-seen order."""

    containers: list[str] = []
    for item in normalize_dpw_container_items(value):
        if item.container is not None:
            containers.append(item.container)
    return containers


def _format_date(year: int, month: int, day: int) -> Optional[str]:
    try:
        parsed = datetime(year=year, month=month, day=day)
    except ValueError:
        return None
    return parsed.strftime("%d/%m/%Y")


def normalize_dpw_date(value: Any) -> Optional[str]:
    """Normalize receipt date values to DD/MM/YYYY."""

    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None

    dmy = _DATE_DMY_RE.search(text)
    if dmy:
        day, month, year = (
            int(dmy.group(1)),
            int(dmy.group(2)),
            int(dmy.group(3)),
        )
        return _format_date(year, month, day)

    iso = _DATE_ISO_RE.search(text)
    if iso:
        year, month, day = (
            int(iso.group(1)),
            int(iso.group(2)),
            int(iso.group(3)),
        )
        return _format_date(year, month, day)
    return None


def normalize_receipt_no(value: Optional[str]) -> Optional[str]:
    """Normalize a receipt/BOL number without inventing missing characters."""

    if value is None:
        return None
    text = value.strip()
    if not text or text.lower() == "null":
        return None
    text = re.sub(r"\s+", " ", text)
    text = _RECEIPT_LABEL_RE.sub("", text).strip(" :")
    compact = re.sub(r"\s+", "", text).upper()
    return compact or None


def normalize_dpw_container_items(value: Any) -> list[DpwCargoContainer]:
    """Return unique DPW container rows with normalized storage date ranges."""

    if value is None:
        return []
    raw_values: Iterable[Any]
    if isinstance(value, list):
        raw_values = value
    elif isinstance(value, tuple):
        raw_values = value
    else:
        raw_values = [value]

    containers: list[DpwCargoContainer] = []
    index_by_container: dict[str, int] = {}

    def add_item(
        container_value: Optional[str],
        from_value: Any = None,
        to_value: Any = None,
    ) -> None:
        container = _first_container_from_value(container_value)
        if not container:
            return
        from_date = normalize_dpw_date(from_value)
        to_date = normalize_dpw_date(to_value)
        if container in index_by_container:
            existing = containers[index_by_container[container]]
            if existing.from_date is None and from_date is not None:
                existing.from_date = from_date
            if existing.to_date is None and to_date is not None:
                existing.to_date = to_date
            return
        index_by_container[container] = len(containers)
        containers.append(
            DpwCargoContainer(
                container=container,
                from_date=from_date,
                to_date=to_date,
            )
        )

    for raw_value in raw_values:
        if raw_value is None:
            continue
        if isinstance(raw_value, DpwCargoContainerLLMOutput):
            add_item(raw_value.container, raw_value.from_date, raw_value.to_date)
            continue
        if isinstance(raw_value, dict):
            add_item(
                raw_value.get("container")
                or raw_value.get("container_no")
                or raw_value.get("container_number"),
                raw_value.get("from")
                or raw_value.get("from_date")
                or raw_value.get("start_date")
                or raw_value.get("date_from"),
                raw_value.get("to")
                or raw_value.get("to_date")
                or raw_value.get("end_date")
                or raw_value.get("date_to"),
            )
            continue

        text = str(raw_value)
        text_items = _container_items_from_text(text)
        if text_items:
            for container, from_value, to_value in text_items:
                add_item(container, from_value, to_value)
            continue
        for candidate in _container_candidates_from_text(text):
            add_item(candidate)

    return containers


def parse_dpw_cargo_response(
    content: str,
    metadata: ExtractionMetadata,
    *,
    pages_processed: int,
) -> DpwCargoExtractorResponse:
    """Parse and normalize model JSON into the DPW API response contract."""

    stripped = _strip_json_from_llm_text(content)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM output is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("LLM JSON root must be an object")

    try:
        parsed = DpwCargoLLMOutput.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"LLM JSON failed schema validation: {exc}") from exc

    containers = normalize_dpw_container_items(parsed.containers)
    return DpwCargoExtractorResponse(
        date=normalize_dpw_date(parsed.date),
        containers=containers,
        total_containers=len(containers),
        pages_processed=pages_processed,
        receipt_no=normalize_receipt_no(parsed.receipt_no),
        metadata=metadata,
        error=None,
    )


def _crop_png_region(page_image: bytes, region: tuple[float, float, float, float]) -> bytes:
    image = Image.open(io.BytesIO(page_image))
    width, height = image.size
    left, top, right, bottom = region
    crop = image.crop(
        (
            int(width * left),
            int(height * top),
            int(width * right),
            int(height * bottom),
        )
    )
    if crop.mode in ("RGBA", "P"):
        crop = crop.convert("RGB")
    buffer = io.BytesIO()
    crop.save(buffer, format="PNG")
    return buffer.getvalue()


def build_dpw_cargo_vision_images(page_images: list[bytes]) -> list[bytes]:
    """Build compact crops for DPW headers and charge-description container rows."""

    if not page_images:
        return []

    images: list[bytes] = []
    try:
        images.append(_crop_png_region(page_images[0], _DPW_HEADER_CROP_REGION))
        for index, page_image in enumerate(page_images):
            region = (
                _DPW_CONTAINER_CROP_REGION_FIRST
                if index == 0
                else _DPW_CONTAINER_CROP_REGION_CONTINUATION
            )
            images.append(_crop_png_region(page_image, region))
    except Exception:
        return page_images
    return images or page_images
