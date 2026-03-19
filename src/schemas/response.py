"""Response schemas for the document extraction API."""

from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


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
    container_size: Optional[int] = None


class ShipmentClassificationResult(BaseModel):
    """LLM output from shipment document classification (extra keys preserved)."""

    model_config = ConfigDict(extra="allow")

    is_valid_document: bool = False
    has_lpo: bool = False
    has_performa_invoice: bool = False
    has_ricequality_doc: bool = False
    reason: str = ""


class ShipmentFormResponse(BaseModel):
    """Combined response from /shipment-form: LPO, Performa, calculations, classification, rice report, metadata."""

    lpo_invoice: Optional[LPOInvoiceResult] = Field(default=None, description="LPO extraction result.")
    performa_invoice: Optional[PerformaInvoiceResult] = Field(
        default=None, description="Performa invoice extraction result."
    )
    metadata: Optional[ExtractionMetadata] = Field(default=None, description="Aggregated usage/cost metadata.")
    shipment_calculations: Optional[dict[str, Any]] = Field(
        default=None,
        description="Derived logistics and price reconciliation (fcl, bags, is_price_matching, etc.).",
    )
    classified_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Full JSON from shipment document classification LLM call.",
    )
    s1_quality_report: Optional[dict[str, Any]] = Field(
        default=None,
        description="Full JSON from Rice Quality Report extraction LLM call.",
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
        if self.classified_data is not None:
            out["classified_data"] = self.classified_data
        if self.s1_quality_report is not None:
            out["s1_quality_report"] = self.s1_quality_report
        return out


class BillOfLadingContainerRow(BaseModel):
    """One row from the container annexure (Page 2)."""

    model_config = ConfigDict(extra="ignore")

    container_no: str = Field(..., description="Container ID as printed (e.g. FCIU2664293).")
    pkg_ct: int = Field(..., description="Package count from the Pkg Cnt column for this row.")

    @field_validator("container_no", mode="before")
    @classmethod
    def _strip_container_no(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v


class BillOfLadingStructuredExtraction(BaseModel):
    """
    Structured B/L and shipment fields aligned with the bill extraction notebook schema.
    Nullable fields mirror explicit nulls from the model when data is missing.
    """

    model_config = ConfigDict(extra="ignore")

    bl_number: Optional[str] = Field(default=None, description="B/L NUMBER / B/L No.")
    shipped_on_board_date: Optional[str] = Field(
        default=None, description="ISO 8601 date YYYY-MM-DD when cargo shipped on board."
    )
    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    number_of_containers: Optional[int] = None
    number_of_bags: Optional[int] = None
    quantity_mt: Optional[float] = Field(default=None, description="Total quantity in metric tons.")
    shipping_line: Optional[str] = None
    free_detention_days: Optional[int] = None
    maximum_detention_days: Optional[int] = None
    freight_prepaid: Optional[bool] = None
    vessel_name: Optional[str] = None
    invoice_number: Optional[str] = None
    containers: list[BillOfLadingContainerRow] = Field(
        default_factory=list,
        description="Annexure rows; empty if Page 2 was not provided or has no table.",
    )
    checksum_warning: Optional[bool] = Field(
        default=None,
        description="True when pkg_ct sum could not be reconciled with number_of_bags.",
    )

    @field_validator("containers", mode="before")
    @classmethod
    def _containers_none_to_empty(cls, v: Any) -> Any:
        if v is None:
            return []
        return v

    @model_validator(mode="before")
    @classmethod
    def _trim_top_level_strings(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        skip = {"containers", "freight_prepaid", "checksum_warning"}
        for key, val in list(out.items()):
            if key in skip or not isinstance(val, str):
                continue
            s = val.strip()
            out[key] = s if s else None
        return out


class BillNoExtractionResponse(BaseModel):
    """
    Flat JSON shape for POST /purchase-tracker/bill-no: extraction fields and metadata
    at the top level (no nested `extraction` object).
    """

    bill_no: Optional[str] = Field(default=None, description="B/L number (from model bl_number / bill_no).")
    shipped_on_board_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD.")
    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    number_of_containers: Optional[int] = None
    number_of_bags: Optional[int] = None
    quantity_mt: Optional[float] = Field(default=None, description="Quantity in metric tons.")
    shipping_line: Optional[str] = None
    free_detention_days: Optional[int] = None
    maximum_detention_days: Optional[int] = None
    freight_prepaid: Optional[bool] = None
    vessel_name: Optional[str] = None
    invoice_number: Optional[str] = None
    containers: list[BillOfLadingContainerRow] = Field(
        default_factory=list,
        description="Container annexure rows; empty list if none.",
    )
    metadata: Optional[ExtractionMetadata] = Field(
        default=None,
        description="Token usage, cost, latency from the LLM call.",
    )

    @field_serializer("quantity_mt", when_used="json")
    def _quantity_mt_json(self, value: Optional[float]) -> Optional[Union[int, float]]:
        if value is None:
            return None
        f = float(value)
        if f.is_integer():
            return int(f)
        return f
