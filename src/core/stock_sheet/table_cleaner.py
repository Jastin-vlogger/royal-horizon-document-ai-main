"""Optional LLM-based stock-sheet row cleaner."""

import asyncio
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.config.settings import get_settings
from src.core.llm import get_llm
from src.prompts.stock_sheet import build_stock_sheet_cleaner_prompt
from src.schemas.response import ExtractionMetadata
from src.utils.cost_calculator import calculate_cost


def _extract_usage(meta: dict) -> tuple[int, int, int]:
    usage = meta.get("token_usage") or meta.get("usage_metadata") or {}
    if not isinstance(usage, dict):
        return 0, 0, 0
    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))
    return input_tokens, output_tokens, total_tokens


def _coerce_value(value: Any) -> int | float | str | None:
    if value is None or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _sanitize_rows(rows: list[Any], fallback_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        sanitized.append({str(key): _coerce_value(value) for key, value in row.items()})
    return sanitized or fallback_rows


async def _clean_batch(
    *,
    headers: list[str],
    rows: list[dict[str, Any]],
    cleaner_prompt: str,
) -> tuple[list[str], list[dict[str, Any]], ExtractionMetadata]:
    llm = get_llm()
    payload = {"headers": headers, "rows": rows}
    response = await llm.ainvoke(
        [
            SystemMessage(content=cleaner_prompt),
            HumanMessage(content=json.dumps(payload, ensure_ascii=True)),
        ]
    )
    content = response.content if hasattr(response, "content") else str(response)
    if not isinstance(content, str):
        content = str(content)

    parsed_headers = headers
    parsed_rows = rows
    try:
        cleaned = json.loads(content)
        if isinstance(cleaned, dict):
            maybe_headers = cleaned.get("headers")
            maybe_rows = cleaned.get("rows")
            if isinstance(maybe_headers, list) and len(maybe_headers) == len(headers):
                parsed_headers = [str(header) for header in maybe_headers]
            if isinstance(maybe_rows, list) and len(maybe_rows) == len(rows):
                parsed_rows = _sanitize_rows(maybe_rows, rows)
    except json.JSONDecodeError:
        parsed_headers = headers
        parsed_rows = rows

    meta = getattr(response, "response_metadata", None) or {}
    settings = get_settings()
    input_tokens, output_tokens, total_tokens = _extract_usage(meta)
    metadata = ExtractionMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_incurred=calculate_cost(settings.model_to_use, input_tokens, output_tokens),
        cost_currency="USD",
        model=settings.model_to_use,
    )
    return parsed_headers, parsed_rows, metadata


async def maybe_clean_rows(
    headers: list[str],
    rows: list[dict[str, Any]],
    canonical_keys: list[str],
    *,
    batch_size: int = 60,
) -> tuple[list[str], list[dict[str, Any]], ExtractionMetadata | None]:
    """
    Clean rows with the LLM in one or more batches.
    Returns cleaned_headers, cleaned_rows, and aggregated cleaner metadata.
    """
    if not rows:
        return headers, rows, None

    cleaner_prompt = build_stock_sheet_cleaner_prompt(canonical_keys)
    batches = [rows[index : index + batch_size] for index in range(0, len(rows), batch_size)]
    results = await asyncio.gather(
        *[
            _clean_batch(headers=headers, rows=batch, cleaner_prompt=cleaner_prompt)
            for batch in batches
        ]
    )

    cleaned_headers = results[0][0] if results else headers
    cleaned_rows = [row for _, batch_rows, _ in results for row in batch_rows]
    metadata_parts = [metadata for _, _, metadata in results]
    aggregated = ExtractionMetadata(
        input_tokens=sum(part.input_tokens for part in metadata_parts),
        output_tokens=sum(part.output_tokens for part in metadata_parts),
        total_tokens=sum(part.total_tokens for part in metadata_parts),
        cost_incurred=round(sum(part.cost_incurred for part in metadata_parts), 6),
        cost_currency=metadata_parts[0].cost_currency if metadata_parts else "USD",
        model=metadata_parts[0].model if metadata_parts else "",
    )
    return cleaned_headers, cleaned_rows or rows, aggregated
