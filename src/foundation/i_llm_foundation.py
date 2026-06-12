"""LLM foundation interface."""

from typing import Protocol

from src.models.llm.invocation import LLMInvocationResult


class LLMFoundationInterface(Protocol):
    """Domain LLM operations."""

    async def vision(
        self,
        *,
        system_prompt: str,
        image_bytes_list: list[bytes],
        user_prompt: str,
    ) -> LLMInvocationResult:
        """Invoke a vision model."""

    async def text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMInvocationResult:
        """Invoke a text model."""
