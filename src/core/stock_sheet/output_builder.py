"""Build unified stock-sheet response objects."""

from src.schemas.stock_sheet import (
    StockSheetData,
    StockSheetFileInfo,
    StockSheetMetadata,
    StockSheetResponse,
    StockSheetRow,
)


def build_stock_sheet_response(
    *,
    valid: bool,
    status: str,
    reason: str | None,
    filename: str,
    file_type: str,
    pages_detected: int,
    pages_processed: int,
    headers: list[str],
    rows: list[dict[str, str]],
    signature_check: dict | None,
    metadata: StockSheetMetadata,
) -> StockSheetResponse:
    """Create API response with stable structure for all outcomes."""
    row_models = [StockSheetRow.model_validate(row) for row in rows]
    return StockSheetResponse(
        valid=valid,
        status=status,
        reason=reason,
        file_info=StockSheetFileInfo(
            filename=filename,
            file_type=file_type,
            pages_detected=pages_detected,
            pages_processed=pages_processed,
        ),
        data=StockSheetData(
            headers=headers,
            rows=row_models,
            total_rows=len(row_models),
        ),
        signature_check=signature_check,
        metadata=metadata,
    )
