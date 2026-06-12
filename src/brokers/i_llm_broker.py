"""LLM broker interface."""

from typing import Protocol

from src.models.llm.invocation import LLMInvocationResult


class LLMBrokerInterface(Protocol):
    """Provider-neutral LLM interface."""

    async def invoke_vision(
        self,
        *,
        system_prompt: str,
        image_bytes_list: list[bytes],
        user_prompt: str,
    ) -> LLMInvocationResult:
        """Invoke a vision-capable model."""

    async def invoke_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMInvocationResult:
        """Invoke a text model."""
