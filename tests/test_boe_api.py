"""Tests for BOE extraction API behavior."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from src.models.api.response import ExtractionMetadata
from src.models.llm.invocation import LLMInvocationResult


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (1000, 1200), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_boe_extract_success_response_shape(client: TestClient, monkeypatch):
    calls = {}

    def fake_pdf_page_count(self, document):
        calls["page_count_filename"] = document.filename
        return 2

    def fake_limited_pages_png(self, document, max_pages):
        calls["render_filename"] = document.filename
        calls["max_pages"] = max_pages
        return [_png_bytes(), _png_bytes()]

    async def fake_vision(self, *, system_prompt, image_bytes_list, user_prompt):
        calls["vision_pages"] = len(image_bytes_list)
        calls["has_boe_prompt"] = "MARKS & NUMBERS" in system_prompt
        return LLMInvocationResult(
            content='{"containers": ["CBHU3475526", "CLHU3820005"], "date": "19-01-2026"}',
            metadata=ExtractionMetadata(total_tokens=42, model="gpt-4o"),
        )

    monkeypatch.setattr(
        "src.foundation.document_foundation_impl.DocumentFoundation.pdf_page_count",
        fake_pdf_page_count,
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
        "/boe/extract",
        files={"file": ("boe.pdf", io.BytesIO(b"pdf-bytes"), "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "containers": ["CBHU3475526", "CLHU3820005"],
        "date": "19/01/2026",
    }
    assert body["metadata"]["total_tokens"] == 42
    assert calls == {
        "page_count_filename": "boe.pdf",
        "render_filename": "boe.pdf",
        "max_pages": 2,
        "vision_pages": 6,
        "has_boe_prompt": True,
    }


def test_boe_extract_pdf_threshold_returns_boe_validation_body(
    client: TestClient,
    monkeypatch,
):
    calls = {}

    def fake_pdf_page_count(self, document):
        calls["page_count_filename"] = document.filename
        return 3

    def fail_limited_pages_png(self, document, max_pages):
        raise AssertionError("PDF should not be rendered when over the BOE page limit")

    async def fail_vision(self, *, system_prompt, image_bytes_list, user_prompt):
        raise AssertionError("LLM should not be called when BOE PDF is over the limit")

    monkeypatch.setattr(
        "src.foundation.document_foundation_impl.DocumentFoundation.pdf_page_count",
        fake_pdf_page_count,
    )
    monkeypatch.setattr(
        "src.foundation.document_foundation_impl.DocumentFoundation.limited_pages_png",
        fail_limited_pages_png,
    )
    monkeypatch.setattr(
        "src.foundation.llm_foundation_impl.LLMFoundation.vision",
        fail_vision,
    )

    response = client.post(
        "/boe/extract",
        files={"file": ("boe.pdf", io.BytesIO(b"pdf-bytes"), "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "success": False,
        "message": "PDF exceeds maximum allowed pages",
    }
    assert calls == {"page_count_filename": "boe.pdf"}


def test_boe_extract_invalid_file_type_returns_boe_validation_body(client: TestClient):
    response = client.post(
        "/boe/extract",
        files={"file": ("boe.txt", io.BytesIO(b"hello"), "text/plain")},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert "PDF or image" in body["message"]
