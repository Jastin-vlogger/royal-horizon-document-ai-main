"""Tests for stock-sheet extraction endpoint."""

import io

from fastapi.testclient import TestClient

from src.processing.stock_sheet.constants import CANONICAL_COLUMNS
from src.models.api.stock_sheet import (
    StockSheetData,
    StockSheetFileInfo,
    StockSheetMetadata,
    StockSheetRow,
    StockSheetResponse,
)


def test_stock_sheet_invalid_file_returns_unified_invalid(client: TestClient):
    response = client.post(
        "/extract/stock-sheet",
        files={"file": ("data.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["status"] == "invalid"
    assert "Unsupported file type" in (body["reason"] or "")


def test_stock_sheet_success_response_shape(client: TestClient, monkeypatch):
    async def _fake_pipeline(self, file) -> StockSheetResponse:
        return StockSheetResponse(
            valid=True,
            status="processed",
            reason=None,
            file_info=StockSheetFileInfo(
                filename=file.filename,
                file_type="image",
                pages_detected=1,
                pages_processed=1,
            ),
            data=StockSheetData(
                headers=CANONICAL_COLUMNS,
                rows=[
                    StockSheetRow.model_validate(
                        {
                            "Unit": 20,
                            "Abu Dhabi Musaffah": 30,
                            "ALAin Mazyad": 3877,
                            "Total Bags": 4317,
                        }
                    )
                ],
                total_rows=1,
            ),
            metadata=StockSheetMetadata(
                input_tokens=2,
                output_tokens=3,
                total_tokens=5,
                cost_incurred=0.00001,
                model="gpt-4o",
                pages_processed=1,
                cleanup_status="not_required",
                temp_artifacts_deleted=0,
            ),
        )

    monkeypatch.setattr("src.dispatchers.document_workflow_dispatcher_impl.DocumentWorkflowDispatcher.stock_sheet_extract", _fake_pipeline)
    response = client.post(
        "/extract/stock-sheet",
        files={"file": ("sheet.png", io.BytesIO(b"fakepng"), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["status"] == "processed"
    assert body["metadata"]["total_tokens"] == 5
    assert body["metadata"]["cleanup_status"] == "not_required"
    assert body["data"]["rows"][0]["Unit"] == 20
    assert body["data"]["rows"][0]["Total Bags"] == 4317


def test_stock_sheet_pdf_threshold_returns_invalid(client: TestClient, monkeypatch):
    async def _fake_pipeline(self, file) -> StockSheetResponse:
        return StockSheetResponse(
            valid=False,
            status="invalid",
            reason="PDF has 5 pages; max allowed is 3.",
            file_info=StockSheetFileInfo(
                filename=file.filename,
                file_type="pdf",
                pages_detected=5,
                pages_processed=0,
            ),
            data=StockSheetData(headers=[], rows=[], total_rows=0),
            metadata=StockSheetMetadata(model="gpt-4o"),
        )

    monkeypatch.setattr("src.dispatchers.document_workflow_dispatcher_impl.DocumentWorkflowDispatcher.stock_sheet_extract", _fake_pipeline)
    response = client.post(
        "/extract/stock-sheet",
        files={"file": ("sheet.pdf", io.BytesIO(b"%PDF-1.4 mock"), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["status"] == "invalid"
    assert "max allowed" in body["reason"]
