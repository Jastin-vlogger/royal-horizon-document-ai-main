"""Document workflow dispatcher interface."""

from typing import Optional, Protocol

from fastapi import UploadFile


class DocumentWorkflowDispatcherInterface(Protocol):
    """Bridge HTTP input objects to domain commands."""

    async def bank_advice_is_signed(self, file: UploadFile):
        """Dispatch bank advice signature/seal detection."""

    async def costsheet_is_signed(self, file: UploadFile):
        """Dispatch cost sheet signature detection."""

    async def tax_invoice_extraction(self, file: UploadFile):
        """Dispatch tax invoice extraction."""

    async def arrival_notice_extract(self, file: UploadFile):
        """Dispatch arrival notice extraction."""

    async def boe_extract(self, file: UploadFile):
        """Dispatch BOE extraction."""

    async def shipment_form(
        self,
        *,
        lpo_invoice: Optional[UploadFile],
        rice_quality_report: Optional[UploadFile],
        inco_terms_list: Optional[str],
        suppliers: Optional[str],
    ):
        """Dispatch shipment-form extraction."""

    async def purchase_tracker_fetch_details(
        self,
        *,
        file: UploadFile,
        packaging_list_file: Optional[UploadFile],
        packaging_brand: Optional[str],
    ):
        """Dispatch purchase tracker extraction."""

    async def stock_sheet_extract(self, file: UploadFile):
        """Dispatch stock-sheet extraction."""
