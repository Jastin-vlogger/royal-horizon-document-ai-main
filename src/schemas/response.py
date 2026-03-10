"""Response schemas for the document extraction API."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ExtractionMetadata(BaseModel):
    """Token usage and cost metadata from LLM invocation."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_incurred: float = 0.0
    cost_currency: str = "USD"
    latency_ms: float = 0.0
    model: str = ""


class LPOInvoiceResult(BaseModel):
    """Extracted key-value result for LPO document."""

    model_config = ConfigDict(extra="allow")

    po_number: Optional[str] = None
    po_date: Optional[str] = None
    vendor: Optional[str] = None
    item_code: Optional[str] = None
    commodity: Optional[str] = None
    item: Optional[str] = None
    quantity: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[str] = None
    packaging: Optional[str] = None


class PerformaInvoiceResult(BaseModel):
    """Extracted key-value result for Performa Invoice document."""

    model_config = ConfigDict(extra="allow")

    supplier_details: Optional[str] = None
    inco_terms: Optional[str] = None
    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    pi_number: Optional[str] = None
    pi_date: Optional[str] = None
    quantity: Optional[str] = None
    price_per_mton: Optional[str] = None
    total_price: Optional[str] = None
    partial_shipment: Optional[str] = None
    shipment_terms: Optional[str] = None
    brand: Optional[str] = None
    payment_terms: Optional[str] = None


class ShipmentFormResponse(BaseModel):
    """Combined response from /shipment-form with both documents and metadata."""

    lpo_invoice: Optional[LPOInvoiceResult] = Field(default=None, description="LPO extraction result.")
    performa_invoice: Optional[PerformaInvoiceResult] = Field(
        default=None, description="Performa invoice extraction result."
    )
    metadata: Optional[ExtractionMetadata] = Field(default=None, description="Aggregated usage/cost metadata.")
    shipment_calculations: Optional[dict[str, Any]] = Field(
        default=None,
        description="Derived logistics and price reconciliation (fcl, bags, is_price_matching, etc.).",
    )

    def to_combined_json(self) -> dict[str, Any]:
        """Return a clean combined JSON dict (no metadata if not needed in final contract)."""
        out: dict[str, Any] = {}
        if self.lpo_invoice is not None:
            out["lpo_invoice"] = self.lpo_invoice.model_dump(exclude_none=False)
        else:
            out["lpo_invoice"] = None
        if self.performa_invoice is not None:
            out["performa_invoice"] = self.performa_invoice.model_dump(exclude_none=False)
        else:
            out["performa_invoice"] = None
        if self.metadata is not None:
            out["metadata"] = self.metadata.model_dump()
        if self.shipment_calculations is not None:
            out["shipment_calculations"] = self.shipment_calculations
        return out
