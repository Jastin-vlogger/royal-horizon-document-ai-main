"""Metadata aggregation utilities."""

from src.schemas.response import ExtractionMetadata


def aggregate_metadata(
    bill_metadata: ExtractionMetadata,
    packaging_metadata: ExtractionMetadata,
) -> ExtractionMetadata:
    """
    Aggregate metadata from bill and packaging list extractions.
    
    Sums token counts and costs, takes max latency, and combines model info.
    
    Args:
        bill_metadata: Metadata from bill extraction
        packaging_metadata: Metadata from packaging list extraction
    
    Returns:
        Aggregated metadata
    """
    return ExtractionMetadata(
        input_tokens=bill_metadata.input_tokens + packaging_metadata.input_tokens,
        output_tokens=bill_metadata.output_tokens + packaging_metadata.output_tokens,
        total_tokens=bill_metadata.total_tokens + packaging_metadata.total_tokens,
        cost_incurred=round(bill_metadata.cost_incurred + packaging_metadata.cost_incurred, 6),
        cost_currency=bill_metadata.cost_currency,
        latency_ms=round(max(bill_metadata.latency_ms, packaging_metadata.latency_ms), 2),
        model=bill_metadata.model,
    )
