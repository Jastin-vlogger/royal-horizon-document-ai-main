"""Document workflow coordinator implementation."""

from src.models.domain.documents import (
    PurchaseTrackerCommand,
    ShipmentFormCommand,
    SingleDocumentCommand,
)
from src.orchestration.i_document_workflow_orchestrator import (
    DocumentWorkflowOrchestratorInterface,
)


class DocumentWorkflowCoordinator:
    """V1 coordinator: one orchestrator, stable future coordination seam."""

    def __init__(
        self,
        orchestrator: DocumentWorkflowOrchestratorInterface,
    ) -> None:
        self._orchestrator = orchestrator

    async def bank_advice_is_signed(self, command: SingleDocumentCommand):
        return await self._orchestrator.bank_advice_is_signed(command)

    async def costsheet_is_signed(self, command: SingleDocumentCommand):
        return await self._orchestrator.costsheet_is_signed(command)

    async def tax_invoice_extraction(self, command: SingleDocumentCommand):
        return await self._orchestrator.tax_invoice_extraction(command)

    async def arrival_notice_extract(self, command: SingleDocumentCommand):
        return await self._orchestrator.arrival_notice_extract(command)

    async def boe_extract(self, command: SingleDocumentCommand):
        return await self._orchestrator.boe_extract(command)

    async def dpw_cargo_extract(self, command: SingleDocumentCommand):
        return await self._orchestrator.dpw_cargo_extract(command)

    async def shipment_form(self, command: ShipmentFormCommand):
        return await self._orchestrator.shipment_form(command)

    async def purchase_tracker_fetch_details(self, command: PurchaseTrackerCommand):
        return await self._orchestrator.purchase_tracker_fetch_details(command)

    async def stock_sheet_extract(self, command: SingleDocumentCommand):
        return await self._orchestrator.stock_sheet_extract(command)
