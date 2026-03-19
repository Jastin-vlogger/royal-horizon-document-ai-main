"""LLM invocation with vision support, usage tracking, and cost calculation."""

import base64
import time
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config.settings import get_settings
from src.schemas.response import ExtractionMetadata
from src.utils.cost_calculator import calculate_cost


def _build_image_message(
    image_bytes: bytes,
    user_text: str = "Extract the required fields and return only valid JSON.",
) -> HumanMessage:
    """Build a HumanMessage with image (base64) and optional text."""
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    image_url = f"data:image/png;base64,{b64}"
    content: list = [
        {"type": "text", "text": user_text},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]
    return HumanMessage(content=content)


def _build_multi_image_message(
    image_bytes_list: list[bytes],
    user_text: str,
) -> HumanMessage:
    """Build a HumanMessage with multiple PNG images (base64) and leading text."""
    content: list = [{"type": "text", "text": user_text}]
    for chunk in image_bytes_list:
        b64 = base64.standard_b64encode(chunk).decode("utf-8")
        image_url = f"data:image/png;base64,{b64}"
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    return HumanMessage(content=content)


def _usage_from_response_metadata(
    meta: Optional[Dict[str, Any]],
) -> tuple[int, int, int]:
    """Extract input_tokens, output_tokens, total_tokens from response_metadata."""
    if not meta:
        return 0, 0, 0
    usage = meta.get("token_usage") or meta.get("usage_metadata") or {}
    if isinstance(usage, dict):
        inp = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        out = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        total = usage.get("total_tokens") or (inp + out)
        return int(inp), int(out), int(total)
    return 0, 0, 0


def get_llm() -> ChatOpenAI:
    """Create ChatOpenAI instance from settings (vision-capable)."""
    s = get_settings()
    return ChatOpenAI(
        model=s.model_to_use,
        temperature=s.temperature,
        max_tokens=s.max_tokens,
        api_key=s.openai_api_key,
    )


async def invoke_vision_extraction(
    system_prompt: str,
    image_bytes: bytes,
    user_text: str = "Extract the required fields and return only valid JSON.",
) -> tuple[str, ExtractionMetadata]:
    """
    Run vision extraction: system prompt + image, return (content, metadata).
    Uses ainvoke and captures token usage, cost, and latency.
    """
    llm = get_llm()
    s = get_settings()
    model = s.model_to_use

    messages = [
        SystemMessage(content=system_prompt),
        _build_image_message(image_bytes, user_text),
    ]

    start = time.perf_counter()
    response = await llm.ainvoke(messages)
    latency_ms = (time.perf_counter() - start) * 1000.0

    content = response.content if hasattr(response, "content") else str(response)
    if not isinstance(content, str):
        content = str(content)

    meta = getattr(response, "response_metadata", None) or {}
    input_tokens, output_tokens, total_tokens = _usage_from_response_metadata(meta)
    cost_usd = calculate_cost(model, input_tokens, output_tokens)

    extraction_meta = ExtractionMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_incurred=cost_usd,
        cost_currency="USD",
        latency_ms=round(latency_ms, 2),
        model=model,
    )
    return content, extraction_meta


async def invoke_multi_image_vision_extraction(
    system_prompt: str,
    image_bytes_list: list[bytes],
    user_text: str = "Extract the required fields and return only valid JSON.",
) -> tuple[str, ExtractionMetadata]:
    """
    Vision extraction with one HumanMessage containing multiple images.
    Same metadata/cost behavior as invoke_vision_extraction.
    """
    if not image_bytes_list:
        raise ValueError("At least one image is required")

    llm = get_llm()
    s = get_settings()
    model = s.model_to_use

    messages = [
        SystemMessage(content=system_prompt),
        _build_multi_image_message(image_bytes_list, user_text),
    ]

    start = time.perf_counter()
    response = await llm.ainvoke(messages)
    latency_ms = (time.perf_counter() - start) * 1000.0

    content = response.content if hasattr(response, "content") else str(response)
    if not isinstance(content, str):
        content = str(content)

    meta = getattr(response, "response_metadata", None) or {}
    input_tokens, output_tokens, total_tokens = _usage_from_response_metadata(meta)
    cost_usd = calculate_cost(model, input_tokens, output_tokens)

    extraction_meta = ExtractionMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_incurred=cost_usd,
        cost_currency="USD",
        latency_ms=round(latency_ms, 2),
        model=model,
    )
    return content, extraction_meta
