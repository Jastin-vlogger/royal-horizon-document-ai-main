"""Document workflow orchestration implementation."""

import asyncio
import io
import json
import math
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from PIL import Image

from src.config.settings import Settings
from src.foundation.document_foundation_impl import DocumentFoundation
from src.foundation.llm_foundation_impl import LLMFoundation
from src.foundation.ocr_foundation_impl import OCRFoundation
from src.foundation.prompt_foundation_impl import PromptFoundation
from src.models.api.arrival_notice import ArrivalNoticeExtractResponse
from src.models.api.bank_advice_is_signed import BankAdviceIsSignedResponse
from src.models.api.boe import BoeExtractResponse
from src.models.api.costsheet_is_signed import CostSheetIsSignedResponse
from src.models.api.response import (
    EnhancedBillNoExtractionResponse,
    ExtractionMetadata,
    ShipmentFormResponse,
)
from src.models.api.stock_sheet import StockSheetResponse
from src.models.api.tax_invoice import TaxInvoiceExtractionResponse
from src.models.domain.documents import (
    DocumentInput,
    PurchaseTrackerCommand,
    ShipmentFormCommand,
    SingleDocumentCommand,
)
from src.models.domain.errors import (
    ConfigurationError,
    DomainValidationError,
    LLMOutputError,
    ShipmentClassificationError,
)
from src.processing.extractions import (
    build_bill_no_api_response,
    parse_arrival_notice_response,
    parse_bank_advice_response,
    parse_bill_structured_response,
    parse_costsheet_response,
    parse_lpo_invoice_response,
    parse_packaging_list_response,
    parse_rice_quality_response,
    parse_shipment_classification_response,
    parse_stock_sheet_orientation,
    parse_stock_sheet_signature,
    parse_tax_invoice_response,
    sanitize_cleaned_rows,
)
from src.processing.boe import build_boe_vision_images, parse_boe_response
from src.processing.shared.container_matcher import align_containers_to_packaging_list
from src.processing.shared.metadata_aggregator import aggregate_metadata
from src.processing.shipment.shipment_calculations import calculate_shipment_logistics
from src.processing.stock_sheet.constants import CANONICAL_COLUMNS
from src.processing.stock_sheet.metadata import (
    build_stock_sheet_metadata,
    merge_extraction_metadata,
)
from src.processing.stock_sheet.output_builder import build_stock_sheet_response
from src.processing.stock_sheet.table_parser import (
    map_rows_to_canonical,
    parse_stock_table,
)
from src.processing.stock_sheet.total_row import maybe_repair_total_row

ALLOWED_TYPES = {"pdf", "image"}


@dataclass
class PreparedStockPages:
    """Prepared stock-sheet pages."""

    file_type: str
    pages_detected: int
    page_images: list[bytes]
    temp_artifacts_deleted: int = 0
    orientation_metadata: list[ExtractionMetadata] = field(default_factory=list)
    rotation_angles: list[int] = field(default_factory=list)


class DocumentWorkflowOrchestrator:
    """Coordinates document extraction workflows."""

    def __init__(
        self,
        *,
        settings: Settings,
        documents: DocumentFoundation,
        llm: LLMFoundation,
        prompts: PromptFoundation,
        ocr: OCRFoundation,
    ) -> None:
        self._settings = settings
        self._documents = documents
        self._llm = llm
        self._prompts = prompts
        self._ocr = ocr

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((time.perf_counter() - started_at) * 1000.0, 2)

    @staticmethod
    def _aggregate_many(parts: list[ExtractionMetadata]) -> Optional[ExtractionMetadata]:
        if not parts:
            return None
        return ExtractionMetadata(
            input_tokens=sum(part.input_tokens for part in parts),
            output_tokens=sum(part.output_tokens for part in parts),
            total_tokens=sum(part.total_tokens for part in parts),
            cost_incurred=round(sum(part.cost_incurred for part in parts), 6),
            cost_currency=parts[0].cost_currency,
            latency_ms=sum(part.latency_ms for part in parts),
            model=parts[0].model,
        )

    @staticmethod
    def _cleanup_status(temp_artifacts_deleted: int, *, failed: bool = False) -> str:
        if failed:
            return "partial" if temp_artifacts_deleted else "not_required"
        return "success" if temp_artifacts_deleted else "not_required"

    def _validate_type(self, document: DocumentInput, *, label: str) -> str:
        file_type = self._documents.file_type(document)
        if file_type not in ALLOWED_TYPES:
            raise DomainValidationError(
                f"{label} must be PDF or image (jpg, jpeg, png). Got: {document.filename}"
            )
        return file_type

    @staticmethod
    def _require_prompt(value: str, message: str) -> str:
        if not value or not value.strip():
            raise ConfigurationError(message)
        return value.strip()

    def _require_positive_api_int(self, key: str) -> int:
        value = self._prompts.api_config(key)
        if value is None:
            raise ConfigurationError(f"{key} is not configured")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(f"{key} must be an integer") from exc
        if parsed < 1:
            raise ConfigurationError(f"{key} must be at least 1")
        return parsed

    async def _first_page_png(self, document: DocumentInput, *, label: str) -> bytes:
        self._validate_type(document, label=label)
        try:
            return await asyncio.to_thread(self._documents.first_page_png, document)
        except Exception as exc:
            raise DomainValidationError(f"Could not process {label} file: {exc}") from exc

    async def bank_advice_is_signed(
        self,
        command: SingleDocumentCommand,
    ) -> BankAdviceIsSignedResponse:
        image = await self._first_page_png(command.document, label="File")
        result = await self._llm.vision(
            system_prompt=self._prompts.prompt("bank_advice", "system_prompt"),
            image_bytes_list=[image],
            user_prompt=self._prompts.prompt("bank_advice", "user_prompt"),
        )
        try:
            return parse_bank_advice_response(result.content, result.metadata)
        except ValueError as exc:
            raise LLMOutputError(str(exc)) from exc

    async def costsheet_is_signed(
        self,
        command: SingleDocumentCommand,
    ) -> CostSheetIsSignedResponse:
        image = await self._first_page_png(command.document, label="File")
        result = await self._llm.vision(
            system_prompt=self._prompts.prompt("costsheet", "system_prompt"),
            image_bytes_list=[image],
            user_prompt=self._prompts.prompt("costsheet", "user_prompt"),
        )
        try:
            return parse_costsheet_response(result.content, result.metadata)
        except ValueError as exc:
            raise LLMOutputError(str(exc)) from exc

    async def tax_invoice_extraction(
        self,
        command: SingleDocumentCommand,
    ) -> TaxInvoiceExtractionResponse:
        image = await self._first_page_png(command.document, label="File")
        system_prompt = self._require_prompt(
            self._prompts.prompt("tax_invoice", "system_prompt"),
            "tax_invoice system prompt is empty",
        )
        user_prompt = self._require_prompt(
            self._prompts.prompt("tax_invoice", "user_prompt"),
            "tax_invoice user prompt is empty",
        )
        result = await self._llm.vision(
            system_prompt=system_prompt,
            image_bytes_list=[image],
            user_prompt=user_prompt,
        )
        try:
            extraction = parse_tax_invoice_response(result.content)
        except ValueError as exc:
            raise LLMOutputError(str(exc)) from exc
        return TaxInvoiceExtractionResponse(
            tax_invoice_extraction_result=extraction,
            metadata=result.metadata,
        )

    async def arrival_notice_extract(
        self,
        command: SingleDocumentCommand,
    ) -> ArrivalNoticeExtractResponse:
        self._validate_type(command.document, label="File")
        try:
            pages = await asyncio.to_thread(self._documents.all_pages_png, command.document)
        except Exception as exc:
            raise DomainValidationError(f"Could not read document: {exc}") from exc
        system_prompt = self._require_prompt(
            self._prompts.prompt("arrival_notice", "system_prompt"),
            "arrival_notice system prompt is empty",
        )
        result = await self._llm.vision(
            system_prompt=system_prompt,
            image_bytes_list=pages,
            user_prompt=self._prompts.prompt("arrival_notice", "user_prompt"),
        )
        try:
            return parse_arrival_notice_response(result.content, result.metadata)
        except ValueError as exc:
            raise LLMOutputError(str(exc)) from exc

    async def boe_extract(
        self,
        command: SingleDocumentCommand,
    ) -> BoeExtractResponse:
        file_type = self._validate_type(command.document, label="File")
        max_pages = self._require_positive_api_int("boe.pdf_max_pages")

        try:
            if file_type == "pdf":
                pages_detected = await asyncio.to_thread(
                    self._documents.pdf_page_count,
                    command.document,
                )
                if pages_detected > max_pages:
                    raise DomainValidationError("PDF exceeds maximum allowed pages")
                pages = await asyncio.to_thread(
                    self._documents.limited_pages_png,
                    command.document,
                    max_pages,
                )
            else:
                pages = [
                    await asyncio.to_thread(
                        self._documents.first_page_png,
                        command.document,
                    )
                ]
        except DomainValidationError:
            raise
        except Exception as exc:
            raise DomainValidationError(f"Could not read document: {exc}") from exc

        system_prompt = self._require_prompt(
            self._prompts.prompt("boe", "system_prompt"),
            "boe system prompt is empty",
        )
        user_prompt = self._require_prompt(
            self._prompts.prompt("boe", "user_prompt"),
            "boe user prompt is empty",
        )
        result = await self._llm.vision(
            system_prompt=system_prompt,
            image_bytes_list=build_boe_vision_images(pages),
            user_prompt=user_prompt,
        )
        try:
            return parse_boe_response(result.content, result.metadata)
        except ValueError as exc:
            raise LLMOutputError(str(exc)) from exc

    async def _extract_lpo(
        self,
        image: bytes,
        *,
        inco_terms: list[str],
        suppliers: list[str],
    ):
        result = await self._llm.vision(
            system_prompt=self._prompts.lpo_system_prompt(
                inco_terms=inco_terms,
                suppliers=suppliers,
            ),
            image_bytes_list=[image],
            user_prompt=self._prompts.prompt("lpo_invoice", "user_prompt"),
        )
        return parse_lpo_invoice_response(result.content, inco_terms), result.metadata

    async def _extract_rice_quality(self, image: bytes):
        result = await self._llm.vision(
            system_prompt=self._prompts.prompt("rice_quality_report", "system_prompt"),
            image_bytes_list=[image],
            user_prompt=self._prompts.prompt("rice_quality_report", "user_prompt"),
        )
        return parse_rice_quality_response(result.content), result.metadata

    async def shipment_form(
        self,
        command: ShipmentFormCommand,
    ) -> ShipmentFormResponse:
        inco_terms = command.inco_terms_list or list(
            self._prompts.api_config(
                "shipment_form.default_inco_terms",
                ["CIF", "FOB", "EXWORKS", "C&F"],
            )
        )

        lpo_png, rice_png = await asyncio.gather(
            self._first_page_png(command.lpo_invoice, label="LPO"),
            self._first_page_png(command.rice_quality_report, label="Rice Quality Report"),
        )

        classification = await self._llm.vision(
            system_prompt=self._prompts.prompt("shipment_classification", "system_prompt"),
            image_bytes_list=[lpo_png, rice_png],
            user_prompt=self._prompts.prompt("shipment_classification", "user_prompt"),
        )
        classified_data = parse_shipment_classification_response(classification.content)
        metadata_parts = [classification.metadata]

        if not classified_data.get("is_valid_document"):
            raise ShipmentClassificationError(classified_data)

        try:
            (lpo_result, lpo_meta), (rice_data, rice_meta) = await asyncio.gather(
                self._extract_lpo(
                    lpo_png,
                    inco_terms=inco_terms,
                    suppliers=command.suppliers,
                ),
                self._extract_rice_quality(rice_png),
            )
        except ValueError as exc:
            raise LLMOutputError(str(exc)) from exc

        metadata_parts.extend([lpo_meta, rice_meta])
        aggregated = self._aggregate_many(metadata_parts)
        combined = {
            "lpo_invoice": lpo_result.model_dump(exclude_none=False)
            if lpo_result
            else None,
            "metadata": aggregated.model_dump() if aggregated else None,
        }
        shipment_calculations = calculate_shipment_logistics(combined).get(
            "shipment_calculations"
        )
        return ShipmentFormResponse(
            lpo_invoice=lpo_result,
            metadata=aggregated,
            shipment_calculations=shipment_calculations,
            classified_data=classified_data,
            s1_quality_report=rice_data,
        )

    async def purchase_tracker_fetch_details(
        self,
        command: PurchaseTrackerCommand,
    ) -> EnhancedBillNoExtractionResponse:
        self._validate_type(command.bill_document, label="Bill file")
        max_pages = int(
            self._prompts.api_config("purchase_tracker.bill_fetch_details_max_pages", 3)
        )
        try:
            bill_pages = await asyncio.to_thread(
                self._documents.limited_pages_png,
                command.bill_document,
                max_pages,
            )
        except Exception as exc:
            raise DomainValidationError(f"Could not read bill document pages: {exc}") from exc

        bill_result = await self._llm.vision(
            system_prompt=self._prompts.prompt("purchase_tracker_bill_no", "system_prompt"),
            image_bytes_list=bill_pages,
            user_prompt=self._prompts.bill_user_prompt(len(bill_pages)),
        )
        bill_extraction, bill_parse_error = parse_bill_structured_response(
            bill_result.content
        )
        bill_response = build_bill_no_api_response(bill_extraction, bill_result.metadata)

        packaging_extraction = None
        packaging_metadata = None
        if command.packaging_list_document and command.packaging_brand:
            self._validate_type(
                command.packaging_list_document,
                label="Packaging list file",
            )
            pkg_max_pages = int(
                self._prompts.api_config("purchase_tracker.packaging_list_max_pages", 2)
            )
            try:
                pkg_pages = await asyncio.to_thread(
                    self._documents.strict_limited_pages_png,
                    command.packaging_list_document,
                    pkg_max_pages,
                )
            except Exception as exc:
                raise DomainValidationError(f"Packaging list error: {exc}") from exc

            pkg_result = await self._llm.vision(
                system_prompt=self._prompts.prompt("packaging_list", "system_prompt"),
                image_bytes_list=pkg_pages,
                user_prompt=self._prompts.packaging_list_user_prompt(
                    command.packaging_brand.strip()
                ),
            )
            packaging_extraction, _pkg_parse_error = parse_packaging_list_response(
                pkg_result.content
            )
            packaging_metadata = pkg_result.metadata

        if packaging_extraction and packaging_extraction.container_number_list:
            bill_response.containers = align_containers_to_packaging_list(
                bill_containers=bill_response.containers,
                packaging_containers=packaging_extraction.container_info,
                fuzzy_threshold=0.85,
            )

        final_metadata = (
            aggregate_metadata(bill_result.metadata, packaging_metadata)
            if packaging_metadata
            else bill_result.metadata
        )
        return EnhancedBillNoExtractionResponse(
            bill_extracted_data=bill_response.model_dump(exclude={"metadata"}),
            packaging_list=packaging_extraction.model_dump()
            if packaging_extraction
            else None,
            metadata=final_metadata,
        )

    def _stock_failure_response(
        self,
        *,
        started_at: float,
        filename: str,
        file_type: str,
        pages_detected: int,
        pages_processed: int,
        status: str,
        reason: str,
        usage_parts: list[ExtractionMetadata],
        temp_artifacts_deleted: int = 0,
        failed: bool = False,
    ) -> StockSheetResponse:
        metadata = build_stock_sheet_metadata(
            merge_extraction_metadata(usage_parts, model=self._settings.model_to_use),
            pipeline_latency_ms=self._elapsed_ms(started_at),
            model=self._settings.model_to_use,
            pages_processed=pages_processed,
            cleanup_status=self._cleanup_status(temp_artifacts_deleted, failed=failed),
            temp_artifacts_deleted=temp_artifacts_deleted,
        )
        return build_stock_sheet_response(
            valid=False,
            status=status,
            reason=reason,
            filename=filename,
            file_type=file_type,
            pages_detected=pages_detected,
            pages_processed=pages_processed,
            headers=CANONICAL_COLUMNS,
            rows=[],
            signature_check=None,
            metadata=metadata,
        )

    @staticmethod
    def _rotate_png_bytes(image_bytes: bytes, clockwise_degrees: int) -> bytes:
        if clockwise_degrees == 0:
            return image_bytes
        image = Image.open(io.BytesIO(image_bytes))
        rotated = image.rotate(-clockwise_degrees, expand=True)
        if rotated.mode in ("RGBA", "P"):
            rotated = rotated.convert("RGB")
        buffer = io.BytesIO()
        rotated.save(buffer, format="PNG")
        return buffer.getvalue()

    def _validate_stock_image_pixels(self, document: DocumentInput) -> None:
        image = Image.open(io.BytesIO(document.content))
        if image.width * image.height > self._settings.stock_sheet_max_image_pixels:
            raise ValueError(
                f"Image dimensions exceed max allowed pixels ({self._settings.stock_sheet_max_image_pixels})."
            )

    async def _prepare_stock_pages(
        self,
        document: DocumentInput,
    ) -> PreparedStockPages:
        file_type = self._documents.file_type(document)
        if file_type == "unknown":
            raise ValueError("Unsupported file type. Allowed: PDF, JPG, JPEG, PNG.")

        if file_type == "pdf":
            pages_detected = await asyncio.to_thread(
                self._documents.pdf_page_count,
                document,
            )
            if pages_detected > self._settings.stock_sheet_pdf_max_pages:
                raise ValueError(
                    f"PDF has {pages_detected} pages; max allowed is {self._settings.stock_sheet_pdf_max_pages}."
                )
            images = await asyncio.to_thread(
                self._documents.limited_pages_png,
                document,
                self._settings.stock_sheet_pdf_max_pages,
            )
        else:
            await asyncio.to_thread(self._validate_stock_image_pixels, document)
            pages_detected = 1
            images = [await asyncio.to_thread(self._documents.first_page_png, document)]

        orientation_metadata: list[ExtractionMetadata] = []
        rotation_angles = [0 for _ in images]
        if self._settings.stock_sheet_enable_preprocess and images:
            orientation_prompt = self._prompts.prompt("stock_sheet", "orientation_prompt")
            orientation_results = await asyncio.gather(
                *[
                    self._llm.vision(
                        system_prompt=orientation_prompt,
                        image_bytes_list=[page],
                        user_prompt="Analyze the orientation and return the JSON.",
                    )
                    for page in images
                ]
            )
            rotation_angles = [
                parse_stock_sheet_orientation(result.content)
                for result in orientation_results
            ]
            orientation_metadata = [result.metadata for result in orientation_results]
            images = await asyncio.gather(
                *[
                    asyncio.to_thread(self._rotate_png_bytes, image, angle)
                    for image, angle in zip(images, rotation_angles)
                ]
            )

        return PreparedStockPages(
            file_type=file_type,
            pages_detected=pages_detected,
            page_images=images,
            orientation_metadata=orientation_metadata,
            rotation_angles=rotation_angles,
        )

    async def _clean_stock_rows(
        self,
        headers: list[str],
        rows: list[dict[str, Any]],
    ) -> tuple[list[str], list[dict[str, Any]], ExtractionMetadata | None]:
        if not rows:
            return headers, rows, None
        batch_size = max(1, self._settings.stock_sheet_llm_batch_size)
        batches = [rows[index : index + batch_size] for index in range(0, len(rows), batch_size)]
        cleaner_prompt = self._prompts.stock_sheet_cleaner_prompt(CANONICAL_COLUMNS)
        results = await asyncio.gather(
            *[
                self._llm.text(
                    system_prompt=cleaner_prompt,
                    user_prompt=json.dumps(
                        {"headers": headers, "rows": batch},
                        ensure_ascii=True,
                    ),
                )
                for batch in batches
            ]
        )
        cleaned_batches = [
            sanitize_cleaned_rows(
                result.content,
                fallback_headers=headers,
                fallback_rows=batch,
            )
            for result, batch in zip(results, batches)
        ]
        cleaned_headers = cleaned_batches[0][0] if cleaned_batches else headers
        cleaned_rows = [row for _, batch_rows in cleaned_batches for row in batch_rows]
        metadata = self._aggregate_many([result.metadata for result in results])
        return cleaned_headers, cleaned_rows or rows, metadata

    async def stock_sheet_extract(
        self,
        command: SingleDocumentCommand,
    ) -> StockSheetResponse:
        started_at = time.perf_counter()
        usage_parts: list[ExtractionMetadata] = []
        filename = command.document.filename or "unknown"

        try:
            prepared = await self._prepare_stock_pages(command.document)
            usage_parts.extend(prepared.orientation_metadata)
        except ValueError as exc:
            return self._stock_failure_response(
                started_at=started_at,
                filename=filename,
                file_type="unknown",
                pages_detected=0,
                pages_processed=0,
                status="invalid",
                reason=str(exc),
                usage_parts=usage_parts,
            )

        try:
            signature_result = await self._llm.vision(
                system_prompt=self._prompts.prompt("stock_sheet", "signature_prompt"),
                image_bytes_list=[prepared.page_images[0]],
                user_prompt="Check all three signature fields and return JSON.",
            )
            signature_check = parse_stock_sheet_signature(signature_result.content)
            usage_parts.append(signature_result.metadata)

            if not bool(signature_check.get("all_signed", False)):
                metadata = build_stock_sheet_metadata(
                    merge_extraction_metadata(usage_parts, model=self._settings.model_to_use),
                    pipeline_latency_ms=self._elapsed_ms(started_at),
                    model=self._settings.model_to_use,
                    pages_processed=len(prepared.page_images),
                    cleanup_status=self._cleanup_status(prepared.temp_artifacts_deleted),
                    temp_artifacts_deleted=prepared.temp_artifacts_deleted,
                )
                return build_stock_sheet_response(
                    valid=False,
                    status="invalid",
                    reason="Document is unsigned: Prepared By, Reviewed By, and Approved By signatures are required.",
                    filename=filename,
                    file_type=prepared.file_type,
                    pages_detected=prepared.pages_detected,
                    pages_processed=len(prepared.page_images),
                    headers=CANONICAL_COLUMNS,
                    rows=[],
                    signature_check=signature_check,
                    metadata=metadata,
                )

            page_tables = await asyncio.gather(
                *[
                    asyncio.to_thread(self._ocr.extract_tables, page)
                    for page in prepared.page_images
                ]
            )
            merged_tables = [table for tables in page_tables for table in tables]
            headers, rows = parse_stock_table(merged_tables)
            _cleaned_headers, cleaned_rows, cleaner_meta = await self._clean_stock_rows(
                headers,
                rows,
            )
            if cleaner_meta is not None:
                usage_parts.append(cleaner_meta)

            repaired_total_row = await asyncio.to_thread(
                maybe_repair_total_row,
                content=command.document.content,
                file_type=prepared.file_type,
                rotation_angle=prepared.rotation_angles[0]
                if prepared.rotation_angles
                else 0,
                raw_tables=merged_tables,
                rows=cleaned_rows,
                extract_tables=self._ocr.extract_tables,
            )
            if repaired_total_row is not None and cleaned_rows:
                cleaned_rows[-1] = repaired_total_row

            metadata = build_stock_sheet_metadata(
                merge_extraction_metadata(usage_parts, model=self._settings.model_to_use),
                pipeline_latency_ms=self._elapsed_ms(started_at),
                model=self._settings.model_to_use,
                pages_processed=len(prepared.page_images),
                cleanup_status=self._cleanup_status(prepared.temp_artifacts_deleted),
                temp_artifacts_deleted=prepared.temp_artifacts_deleted,
            )
            return build_stock_sheet_response(
                valid=True,
                status="processed",
                reason=None,
                filename=filename,
                file_type=prepared.file_type,
                pages_detected=prepared.pages_detected,
                pages_processed=len(prepared.page_images),
                headers=CANONICAL_COLUMNS,
                rows=map_rows_to_canonical(cleaned_rows),
                signature_check=signature_check,
                metadata=metadata,
            )
        except Exception as exc:
            return self._stock_failure_response(
                started_at=started_at,
                filename=filename,
                file_type=prepared.file_type,
                pages_detected=prepared.pages_detected,
                pages_processed=len(prepared.page_images),
                status="failed",
                reason=f"Extraction failed: {exc}",
                usage_parts=usage_parts,
                temp_artifacts_deleted=prepared.temp_artifacts_deleted,
                failed=True,
            )
