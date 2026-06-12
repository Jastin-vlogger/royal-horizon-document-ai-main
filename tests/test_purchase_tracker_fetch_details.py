"""Tests for purchase-tracker fetch-details API behavior."""

import io

from fastapi.testclient import TestClient

from src.models.api.response import ExtractionMetadata
from src.models.llm.invocation import LLMInvocationResult


def test_fetch_details_loads_three_bill_pages(client: TestClient, monkeypatch):
    """The fetch-details endpoint requests three B/L pages for PDFs."""

    calls = {}

    def fake_limited_pages_png(self, document, max_pages):
        calls["filename"] = document.filename
        calls["max_pages"] = max_pages
        return [b"page-1", b"page-2", b"page-3"]

    async def fake_vision(self, *, system_prompt, image_bytes_list, user_prompt):
        calls["page_count"] = len(image_bytes_list)
        return LLMInvocationResult(
            content='{"bl_number": "AKI0630692", "containers": []}',
            metadata=ExtractionMetadata(model="gpt-4o"),
        )

    monkeypatch.setattr(
        "src.foundation.document_foundation_impl.DocumentFoundation.limited_pages_png",
        fake_limited_pages_png,
    )
    monkeypatch.setattr(
        "src.foundation.llm_foundation_impl.LLMFoundation.vision",
        fake_vision,
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
