"""Pydantic schemas for POST /bank-advice/is-signed."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BankAdviceIsSignedMetadata(BaseModel):
    """Token usage, cost, and latency for the vision LLM call."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)
    cost_incurred: float = Field(..., ge=0.0)
    cost_currency: Literal["USD"] = "USD"
    latency_ms: float = Field(..., ge=0.0)
    model: str = Field(..., min_length=1)


class BankAdviceSignatureLLMOutput(BaseModel):
    """Strict model output: signature and seal presence only (no metadata)."""

    model_config = ConfigDict(extra="forbid")

    is_signed: bool = Field(
        ...,
        description="True only if visible handwritten ink signature/initials (not printed text).",
    )
    is_sealed: bool = Field(
        ...,
        description="True only if a visible stamp/seal impression (ink), not a printed logo only.",
    )


class BankAdviceIsSignedResponse(BaseModel):
    """Full API response for bank advice signature and seal detection."""

    model_config = ConfigDict(extra="forbid")

    is_signed: bool
    is_sealed: bool
    metadata: BankAdviceIsSignedMetadata
