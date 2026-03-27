"""Tests for shipment-form API."""

import io

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from src.main import app
    return TestClient(app)


def test_shipment_form_no_files_returns_400(client: TestClient):
    """Both files are required."""
    response = client.post(
        "/shipment-form",
        data={},
    )
    assert response.status_code == 400
    assert "Both files are required" in response.json().get("detail", "")


def test_shipment_form_invalid_file_type_returns_400(client: TestClient):
    """Invalid file type (e.g. .txt) is rejected."""
    response = client.post(
        "/shipment-form",
        files={
            "lpo_invoice": ("doc.txt", io.BytesIO(b"hello"), "text/plain"),
            "rice_quality_report": ("report.txt", io.BytesIO(b"hello"), "text/plain"),
        },
    )
    assert response.status_code == 400
    assert "PDF or image" in response.json().get("detail", "")
