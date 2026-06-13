"""Tests for BOE extraction parsing utilities."""

import io

import pytest
from PIL import Image

from src.models.api.response import ExtractionMetadata
from src.processing.boe import (
    build_boe_vision_images,
    normalize_boe_date,
    normalize_container_values,
    parse_boe_response,
)


def test_normalize_container_values_handles_multiline_commas_and_duplicates():
    containers = normalize_container_values(
        [
            "Container Nos:\nCBHU3475526, CLHU 3820005,\nDVRU1599581",
            "CBHU3475526",
            " GLDU5290979 ",
        ]
    )

    assert containers == [
        "CBHU3475526",
        "CLHU3820005",
        "DVRU1599581",
        "GLDU5290979",
    ]


def test_normalize_container_values_returns_empty_for_missing_values():
    assert normalize_container_values(None) == []
    assert normalize_container_values("Container Nos:") == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("19/01/2026", "19/01/2026"),
        ("DCE DATE : 19-01-2026", "19/01/2026"),
        (" 01/02/2026 ", "01/02/2026"),
    ],
)
def test_normalize_boe_date(raw: str, expected: str):
    assert normalize_boe_date(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "null", "2026/01/19", "32/01/2026"])
def test_normalize_boe_date_returns_none_for_invalid_values(raw):
    assert normalize_boe_date(raw) is None


def test_parse_boe_response_normalizes_model_payload():
    response = parse_boe_response(
        """
        ```json
        {
          "containers": "Container Nos:\\nCBHU3475526, CLHU3820005,\\nCBHU3475526",
          "date": "19-01-2026"
        }
        ```
        """,
        ExtractionMetadata(total_tokens=5, model="gpt-4o"),
    )

    assert response.success is True
    assert response.data.containers == ["CBHU3475526", "CLHU3820005"]
    assert response.data.date == "19/01/2026"
    assert response.metadata.total_tokens == 5


def test_build_boe_vision_images_adds_zoom_crops():
    image = Image.new("RGB", (1000, 1200), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    images = build_boe_vision_images([buffer.getvalue()])

    assert len(images) == 3
    assert images[0] == buffer.getvalue()
