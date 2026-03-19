"""Pydantic schemas for POST /costsheet/is-signed."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CostSheetSignedBy(BaseModel):
    """Per-role handwritten signature presence on the cost sheet left margin."""

    model_config = ConfigDict(extra="forbid")

    cfo: bool = Field(..., description="CFO block signed with genuine pen ink.")
    fc: bool = Field(..., description="FC block signed.")
    md: bool = Field(..., description="MD block signed.")
    ap: bool = Field(..., description="AP block signed.")


class CostSheetIsSignedMetadata(BaseModel):
    """Token usage, cost, and latency for the vision LLM call."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)
    cost_incurred: float = Field(..., ge=0.0)
    cost_currency: Literal["USD"] = "USD"
    latency_ms: float = Field(..., ge=0.0)
    model: str = Field(..., min_length=1)


class CostSheetSignatureLLMOutput(BaseModel):
    """
    Strict subset returned by the model (no metadata).
    Parsed and validated before merging with invocation metadata.
    """

    model_config = ConfigDict(extra="forbid")

    is_all_signed: bool
    signed_by: CostSheetSignedBy


class CostSheetIsSignedResponse(BaseModel):
    """Full API response for cost sheet signature detection."""

    model_config = ConfigDict(extra="forbid")

    is_all_signed: bool
    signed_by: CostSheetSignedBy
    metadata: CostSheetIsSignedMetadata
