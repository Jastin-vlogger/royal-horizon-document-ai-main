"""Document workflow dispatcher implementation."""

import json
from typing import Optional

from fastapi import UploadFile

from src.coordination.i_document_workflow_coordinator import (
    DocumentWorkflowCoordinatorInterface,
)
from src.models.domain.documents import (
    DocumentInput,
    PurchaseTrackerCommand,
    ShipmentFormCommand,
    SingleDocumentCommand,
)
from src.models.domain.errors import DomainValidationError


class DocumentWorkflowDispatcher:
    """Convert HTTP upload/form inputs into domain commands."""

    def __init__(self, coordinator: DocumentWorkflowCoordinatorInterface) -> None:
        self._coordinator = coordinator

    @staticmethod
    async def _document_from_upload(upload: UploadFile, *, label: str) -> DocumentInput:
        if not upload or not upload.filename:
            raise DomainValidationError(f"{label} must be provided.")
        content = await upload.read()
        if not content:
            raise DomainValidationError(f"{label} must be provided.")
        return DocumentInput(filename=upload.filename or "unknown", content=content)

    @staticmethod
    def _parse_list_form(value: Optional[str]) -> list[str]:
        if not value or not value.strip():
            return []
        try:
            data = json.loads(value)
            if isinstance(data, list):
                return [str(item) for item in data]
        except json.JSONDecodeError:
            pass
        return [part.strip() for part in value.split(",") if part.strip()]

    async def bank_advice_is_signed(self, file: UploadFile):
        document = await self._document_from_upload(file, label="A file")
        return await self._coordinator.bank_advice_is_signed(
            SingleDocumentCommand(document=document)
        )

    async def costsheet_is_signed(self, file: UploadFile):
        document = await self._document_from_upload(file, label="A file")
        return await self._coordinator.costsheet_is_signed(
            SingleDocumentCommand(document=document)
        )

    async def tax_invoice_extraction(self, file: UploadFile):
        document = await self._document_from_upload(file, label="A file")
        return await self._coordinator.tax_invoice_extraction(
            SingleDocumentCommand(document=document)
        )

    async def arrival_notice_extract(self, file: UploadFile):
        document = await self._document_from_upload(file, label="A file")
        return await self._coordinator.arrival_notice_extract(
            SingleDocumentCommand(document=document)
        )

    async def shipment_form(
        self,
        *,
        lpo_invoice: Optional[UploadFile],
        rice_quality_report: Optional[UploadFile],
        inco_terms_list: Optional[str],
        suppliers: Optional[str],
    ):
        if not (
            lpo_invoice
            and lpo_invoice.filename
            and rice_quality_report
            and rice_quality_report.filename
        ):
            raise DomainValidationError(
                "Both files are required: lpo_invoice, rice_quality_report"
            )
        command = ShipmentFormCommand(
            lpo_invoice=await self._document_from_upload(lpo_invoice, label="LPO"),
            rice_quality_report=await self._document_from_upload(
                rice_quality_report,
                label="Rice Quality Report",
            ),
            inco_terms_list=self._parse_list_form(inco_terms_list),
            suppliers=self._parse_list_form(suppliers),
        )
        return await self._coordinator.shipment_form(command)

    async def purchase_tracker_fetch_details(
        self,
        *,
        file: UploadFile,
        packaging_list_file: Optional[UploadFile],
        packaging_brand: Optional[str],
    ):
        if packaging_list_file and packaging_list_file.filename and not packaging_brand:
            raise DomainValidationError(
                "packaging_brand is required when packaging_list_file is provided."
            )

        packaging_document = None
        if packaging_list_file and packaging_list_file.filename:
            packaging_document = await self._document_from_upload(
                packaging_list_file,
                label="Packaging list file",
            )

        command = PurchaseTrackerCommand(
            bill_document=await self._document_from_upload(
                file,
                label="Bill document file",
            ),
            packaging_list_document=packaging_document,
            packaging_brand=packaging_brand,
        )
        return await self._coordinator.purchase_tracker_fetch_details(command)

    async def stock_sheet_extract(self, file: UploadFile):
        document = await self._document_from_upload(file, label="A file")
        return await self._coordinator.stock_sheet_extract(
            SingleDocumentCommand(document=document)
        )
