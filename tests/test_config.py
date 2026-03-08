"""Tests for config and settings."""

import os

import pytest


def test_settings_load_from_env(monkeypatch):
    """Settings load from environment."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    # Clear cache to pick up new env
    from src.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    assert s.openai_api_key == "sk-test"
    assert s.port == 9000
    assert s.log_level == "DEBUG"
    get_settings.cache_clear()
