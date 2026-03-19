"""Vision LLM pipeline for cost sheet signature detection (first page / single image)."""

import base64
import json
import re
import time
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.config.logger import logger
from src.config.settings import get_settings
from src.prompts.costsheet_is_signed import (
    COSTSHEET_IS_SIGNED_PROMPT,
    COSTSHEET_SIGNATURE_USER_PROMPT,
)
from src.schemas.costsheet_is_signed import (
    CostSheetIsSignedMetadata,
    CostSheetIsSignedResponse,
    CostSheetSignatureLLMOutput,
)
from src.utils.cost_calculator import calculate_cost


def _usage_from_response_metadata(meta: Optional[Dict[str, Any]]) -> tuple[int, int, int]:
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
        {"type": "text", "text": user_text},
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


def _normalize_signature_payload(data: Any) -> dict[str, Any]:
    """
    Accept both API shape (nested signed_by) and legacy flat keys from the notebook
    (is_ap_signed, is_fc_signed, is_cfo_signed, is_md_signed).
    """
    if not isinstance(data, dict):
        raise ValueError("LLM JSON root must be an object")

    out = dict(data)
    signed_by = out.get("signed_by")
    if isinstance(signed_by, dict):
        for k in ("is_ap_signed", "is_fc_signed", "is_cfo_signed", "is_md_signed"):
            out.pop(k, None)
        return out

    legacy_keys = ("is_ap_signed", "is_fc_signed", "is_cfo_signed", "is_md_signed")
    if all(k in out for k in legacy_keys):
        out["signed_by"] = {
            "ap": bool(out.pop("is_ap_signed")),
            "fc": bool(out.pop("is_fc_signed")),
            "cfo": bool(out.pop("is_cfo_signed")),
            "md": bool(out.pop("is_md_signed")),
        }
        return out

    return out


def _parse_signature_llm_output(content: str) -> CostSheetSignatureLLMOutput:
    stripped = _strip_json_from_llm_text(content)
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM output is not valid JSON: {e}") from e
    data = _normalize_signature_payload(raw)
    try:
        return CostSheetSignatureLLMOutput.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"LLM JSON does not match schema: {e}") from e


async def run_costsheet_signature_detection(
    image_png_bytes: bytes,
) -> CostSheetIsSignedResponse:
    """
    Run vision model on PNG bytes. No SystemMessage unless placeholder is non-empty.

    Raises ValueError if the model output cannot be parsed or validated as JSON matching
    the signature schema (after tokens may already have been consumed).
    """
    from src.core.llm import get_llm

    llm = get_llm()
    s = get_settings()
    model = s.model_to_use

    messages = []
    sys_text = COSTSHEET_IS_SIGNED_PROMPT.strip()
    if sys_text:
        messages.append(SystemMessage(content=sys_text))
    messages.append(
        _build_vision_human_message(image_png_bytes, COSTSHEET_SIGNATURE_USER_PROMPT)
    )

    start = time.perf_counter()
    response = await llm.ainvoke(messages)
    latency_ms = (time.perf_counter() - start) * 1000.0
    content = response.content if hasattr(response, "content") else str(response)
    if not isinstance(content, str):
        content = str(content)

    meta = getattr(response, "response_metadata", None) or {}
    input_tokens, output_tokens, total_tokens = _usage_from_response_metadata(meta)
    cost_usd = calculate_cost(model, input_tokens, output_tokens)

    extraction_meta = CostSheetIsSignedMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_incurred=cost_usd,
        cost_currency="USD",
        latency_ms=round(latency_ms, 2),
        model=model,
    )

    try:
        llm_part = _parse_signature_llm_output(content)
    except ValueError:
        logger.warning("Cost sheet signature parse/validation failed")
        raise

    return CostSheetIsSignedResponse(
        is_all_signed=llm_part.is_all_signed,
        signed_by=llm_part.signed_by,
        metadata=extraction_meta,
    )
