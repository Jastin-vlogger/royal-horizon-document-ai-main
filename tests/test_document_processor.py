"""Tests for document processing (file type, PDF to image)."""

import io

import pytest
from PIL import Image

from src.core.document_processor import (
    detect_file_type,
    is_image,
    is_pdf,
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
