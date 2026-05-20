"""Stock-sheet extraction pipeline."""

import asyncio
import time

from src.config.settings import get_settings
from src.core.stock_sheet.constants import CANONICAL_COLUMNS
from src.core.stock_sheet.metadata import (
    build_stock_sheet_metadata,
    merge_extraction_metadata,
)
from src.core.stock_sheet.ocr_textract import TextractTableExtractor
from src.core.stock_sheet.output_builder import build_stock_sheet_response
from src.core.stock_sheet.preprocess import prepare_pages
from src.core.stock_sheet.table_cleaner import maybe_clean_rows
from src.core.stock_sheet.table_parser import map_rows_to_canonical, parse_stock_table
from src.core.stock_sheet.total_row import maybe_repair_total_row
from src.core.stock_sheet.vision_checks import verify_signatures
from src.schemas.stock_sheet import StockSheetResponse


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000.0, 2)


def _cleanup_status(temp_artifacts_deleted: int, *, failed: bool = False) -> str:
    if failed:
        return "partial" if temp_artifacts_deleted else "not_required"
    return "success" if temp_artifacts_deleted else "not_required"


async def run_stock_sheet_pipeline(content: bytes, filename: str) -> StockSheetResponse:
    """Run full stock-sheet extraction and return unified response."""
    settings = get_settings()
    started_at = time.perf_counter()
    usage_parts = []

    try:
        prepared = await prepare_pages(content, filename)
        usage_parts.extend(prepared.orientation_metadata)
    except ValueError as exc:
        metadata = build_stock_sheet_metadata(
            merge_extraction_metadata([], model=settings.model_to_use),
            pipeline_latency_ms=_elapsed_ms(started_at),
            model=settings.model_to_use,
            pages_processed=0,
            cleanup_status="not_required",
            temp_artifacts_deleted=0,
        )
        return build_stock_sheet_response(
            valid=False,
            status="invalid",
            reason=str(exc),
            filename=filename,
            file_type="unknown",
            pages_detected=0,
            pages_processed=0,
            headers=CANONICAL_COLUMNS,
            rows=[],
            signature_check=None,
            metadata=metadata,
        )

    try:
        signature_result, signature_meta = await verify_signatures(prepared.page_images[0])
        usage_parts.append(signature_meta)
        if not bool(signature_result.get("all_signed", False)):
            metadata = build_stock_sheet_metadata(
                merge_extraction_metadata(usage_parts, model=settings.model_to_use),
                pipeline_latency_ms=_elapsed_ms(started_at),
                model=settings.model_to_use,
                pages_processed=len(prepared.page_images),
                cleanup_status=_cleanup_status(prepared.temp_artifacts_deleted),
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
                signature_check=signature_result,
                metadata=metadata,
            )

        extractor = TextractTableExtractor()
        page_tables = await asyncio.gather(
            *(asyncio.to_thread(extractor.extract_tables, page) for page in prepared.page_images)
        )
        merged_tables = [table for tables in page_tables for table in tables]

        headers, rows = parse_stock_table(merged_tables)
        _, cleaned_rows, cleaner_meta = await maybe_clean_rows(
            headers,
            rows,
            CANONICAL_COLUMNS,
            batch_size=settings.stock_sheet_llm_batch_size,
        )
        if cleaner_meta is not None:
            usage_parts.append(cleaner_meta)
        repaired_total_row = await asyncio.to_thread(
            maybe_repair_total_row,
            content=content,
            file_type=prepared.file_type,
            rotation_angle=prepared.rotation_angles[0] if prepared.rotation_angles else 0,
            raw_tables=merged_tables,
            rows=cleaned_rows,
        )
        if repaired_total_row is not None and cleaned_rows:
            cleaned_rows[-1] = repaired_total_row

        metadata = build_stock_sheet_metadata(
            merge_extraction_metadata(usage_parts, model=settings.model_to_use),
            pipeline_latency_ms=_elapsed_ms(started_at),
            model=settings.model_to_use,
            pages_processed=len(prepared.page_images),
            cleanup_status=_cleanup_status(prepared.temp_artifacts_deleted),
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
            signature_check=signature_result,
            metadata=metadata,
        )
    except Exception as exc:
        metadata = build_stock_sheet_metadata(
            merge_extraction_metadata(usage_parts, model=settings.model_to_use),
            pipeline_latency_ms=_elapsed_ms(started_at),
            model=settings.model_to_use,
            pages_processed=len(prepared.page_images),
            cleanup_status=_cleanup_status(prepared.temp_artifacts_deleted, failed=True),
            temp_artifacts_deleted=prepared.temp_artifacts_deleted,
        )
        return build_stock_sheet_response(
            valid=False,
            status="failed",
            reason=f"Extraction failed: {exc}",
            filename=filename,
            file_type=prepared.file_type,
            pages_detected=prepared.pages_detected,
            pages_processed=len(prepared.page_images),
            headers=CANONICAL_COLUMNS,
            rows=[],
            signature_check=None,
            metadata=metadata,
        )
