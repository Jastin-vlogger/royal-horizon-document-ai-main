"""Pydantic schemas for POST /boe/extract."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.models.api.response import ExtractionMetadata


class BoeExtractData(BaseModel):
    """Extracted BOE fields returned to API consumers."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    containers: list[str] = Field(
        default_factory=list,
        description="Container numbers found under MARKS & NUMBERS / Container Nos.",
    )
    date: Optional[str] = Field(
        default=None,
        description="DCE DATE normalized to DD/MM/YYYY, or null when absent.",
    )


class BoeLLMOutput(BaseModel):
    """Raw JSON shape expected from the BOE extraction prompt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    containers: list[str] | str | None = Field(default_factory=list)
    date: Optional[str] = None


class BoeExtractResponse(BaseModel):
    """Successful BOE extraction response."""

    success: bool = True
    data: BoeExtractData = Field(default_factory=BoeExtractData)
    metadata: ExtractionMetadata = Field(default_factory=ExtractionMetadata)


class BoeValidationErrorResponse(BaseModel):
    """BOE validation error response."""

    success: bool = False
    message: str
