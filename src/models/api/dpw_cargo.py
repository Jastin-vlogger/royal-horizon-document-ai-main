"""Pydantic schemas for POST /dpw-cargo-extractor."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.models.api.response import ExtractionMetadata


class DpwCargoLLMOutput(BaseModel):
    """Raw JSON shape expected from the DPW cargo receipt prompt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    date: Optional[str] = None
    containers: list[str] | str | None = Field(default_factory=list)
    receipt_no: Optional[str] = None


class DpwCargoExtractorResponse(BaseModel):
    """Flat DPW cargo extractor API response."""

    date: Optional[str] = None
    containers: Optional[list[str]] = None
    total_containers: Optional[int] = None
    pages_processed: Optional[int] = None
    receipt_no: Optional[str] = None
    metadata: Optional[ExtractionMetadata] = None
    error: Optional[str] = None

    @classmethod
    def failure(cls, message: str) -> "DpwCargoExtractorResponse":
        """Build the endpoint's error response body."""

        return cls(error=message)
