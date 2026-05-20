"""Constants and helpers used by stock-sheet extraction."""

from collections.abc import Mapping
from typing import Any
import re

CANONICAL_COLUMNS: list[str] = [
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
]

START_TOKENS: set[str] = {"unit"}
END_TOKENS: set[str] = {"total bags", "totalbags", "total bag"}
NULL_CELL_TOKENS: set[str] = {"", "-", "--", "—", "N/A", "null", "None", "*"}

_COLUMN_ALIASES_RAW: dict[str, str] = {
    "unit": "Unit",
    "abu dhabi musaffah": "Abu Dhabi Musaffah",
    "abudhabi musaffah": "Abu Dhabi Musaffah",
    "al ain mazyad": "ALAin Mazyad",
    "alain mazyad": "ALAin Mazyad",
    "al ain mazyad (strategic)": "AlAin Maryad (Strategic)",
    "alain mazyad (strategic)": "AlAin Maryad (Strategic)",
    "al ain mazyad (acc)": "AlAin Mazyad (Acc)",
    "alain mazyad (acc)": "AlAin Mazyad (Acc)",
    "al ain sanaya b block-a": "Al Aln Sanaya B Block - A",
    "al ain sanaya b block - a": "Al Aln Sanaya B Block - A",
    "al ain sanaya b block-b": "Al Aln Sanaya B Block - B",
    "al ain sanaya b block - b": "Al Aln Sanaya B Block - B",
    "al ain sanaya b block-c": "Al Aln Sanaya B Block - C",
    "al ain sanaya b block - c": "Al Aln Sanaya B Block - C",
    "al ain sanaya b block-d": "Al Aln Sanaya B Block - D",
    "al ain sanaya b block - d": "Al Aln Sanaya B Block - D",
    "mazyad (6 months contr.)": "Mazyad (6 months contr)",
    "mazyad (6 months contr)": "Mazyad (6 months contr)",
    "dic 1": "DIC1",
    "dic1": "DIC1",
    "dic 2": "DIC2",
    "dic2": "DIC2",
    "dic 3": "DIC3",
    "dic3": "DIC3",
    "dic 4": "DIC4",
    "dic4": "DIC4",
    "dic 5": "DIC5",
    "dic5": "DIC5",
    "dic 6": "DIC6",
    "dic6": "DIC6",
    "dic 7": "DIC7",
    "dic7": "DIC7",
    "dic 8": "DIC8",
    "dic8": "DIC8",
    "dic 9": "DIC9",
    "dic9": "DIC9",
    "dic 9 (strategic)": "DIC9 (Strategic)",
    "dic9 (strategic)": "DIC9 (Strategic)",
    "dic 10": "DIC10",
    "dic10": "DIC10",
    "dic 11": "DIC11",
    "dic11": "DIC11",
    "sharjah sajaa block b": "Sharja Sajaa Block B",
    "sharja sajaa block b": "Sharja Sajaa Block B",
    "sharjah sajaa block c": "Sharja Sajaa Block C",
    "sharja sajaa block c": "Sharja Sajaa Block C",
    "total bags": "Total Bags",
    "totalbags": "Total Bags",
    "total bag": "Total Bags",
}


def normalize_column_token(value: str) -> str:
    """Collapse OCR punctuation and whitespace so aliases match consistently."""
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


COLUMN_ALIASES: dict[str, str] = {
    normalize_column_token(key): value for key, value in _COLUMN_ALIASES_RAW.items()
}
CANONICAL_COLUMN_LOOKUP: dict[str, str] = {
    normalize_column_token(column): column for column in CANONICAL_COLUMNS
}
CANONICAL_COLUMN_LOOKUP.update(COLUMN_ALIASES)


def to_canonical_column(raw_key: str) -> str | None:
    """Return the canonical stock-sheet column for a raw OCR header."""
    return CANONICAL_COLUMN_LOOKUP.get(normalize_column_token(raw_key))


def empty_canonical_row() -> dict[str, Any]:
    """Return an empty row with every canonical stock-sheet column present."""
    return {column: None for column in CANONICAL_COLUMNS}


def enforce_canonical_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return a row with exactly the canonical stock-sheet columns in order."""
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        canonical = to_canonical_column(str(key))
        if canonical:
            normalized[canonical] = value
    return {column: normalized.get(column) for column in CANONICAL_COLUMNS}
