"""Pydantic schemas for POST /dpw-cargo-extractor."""

from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from src.models.api.response import ExtractionMetadata


class DpwCargoContainer(BaseModel):
    """One DPW container row with its storage date range."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    container: Optional[str] = None
    from_date: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("from", "from_date"),
        serialization_alias="from",
    )
    to_date: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("to", "to_date"),
        serialization_alias="to",
    )


class DpwCargoContainerLLMOutput(BaseModel):
    """Raw container object expected from the DPW cargo receipt prompt."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, str_strip_whitespace=True)

    container: Optional[str] = None
    from_date: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("from", "from_date"),
    )
    to_date: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("to", "to_date"),
    )


class DpwCargoLLMOutput(BaseModel):
    """Raw JSON shape expected from the DPW cargo receipt prompt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    date: Optional[str] = None
    containers: list[DpwCargoContainerLLMOutput | str] | str | None = Field(
        default_factory=list
    )
    receipt_no: Optional[str] = None


class DpwCargoExtractorResponse(BaseModel):
    """Flat DPW cargo extractor API response."""

    date: Optional[str] = None
    containers: Optional[list[DpwCargoContainer]] = None
    total_containers: Optional[int] = None
    pages_processed: Optional[int] = None
    receipt_no: Optional[str] = None
    metadata: Optional[ExtractionMetadata] = None
    error: Optional[str] = None

    @classmethod
    def failure(cls, message: str) -> "DpwCargoExtractorResponse":
        """Build the endpoint's error response body."""

        return cls(error=message)
