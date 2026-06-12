"""Pydantic schemas for stock-sheet extraction endpoint."""

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, create_model

from src.models.common.stock_sheet_columns import CANONICAL_COLUMNS


class StockSheetMetadata(BaseModel):
    """Usage, cost, and processing metadata for stock-sheet extraction."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_incurred: float = 0.0
    cost_currency: Literal["USD"] = "USD"
    latency_ms: float = 0.0
    model: str = ""
    pages_processed: int = 0
    cleanup_status: Literal["success", "partial", "not_required"] = "not_required"
    temp_artifacts_deleted: int = 0


class StockSheetFileInfo(BaseModel):
    """Input-file metadata reported in response."""

    filename: str
    file_type: str
    pages_detected: int = 0
    pages_processed: int = 0


StockSheetCellValue = Optional[str | int | float]


class _StockSheetRowBase(BaseModel):
    """Shared config for dynamically generated stock-sheet rows."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


def _column_to_field_name(column: str, used_names: set[str]) -> str:
    candidate = re.sub(r"[^0-9a-zA-Z]+", "_", column).strip("_").lower()
    if not candidate or candidate[0].isdigit():
        candidate = f"col_{candidate}"
    base = candidate
    suffix = 2
    while candidate in used_names:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used_names.add(candidate)
    return candidate


def _build_stock_sheet_row_model() -> type[BaseModel]:
    field_names: set[str] = set()
    field_definitions = {}
    for column in CANONICAL_COLUMNS:
        field_definitions[_column_to_field_name(column, field_names)] = (
            StockSheetCellValue,
            Field(default=None, alias=column, serialization_alias=column),
        )
    return create_model(
        "StockSheetRow",
        __base__=_StockSheetRowBase,
        __module__=__name__,
        **field_definitions,
    )


StockSheetRow = _build_stock_sheet_row_model()


class StockSheetData(BaseModel):
    """Extracted stock-sheet table data."""

    headers: list[str] = Field(default_factory=list)
    rows: list[StockSheetRow] = Field(default_factory=list)
    total_rows: int = 0


class StockSheetResponse(BaseModel):
    """Unified JSON response for valid/invalid/failed processing outcomes."""

    valid: bool
    status: Literal["processed", "invalid", "failed"]
    reason: Optional[str] = None
    file_info: StockSheetFileInfo
    data: StockSheetData
    signature_check: Optional[dict] = None
    metadata: StockSheetMetadata
