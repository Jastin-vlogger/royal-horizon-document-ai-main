"""Focused total-row repair for stock-sheet extraction."""

from io import BytesIO
from typing import Any

import fitz
from PIL import Image

from src.core.stock_sheet.constants import CANONICAL_COLUMNS, empty_canonical_row, enforce_canonical_row
from src.core.stock_sheet.ocr_textract import TextractTableExtractor

TOTAL_ROW_CROP_TOP = 0.081
TOTAL_ROW_CROP_BOTTOM = 0.825
EARLY_CROP_LEFT = 0.342
EARLY_CROP_RIGHT = 0.608
TAIL_CROP_LEFT = 0.613
TAIL_CROP_RIGHT = 0.912
RENDER_SCALE = 2.5
UPSCALE_FACTOR = 4

EARLY_CANONICAL_HEADERS: tuple[str, ...] = (
    "Unit",
    "Abu Dhabi Musaffah",
    "ALAin Mazyad",
    "AlAin Maryad (Strategic)",
    "AlAin Mazyad (Acc)",
    "Al Aln Sanaya B Block - A",
    "Al Aln Sanaya B Block - B",
    "Al Aln Sanaya B Block - C",
    "Al Aln Sanaya B Block - D",
    "Mazyad (6 months contr)",
    "DIC1",
    "DIC2",
    "DIC3",
    "DIC4",
)

TAIL_CANONICAL_HEADERS: tuple[str, ...] = (
    "DIC5",
    "DIC6",
    "DIC7",
    "DIC8",
    "DIC9",
    "DIC9 (Strategic)",
    "DIC10",
    "DIC11",
    "Sharja Sajaa Block B",
    "Sharja Sajaa Block C",
    "Total Bags",
)


def _image_to_png_bytes(image: Image.Image) -> bytes:
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _render_first_page(content: bytes, file_type: str, rotation_angle: int) -> Image.Image:
    if file_type == "pdf":
        with fitz.open(stream=content, filetype="pdf") as doc:
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE), alpha=False)
            image = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
    else:
        image = Image.open(BytesIO(content)).convert("RGB")
        if image.width < 1800:
            upscale = max(1, int(1800 / max(image.width, 1)))
            image = image.resize((image.width * upscale, image.height * upscale))

    if rotation_angle:
        image = image.rotate(-rotation_angle, expand=True)
    return image


def _crop(image: Image.Image, left: float, right: float) -> bytes:
    width, height = image.size
    crop = image.crop(
        (
            int(width * left),
            int(height * TOTAL_ROW_CROP_TOP),
            int(width * right),
            int(height * TOTAL_ROW_CROP_BOTTOM),
        )
    )
    crop = crop.resize((crop.width * UPSCALE_FACTOR, crop.height * UPSCALE_FACTOR))
    return _image_to_png_bytes(crop)


def _to_value(cell: Any) -> int | float | str | None:
    if cell is None:
        return None
    text = str(cell).strip()
    if text in {"", "-", "--", ".", "—"}:
        return None
    compact = text.replace(",", "").replace(" ", "")
    try:
        number = float(compact)
    except ValueError:
        return text
    return int(number) if number.is_integer() else number


def _merge_crop_values(
    headers: list[str],
    row: list[str],
    canonical_headers: tuple[str, ...],
    *,
    row_offset: int,
    header_offset: int,
) -> dict[str, int | float | str | None]:
    merged: dict[str, int | float | str | None] = {}
    for index, canonical_header in enumerate(canonical_headers):
        header_index = header_offset + index
        row_index = row_offset + index
        if header_index >= len(headers) or row_index >= len(row):
            merged[canonical_header] = None
            continue
        merged[canonical_header] = _to_value(row[row_index])
    return merged


def _get_last_row(table: list[list[str]]) -> list[str]:
    for row in reversed(table):
        if any(str(cell).strip() for cell in row):
            return row
    return []


def repair_total_row_from_tables(
    early_table: list[list[str]],
    tail_table: list[list[str]],
) -> dict[str, int | float | str | None]:
    """Build a canonical Total Qty row from focused early/tail Textract tables."""
    total_row = empty_canonical_row()

    early_row = _get_last_row(early_table)
    tail_row = _get_last_row(tail_table)

    total_row.update(
        _merge_crop_values(
            early_table[0],
            early_row,
            EARLY_CANONICAL_HEADERS,
            row_offset=1,
            header_offset=1,
        )
    )
    total_row.update(
        _merge_crop_values(
            tail_table[0],
            tail_row,
            TAIL_CANONICAL_HEADERS,
            row_offset=0,
            header_offset=0,
        )
    )

    return enforce_canonical_row(total_row)


def maybe_repair_total_row(
    *,
    content: bytes,
    file_type: str,
    rotation_angle: int,
    raw_tables: list[list[list[str]]],
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Repair the final Total Qty row when the raw Textract tables clearly contain it."""
    if not rows or not raw_tables:
        return None

    last_raw_row = _get_last_row(raw_tables[-1])
    if not any("total" in str(cell).strip().lower() for cell in last_raw_row):
        return None

    page_image = _render_first_page(content, file_type, rotation_angle)
    extractor = TextractTableExtractor()
    early_tables = extractor.extract_tables(_crop(page_image, EARLY_CROP_LEFT, EARLY_CROP_RIGHT))
    tail_tables = extractor.extract_tables(_crop(page_image, TAIL_CROP_LEFT, TAIL_CROP_RIGHT))
    if not early_tables or not tail_tables:
        return None

    return repair_total_row_from_tables(early_tables[0], tail_tables[0])
