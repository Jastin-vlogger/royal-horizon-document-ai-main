"""Vision LLM pipeline for bank advice signature and seal detection (first page / single image)."""

import base64
import json
import re
import time
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.config.logger import logger
from src.config.settings import get_settings
from src.prompts.bank_advice_is_signed import (
    BANK_ADVICE_IS_SIGNED_SYSTEM_PROMPT,
    BANK_ADVICE_USER_PROMPT,
)
from src.schemas.bank_advice_is_signed import (
    BankAdviceIsSignedMetadata,
    BankAdviceIsSignedResponse,
    BankAdviceSignatureLLMOutput,
)
from src.utils.cost_calculator import calculate_cost


def _usage_from_response_metadata(
    meta: Optional[Dict[str, Any]],
) -> tuple[int, int, int]:
    if not meta:
        return 0, 0, 0
    usage = meta.get("token_usage") or meta.get("usage_metadata") or {}
    if isinstance(usage, dict):
        inp = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        out = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        total = usage.get("total_tokens") or (inp + out)
        return int(inp), int(out), int(total)
    return 0, 0, 0


def _build_vision_human_message(image_bytes: bytes, user_text: str) -> HumanMessage:
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    image_url = f"data:image/png;base64,{b64}"
    content: list = [
        {"type": "text", "text": user_text.strip()},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]
    return HumanMessage(content=content)


def _strip_json_from_llm_text(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```\s*$", "", s)
        return s.strip()
    m = re.search(r"\{[\s\S]*\}\s*$", s)
    if m:
        return m.group(0).strip()
    return s


def _parse_bank_advice_llm_output(content: str) -> BankAdviceSignatureLLMOutput:
    stripped = _strip_json_from_llm_text(content)
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM output is not valid JSON: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError("LLM JSON root must be an object")
    try:
        return BankAdviceSignatureLLMOutput.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"LLM JSON does not match schema: {e}") from e


async def run_bank_advice_signature_detection(
    image_png_bytes: bytes,
) -> BankAdviceIsSignedResponse:
    """
    Run vision model on PNG bytes. No SystemMessage when the placeholder is empty.

    Raises ValueError if the model output cannot be parsed or validated.
    """
    from src.core.llm import get_llm

    llm = get_llm()
    s = get_settings()
    model = s.model_to_use

    messages = []
    sys_text = BANK_ADVICE_IS_SIGNED_SYSTEM_PROMPT.strip()
    if sys_text:
        messages.append(SystemMessage(content=sys_text))
    messages.append(
        _build_vision_human_message(image_png_bytes, BANK_ADVICE_USER_PROMPT)
    )

    start = time.perf_counter()
    try:
        response = await llm.ainvoke(messages)
    except Exception as e:
        logger.exception("Bank advice vision LLM invocation failed")
        raise RuntimeError(f"Vision model request failed: {e}") from e

    latency_ms = (time.perf_counter() - start) * 1000.0
    content = response.content if hasattr(response, "content") else str(response)
    if not isinstance(content, str):
        content = str(content)

    meta = getattr(response, "response_metadata", None) or {}
    input_tokens, output_tokens, total_tokens = _usage_from_response_metadata(meta)
    cost_usd = calculate_cost(model, input_tokens, output_tokens)

    extraction_meta = BankAdviceIsSignedMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_incurred=cost_usd,
        cost_currency="USD",
        latency_ms=round(latency_ms, 2),
        model=model,
    )

    try:
        llm_part = _parse_bank_advice_llm_output(content)
    except ValueError:
        logger.warning("Bank advice signature/seal parse or validation failed")
        raise

    return BankAdviceIsSignedResponse(
        is_signed=llm_part.is_signed,
        is_sealed=llm_part.is_sealed,
        metadata=extraction_meta,
    )
