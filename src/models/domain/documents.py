"""Internal document command DTOs."""

from typing import Optional

from pydantic import BaseModel, Field


class DocumentInput(BaseModel):
    """Uploaded document bytes plus client-visible file metadata."""

    filename: str
    content: bytes = Field(repr=False)


class SingleDocumentCommand(BaseModel):
    """Command for a workflow that receives one document."""

    document: DocumentInput


class ShipmentFormCommand(BaseModel):
    """Command for the shipment-form workflow."""

    lpo_invoice: DocumentInput
    rice_quality_report: DocumentInput
    inco_terms_list: list[str] = Field(default_factory=list)
    suppliers: list[str] = Field(default_factory=list)


class PurchaseTrackerCommand(BaseModel):
    """Command for purchase tracker bill and optional packaging-list workflow."""

    bill_document: DocumentInput
    packaging_list_document: Optional[DocumentInput] = None
    packaging_brand: Optional[str] = None
