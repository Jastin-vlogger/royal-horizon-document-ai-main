"""LangChain OpenAI LLM broker implementation."""

import base64
import time
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config.settings import Settings
from src.config.model_pricing import calculate_cost
from src.models.api.response import ExtractionMetadata
from src.models.llm.invocation import LLMInvocationResult


class LangChainOpenAIBroker:
    """LLM broker backed by LangChain's ChatOpenAI adapter."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _client(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self._settings.model_to_use,
            temperature=self._settings.temperature,
            max_tokens=self._settings.max_tokens,
            api_key=self._settings.openai_api_key,
            timeout=self._settings.llm_timeout_seconds,
        )

    @staticmethod
    def _usage_from_response_metadata(
        meta: Optional[dict[str, Any]],
    ) -> tuple[int, int, int]:
        if not meta:
            return 0, 0, 0
        usage = meta.get("token_usage") or meta.get("usage_metadata") or {}
        if not isinstance(usage, dict):
            return 0, 0, 0
        input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))
        return input_tokens, output_tokens, total_tokens

    @staticmethod
    def _vision_message(image_bytes_list: list[bytes], user_prompt: str) -> HumanMessage:
        content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        for image_bytes in image_bytes_list:
            encoded = base64.standard_b64encode(image_bytes).decode("utf-8")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{encoded}"},
                }
            )
        return HumanMessage(content=content)

    def _metadata(self, response: Any, latency_ms: float) -> ExtractionMetadata:
        raw_meta = getattr(response, "response_metadata", None) or {}
        input_tokens, output_tokens, total_tokens = self._usage_from_response_metadata(raw_meta)
        model = self._settings.model_to_use
        return ExtractionMetadata(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_incurred=calculate_cost(model, input_tokens, output_tokens),
            cost_currency="USD",
            latency_ms=round(latency_ms, 2),
            model=model,
        )

    async def invoke_vision(
        self,
        *,
        system_prompt: str,
        image_bytes_list: list[bytes],
        user_prompt: str,
    ) -> LLMInvocationResult:
        if not image_bytes_list:
            raise ValueError("At least one image is required")

        messages = []
        if system_prompt.strip():
            messages.append(SystemMessage(content=system_prompt.strip()))
        messages.append(self._vision_message(image_bytes_list, user_prompt.strip()))

        started_at = time.perf_counter()
        response = await self._client().ainvoke(messages)
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        content = response.content if hasattr(response, "content") else str(response)
        if not isinstance(content, str):
            content = str(content)
        return LLMInvocationResult(
            content=content,
            metadata=self._metadata(response, latency_ms),
        )

    async def invoke_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMInvocationResult:
        messages = []
        if system_prompt.strip():
            messages.append(SystemMessage(content=system_prompt.strip()))
        messages.append(HumanMessage(content=user_prompt))

        started_at = time.perf_counter()
        response = await self._client().ainvoke(messages)
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        content = response.content if hasattr(response, "content") else str(response)
        if not isinstance(content, str):
            content = str(content)
        return LLMInvocationResult(
            content=content,
            metadata=self._metadata(response, latency_ms),
        )
