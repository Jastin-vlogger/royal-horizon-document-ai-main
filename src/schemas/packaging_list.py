"""Pydantic schemas for Packaging List extraction."""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class PackagingListContainerInfo(BaseModel):
    """Individual container information from packaging list."""

    container_number: str = Field(..., description="Exact container number as printed")
    no_of_bags: Optional[int] = Field(default=None, description="Number of bags in this container")
    gross_weight: Optional[str] = Field(default=None, description="Gross weight with unit (e.g., 25292.00 KGS)")
    net_weight: Optional[str] = Field(default=None, description="Net weight with unit (e.g., 25000.00 KGS)")

    @field_validator("container_number", mode="before")
    @classmethod
    def _strip_container_number(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v


class PackagingListExtraction(BaseModel):
    """Structured extraction from Packaging List document."""

    brand: Optional[str] = Field(default=None, description="Brand name as it appears in the document")
    expiry_date: Optional[str] = Field(default=None, description="Expiry date (e.g., 08/2027)")
    packing_description: Optional[str] = Field(
        default=None, description="Packing description (e.g., 20KG POUCH BAG)"
    )
    container_info: list[PackagingListContainerInfo] = Field(
        default_factory=list, description="List of container information"
    )
    total_bags: Optional[int] = Field(default=None, description="Total number of bags across all containers")
    total_gross_weight: Optional[str] = Field(default=None, description="Total gross weight with unit")
    total_net_weight: Optional[str] = Field(default=None, description="Total net weight with unit")
    container_number_list: list[str] = Field(
        default_factory=list, description="List of all container numbers for quick lookup"
    )

    @field_validator("container_info", mode="before")
    @classmethod
    def _container_info_none_to_empty(cls, v: Any) -> Any:
        if v is None:
            return []
        return v

    @field_validator("container_number_list", mode="before")
    @classmethod
    def _container_number_list_none_to_empty(cls, v: Any) -> Any:
        if v is None:
            return []
        return v
