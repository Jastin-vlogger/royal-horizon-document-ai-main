"""Notebook-aligned table normalization for stock-sheet extraction."""

from collections.abc import Mapping
from difflib import SequenceMatcher
from typing import Any

from src.processing.stock_sheet.constants import (
    END_TOKENS,
    NULL_CELL_TOKENS,
    START_TOKENS,
    CANONICAL_COLUMNS,
    empty_canonical_row,
    enforce_canonical_row,
    normalize_column_token,
    to_canonical_column,
)

MERGE_RATIO = 0.75
ANCHOR_COLUMNS: tuple[tuple[int, str], ...] = (
    (1, "Abu Dhabi Musaffah"),
    (2, "ALAin Mazyad"),
    (3, "AlAin Maryad (Strategic)"),
    (4, "AlAin Mazyad (Acc)"),
    (9, "Mazyad (6 months contr)"),
    (19, "DIC9 (Strategic)"),
    (21, "DIC11"),
    (22, "Sharja Sajaa Block B"),
    (23, "Sharja Sajaa Block C"),
    (24, "Total Bags"),
)


def _headers_are_similar(headers_a: list[str], headers_b: list[str]) -> bool:
    if not headers_a or not headers_b:
        return False
    compared = min(len(headers_a), len(headers_b))
    matches = sum(
        normalize_column_token(left) == normalize_column_token(right)
        for left, right in zip(headers_a[:compared], headers_b[:compared])
    )
    return matches / max(len(headers_a), len(headers_b), 1) >= MERGE_RATIO


def _find_bounds(headers: list[str]) -> tuple[int, int]:
    start = None
    end = None
    for index, header in enumerate(headers):
        normalized = (header or "").strip().lower()
        if start is None and any(normalized == token or normalized.startswith(f"{token} ") for token in START_TOKENS):
            start = index
        if any(token in normalized for token in END_TOKENS):
            end = index
    if start is None or end is None or start > end:
        raise ValueError(f"Unit/Total Bags columns not found in headers: {headers}")
    return start, end


def _header_similarity(raw_header: str, canonical_header: str) -> float:
    return SequenceMatcher(
        None,
        normalize_column_token(raw_header),
        normalize_column_token(canonical_header),
    ).ratio()


def _build_anchor_mapping(headers: list[str]) -> dict[int, int]:
    anchor_mapping: dict[int, int] = {}
    previous_index = -1

    for canonical_index, canonical_header in ANCHOR_COLUMNS:
        best_score = -1.0
        best_index: int | None = None
        for index in range(previous_index + 1, len(headers)):
            score = _header_similarity(headers[index], canonical_header)
            if score > best_score:
                best_score = score
                best_index = index
        if best_index is None:
            raise ValueError(f"Unable to align stock-sheet headers: {headers}")
        anchor_mapping[best_index] = canonical_index
        previous_index = best_index

    first_anchor_index = min(anchor_mapping)
    if first_anchor_index <= 0:
        raise ValueError(f"Unable to infer Unit column from headers: {headers}")
    anchor_mapping[first_anchor_index - 1] = 0
    return anchor_mapping


def _build_header_mapping(headers: list[str]) -> dict[int, str]:
    try:
        anchor_mapping = _build_anchor_mapping(headers)
    except ValueError:
        start_index, end_index = _find_bounds(headers)
        return {
            index: canonical
            for index in range(start_index, end_index + 1)
            if (canonical := to_canonical_column(headers[index])) is not None
        }

    ordered_anchors = sorted(anchor_mapping.items())
    mapping: dict[int, str] = {}
    for (raw_start, canonical_start), (raw_end, canonical_end) in zip(ordered_anchors, ordered_anchors[1:]):
        mapping[raw_start] = CANONICAL_COLUMNS[canonical_start]
        for raw_index, canonical_index in zip(
            range(raw_start + 1, raw_end),
            range(canonical_start + 1, canonical_end),
        ):
            mapping[raw_index] = CANONICAL_COLUMNS[canonical_index]
    last_raw_index, last_canonical_index = ordered_anchors[-1]
    mapping[last_raw_index] = CANONICAL_COLUMNS[last_canonical_index]
    return mapping


def _normalize_cell(value: Any) -> int | float | str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in NULL_CELL_TOKENS:
        return None
    compact = text.replace(",", "").replace(" ", "")
    try:
        number = float(compact)
    except ValueError:
        return text
    return int(number) if number.is_integer() else number


def _build_row_dict(headers: list[str], row_values: list[Any]) -> dict[str, Any]:
    padded_values = list(row_values[: len(headers)])
    padded_values.extend([None] * max(0, len(headers) - len(padded_values)))
    return {headers[index]: padded_values[index] for index in range(len(headers))}


def parse_stock_table(raw_tables: list[list[list[str]]]) -> tuple[list[str], list[dict[str, Any]]]:
    """Merge Textract tables, slice stock-sheet columns, and normalize cell values."""
    merged_rows: list[list[Any]] = []
    headers: list[str] | None = None

    for table in raw_tables:
        if not table or not table[0]:
            continue

        table_headers = [str(cell).strip() for cell in table[0]]
        data_rows = table[1:]

        if headers is None:
            headers = table_headers
        elif not _headers_are_similar(table_headers, headers) and len(table_headers) > len(headers):
            headers = table_headers

        for row in data_rows:
            padded_values = list(row[: len(headers)])
            padded_values.extend([None] * max(0, len(headers) - len(padded_values)))
            merged_rows.append(padded_values)

    if headers is None:
        raise RuntimeError("No tables found in Textract output.")

    header_mapping = _build_header_mapping(headers)

    normalized_rows: list[dict[str, Any]] = []
    for row_values in merged_rows:
        row = empty_canonical_row()
        for raw_index, canonical_header in header_mapping.items():
            row[canonical_header] = _normalize_cell(row_values[raw_index] if raw_index < len(row_values) else None)
        if not any(str(value).strip() for value in row.values() if value is not None):
            continue
        normalized_rows.append(enforce_canonical_row(row))

    return CANONICAL_COLUMNS, normalized_rows


def map_rows_to_canonical(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Re-key OCR rows to the canonical stock-sheet schema."""
    canonical_rows: list[dict[str, Any]] = []
    for row in rows:
        remapped = empty_canonical_row()
        for key, value in row.items():
            canonical_key = to_canonical_column(str(key))
            if canonical_key:
                remapped[canonical_key] = value
        canonical_rows.append(enforce_canonical_row(remapped))
    return canonical_rows
