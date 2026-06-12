"""Prompt/config broker interface."""

from typing import Any, Protocol


class PromptConfigBrokerInterface(Protocol):
    """Prompt and API config access."""

    def prompt(self, prompt_file: str, key: str) -> str:
        """Return a prompt string from config/prompts."""

    def api_config(self, key: str, default: Any = None) -> Any:
        """Return an API config value."""
