"""Metadata helpers for stock-sheet extraction."""

from collections.abc import Iterable

from src.models.api.response import ExtractionMetadata
from src.models.api.stock_sheet import StockSheetMetadata


def merge_extraction_metadata(
    parts: Iterable[ExtractionMetadata | None],
    *,
    model: str = "",
) -> ExtractionMetadata:
    """Combine usage metadata from multiple LLM calls."""
    collected = [part for part in parts if part is not None]
    if not collected:
        return ExtractionMetadata(model=model)

    input_tokens = sum(part.input_tokens for part in collected)
    output_tokens = sum(part.output_tokens for part in collected)
    total_tokens = sum(part.total_tokens or (part.input_tokens + part.output_tokens) for part in collected)
    return ExtractionMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_incurred=round(sum(part.cost_incurred for part in collected), 6),
        cost_currency=collected[0].cost_currency if collected else "USD",
        latency_ms=round(sum(part.latency_ms for part in collected), 2),
        model=model or next((part.model for part in collected if part.model), ""),
    )


def build_stock_sheet_metadata(
    usage: ExtractionMetadata,
    *,
    pipeline_latency_ms: float,
    model: str,
    pages_processed: int,
    cleanup_status: str,
    temp_artifacts_deleted: int,
) -> StockSheetMetadata:
    """Convert combined LLM usage into the stock-sheet API metadata shape."""
    return StockSheetMetadata(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens or (usage.input_tokens + usage.output_tokens),
        cost_incurred=usage.cost_incurred,
        cost_currency=usage.cost_currency or "USD",
        latency_ms=round(pipeline_latency_ms, 2),
        model=model or usage.model,
        pages_processed=pages_processed,
        cleanup_status=cleanup_status,
        temp_artifacts_deleted=temp_artifacts_deleted,
    )
