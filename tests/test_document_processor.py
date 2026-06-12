"""Tests for document processing (file type, PDF to image)."""

import io

import pytest
from PIL import Image

import src.brokers.document_render_broker as document_processor
from src.brokers.document_render_broker import (
    detect_file_type,
    is_image,
    is_pdf,
    load_bill_document_pages,
    load_image_bytes,
)


def test_detect_file_type():
    assert detect_file_type("doc.pdf") == "pdf"
    assert detect_file_type("x.JPG") == "image"
    assert detect_file_type("y.PNG") == "image"
    assert detect_file_type("z.jpeg") == "image"
    assert detect_file_type("unknown.xyz") == "unknown"


def test_is_pdf():
    assert is_pdf("a.pdf") is True
    assert is_pdf("a.jpg") is False


def test_is_image():
    assert is_image("a.jpg") is True
    assert is_image("a.png") is True
    assert is_image("a.pdf") is False


def test_load_image_bytes_from_png():
    """PNG bytes are normalized to PNG."""
    buf = io.BytesIO()
    img = Image.new("RGB", (10, 10), color="red")
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    out = load_image_bytes(png_bytes, "test.png")
    assert out[:8] == b"\x89PNG\r\n\x1a\n"


def test_load_bill_document_pages_defaults_to_two_pdf_pages(monkeypatch):
    """B/L PDF loading keeps the existing two-page default."""
    calls = {}

    def fake_pdf_pages_to_png_images(content, first_page=1, last_page=2):
        calls["content"] = content
        calls["first_page"] = first_page
        calls["last_page"] = last_page
        return [b"page-1", b"page-2"]

    monkeypatch.setattr(
        document_processor,
        "pdf_pages_to_png_images",
        fake_pdf_pages_to_png_images,
    )

    pages = load_bill_document_pages(b"pdf-bytes", "bill.pdf")

    assert pages == [b"page-1", b"page-2"]
    assert calls == {"content": b"pdf-bytes", "first_page": 1, "last_page": 2}


def test_load_bill_document_pages_accepts_custom_pdf_limit(monkeypatch):
    """fetch-details can request three B/L pages without changing the default."""
    calls = {}

    def fake_pdf_pages_to_png_images(content, first_page=1, last_page=2):
        calls["first_page"] = first_page
        calls["last_page"] = last_page
        return [b"page-1", b"page-2", b"page-3"]

    monkeypatch.setattr(
        document_processor,
        "pdf_pages_to_png_images",
        fake_pdf_pages_to_png_images,
    )

    pages = load_bill_document_pages(b"pdf-bytes", "bill.pdf", max_pages=3)

    assert pages == [b"page-1", b"page-2", b"page-3"]
    assert calls == {"first_page": 1, "last_page": 3}
