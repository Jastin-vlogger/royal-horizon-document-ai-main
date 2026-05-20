"""Tests for purchase-tracker fetch-details API behavior."""

import io

from fastapi.testclient import TestClient

from src.schemas.response import BillOfLadingStructuredExtraction, ExtractionMetadata


def test_fetch_details_loads_three_bill_pages(client: TestClient, monkeypatch):
    """The fetch-details endpoint requests three B/L pages for PDFs."""
    import src.routes.purchase_tracker as purchase_tracker

    calls = {}

    def fake_load_bill_document_pages(content, filename, max_pages=2):
        calls["filename"] = filename
        calls["max_pages"] = max_pages
        return [b"page-1", b"page-2", b"page-3"]

    async def fake_extract_bill_structured(page_images):
        calls["page_count"] = len(page_images)
        extraction = BillOfLadingStructuredExtraction(
            bl_number="AKI0630692",
            shipped_on_board_date="2026-05-02",
            port_of_loading="KARACHI-PAKISTAN",
            port_of_discharge="KHOR AL FAKKAN",
            number_of_containers=0,
            number_of_bags=0,
            quantity_mt=0.0,
            shipping_line="CMA CGM",
            freight_prepaid=False,
            vessel_name="LILA MUMBAI / 0TO3XW1MA",
            invoice_number="MRRM-2026-609",
            containers=[],
        )
        return extraction, ExtractionMetadata(), None

    monkeypatch.setattr(
        purchase_tracker,
        "load_bill_document_pages",
        fake_load_bill_document_pages,
    )
    monkeypatch.setattr(
        purchase_tracker,
        "extract_bill_structured",
        fake_extract_bill_structured,
    )

    response = client.post(
        "/purchase-tracker/fetch-details",
        files={"file": ("bill.pdf", io.BytesIO(b"pdf-bytes"), "application/pdf")},
    )

    assert response.status_code == 200
    assert calls == {
        "filename": "bill.pdf",
        "max_pages": 3,
        "page_count": 3,
    }
