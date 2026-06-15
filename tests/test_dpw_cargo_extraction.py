"""Tests for DPW cargo receipt extraction utilities."""

import io

import pytest
from PIL import Image

from src.models.api.response import ExtractionMetadata
from src.processing.dpw_cargo import (
    build_dpw_cargo_vision_images,
    normalize_dpw_container_values,
    normalize_dpw_date,
    normalize_receipt_no,
    parse_dpw_cargo_response,
)


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (1000, 1200), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_normalize_dpw_container_values_deduplicates_and_accepts_dpw_shape():
    containers = normalize_dpw_container_values(
        [
            "Container DPWU200491",
            "Container DPWU 200491",
            "Container MSKU1234567",
            "CONTAINERS TaxCode(AE_VAT_AR_11)",
            "Container BAD123",
            "Container bsiu314828",
        ]
    )

    assert containers == ["DPWU200491", "MSKU1234567", "BSIU314828"]


def test_normalize_dpw_container_values_returns_empty_for_missing_values():
    assert normalize_dpw_container_values(None) == []
    assert normalize_dpw_container_values("Container") == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("08/06/2026 13:30", "08/06/2026"),
        ("Date : 15-06-2026", "15/06/2026"),
        ("2026-06-15", "15/06/2026"),
    ],
)
def test_normalize_dpw_date(raw: str, expected: str):
    assert normalize_dpw_date(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "null", "2026/15/06", "32/01/2026"])
def test_normalize_dpw_date_returns_none_for_invalid_values(raw):
    assert normalize_dpw_date(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Receipt No : 56710421", "56710421"),
        ("BOL No : MUN KLF26139815", "MUNKLF26139815"),
        (" MUNKLF26139815 ", "MUNKLF26139815"),
    ],
)
def test_normalize_receipt_no(raw: str, expected: str):
    assert normalize_receipt_no(raw) == expected


def test_parse_dpw_cargo_response_normalizes_model_payload():
    response = parse_dpw_cargo_response(
        """
        ```json
        {
          "date": "08/06/2026 13:30",
          "containers": "Container DPWU200491\\nContainer DPWU200491\\nContainer MSKU1234567",
          "receipt_no": "Receipt No : 56710421"
        }
        ```
        """,
        ExtractionMetadata(total_tokens=9, model="gpt-4o"),
        pages_processed=6,
    )

    assert response.date == "08/06/2026"
    assert response.containers == ["DPWU200491", "MSKU1234567"]
    assert response.total_containers == 2
    assert response.pages_processed == 6
    assert response.receipt_no == "56710421"
    assert response.metadata is not None
    assert response.metadata.total_tokens == 9
    assert response.error is None


def test_build_dpw_cargo_vision_images_uses_header_and_page_crops():
    images = build_dpw_cargo_vision_images([_png_bytes(), _png_bytes()])

    assert len(images) == 3
    assert all(image.startswith(b"\x89PNG") for image in images)
