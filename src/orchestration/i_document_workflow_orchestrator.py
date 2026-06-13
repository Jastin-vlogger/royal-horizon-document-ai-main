"""Document workflow orchestrator interface."""

from typing import Protocol

from src.models.api.arrival_notice import ArrivalNoticeExtractResponse
from src.models.api.bank_advice_is_signed import BankAdviceIsSignedResponse
from src.models.api.boe import BoeExtractResponse
from src.models.api.costsheet_is_signed import CostSheetIsSignedResponse
from src.models.api.response import EnhancedBillNoExtractionResponse, ShipmentFormResponse
from src.models.api.stock_sheet import StockSheetResponse
from src.models.api.tax_invoice import TaxInvoiceExtractionResponse
from src.models.domain.documents import (
    PurchaseTrackerCommand,
    ShipmentFormCommand,
    SingleDocumentCommand,
)


class DocumentWorkflowOrchestratorInterface(Protocol):
    """All document workflow entrypoints."""

    async def bank_advice_is_signed(
        self,
        command: SingleDocumentCommand,
    ) -> BankAdviceIsSignedResponse:
        """Run bank advice signature/seal detection."""

    async def costsheet_is_signed(
        self,
        command: SingleDocumentCommand,
    ) -> CostSheetIsSignedResponse:
        """Run cost sheet signature detection."""

    async def tax_invoice_extraction(
        self,
        command: SingleDocumentCommand,
    ) -> TaxInvoiceExtractionResponse:
        """Run tax invoice extraction."""

    async def arrival_notice_extract(
        self,
        command: SingleDocumentCommand,
    ) -> ArrivalNoticeExtractResponse:
        """Run arrival notice extraction."""

    async def boe_extract(
        self,
        command: SingleDocumentCommand,
    ) -> BoeExtractResponse:
        """Run BOE extraction."""

    async def shipment_form(
        self,
        command: ShipmentFormCommand,
    ) -> ShipmentFormResponse:
        """Run shipment form extraction."""

    async def purchase_tracker_fetch_details(
        self,
        command: PurchaseTrackerCommand,
    ) -> EnhancedBillNoExtractionResponse:
        """Run purchase tracker extraction."""

    async def stock_sheet_extract(
        self,
        command: SingleDocumentCommand,
    ) -> StockSheetResponse:
        """Run stock-sheet extraction."""
