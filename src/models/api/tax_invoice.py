"""Pydantic schemas for tax invoice extraction."""

from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.models.api.response import ExtractionMetadata


class TaxInvoiceExtractionResult(BaseModel):
    """Normalized tax invoice fields returned to API consumers."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    po_number: Optional[str] = None
    invoice_id: Optional[str] = None
    invoice_date: Optional[str] = None
    bill_to: Optional[str] = None


class TaxInvoiceLLMOutput(BaseModel):
    """Strict raw shape expected from LLM output."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    po_number: Optional[str] = None
    invoice_id: Optional[str] = None
    invoice_date: Optional[str] = None
    bill_to: Optional[str] = None


class TaxInvoiceExtractionResponse(BaseModel):
    """API response contract for tax invoice extraction."""

    tax_invoice_extraction_result: TaxInvoiceExtractionResult
    metadata: ExtractionMetadata
