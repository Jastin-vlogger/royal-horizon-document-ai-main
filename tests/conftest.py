"""Pytest fixtures and configuration."""

import os

import pytest
from fastapi.testclient import TestClient


# Ensure tests don't call real OpenAI
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""
    from src.main import app
    return TestClient(app)
