"""Tests for DPW cargo receipt API behavior."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from src.models.api.response import ExtractionMetadata
from src.models.llm.invocation import LLMInvocationResult


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (1000, 1200), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_dpw_cargo_extractor_success_response_shape(
    client: TestClient,
    monkeypatch,
):
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
        calls["has_dpw_prompt"] = "DP World cargo receipt" in system_prompt
        return LLMInvocationResult(
            content=(
                '{"date": "08/06/2026 13:30", '
                '"containers": ["Container DPWU200491", "MSKU1234567", "DPWU200491"], '
                '"receipt_no": "Receipt No : 56710421"}'
            ),
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
        "/dpw-cargo-extractor",
        files={"file": ("dpw.pdf", io.BytesIO(b"pdf-bytes"), "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "date": "08/06/2026",
        "containers": ["DPWU200491", "MSKU1234567"],
        "total_containers": 2,
        "pages_processed": 2,
        "receipt_no": "56710421",
        "metadata": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 42,
            "cost_incurred": 0.0,
            "cost_currency": "USD",
            "latency_ms": 0.0,
            "model": "gpt-4o",
        },
        "error": None,
    }
    assert calls == {
        "page_count_filename": "dpw.pdf",
        "render_filename": "dpw.pdf",
        "max_pages": 10,
        "vision_pages": 3,
        "has_dpw_prompt": True,
    }


def test_dpw_cargo_extractor_pdf_threshold_returns_contract_error(
    client: TestClient,
    monkeypatch,
):
    calls = {}

    def fake_pdf_page_count(self, document):
        calls["page_count_filename"] = document.filename
        return 11

    def fail_limited_pages_png(self, document, max_pages):
        raise AssertionError("PDF should not be rendered when over the DPW page limit")

    async def fail_vision(self, *, system_prompt, image_bytes_list, user_prompt):
        raise AssertionError("LLM should not be called when PDF is over the limit")

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
        "/dpw-cargo-extractor",
        files={"file": ("dpw.pdf", io.BytesIO(b"pdf-bytes"), "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "date": None,
        "containers": None,
        "total_containers": None,
        "pages_processed": None,
        "receipt_no": None,
        "metadata": None,
        "error": "PDF exceeds maximum allowed pages",
    }
    assert calls == {"page_count_filename": "dpw.pdf"}


def test_dpw_cargo_extractor_invalid_file_type_returns_contract_error(
    client: TestClient,
):
    response = client.post(
        "/dpw-cargo-extractor",
        files={"file": ("dpw.txt", io.BytesIO(b"hello"), "text/plain")},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["date"] is None
    assert body["metadata"] is None
    assert "PDF" in body["error"]
