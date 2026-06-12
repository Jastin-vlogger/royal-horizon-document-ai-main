"""Prompt foundation interface."""

from typing import Any, Protocol


class PromptFoundationInterface(Protocol):
    """Domain prompt/config operations."""

    def prompt(self, prompt_file: str, key: str) -> str:
        """Return a prompt by key."""

    def api_config(self, key: str, default: Any = None) -> Any:
        """Return API config by dotted path."""
