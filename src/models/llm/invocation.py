"""Provider-neutral LLM request and response models."""

from pydantic import BaseModel, Field

from src.models.api.response import ExtractionMetadata


class LLMInvocationRequest(BaseModel):
    """Text-only LLM invocation request."""

    system_prompt: str
    user_prompt: str


class VisionLLMRequest(LLMInvocationRequest):
    """Vision LLM invocation request with one or more PNG images."""

    images: list[bytes] = Field(default_factory=list, repr=False)


class LLMInvocationResult(BaseModel):
    """Normalized LLM response content plus usage metadata."""

    content: str
    metadata: ExtractionMetadata
