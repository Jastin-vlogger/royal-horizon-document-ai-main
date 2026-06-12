"""LLM foundation implementation."""

from src.brokers.i_llm_broker import LLMBrokerInterface
from src.models.llm.invocation import LLMInvocationResult


class LLMFoundation:
    """Domain wrapper around provider-neutral LLM broker."""

    def __init__(self, llm_broker: LLMBrokerInterface) -> None:
        self._llm_broker = llm_broker

    async def vision(
        self,
        *,
        system_prompt: str,
        image_bytes_list: list[bytes],
        user_prompt: str,
    ) -> LLMInvocationResult:
        return await self._llm_broker.invoke_vision(
            system_prompt=system_prompt,
            image_bytes_list=image_bytes_list,
            user_prompt=user_prompt,
        )

    async def text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMInvocationResult:
        return await self._llm_broker.invoke_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
