"""Prompt foundation implementation."""

from typing import Any

from src.brokers.prompt_config_broker import PromptConfigBroker


class PromptFoundation:
    """Domain wrapper for prompt and API config."""

    def __init__(self, prompt_broker: PromptConfigBroker) -> None:
        self._prompt_broker = prompt_broker

    def prompt(self, prompt_file: str, key: str) -> str:
        return self._prompt_broker.prompt(prompt_file, key)

    def api_config(self, key: str, default: Any = None) -> Any:
        return self._prompt_broker.api_config(key, default)

    def lpo_system_prompt(self, *, inco_terms: list[str], suppliers: list[str]) -> str:
        return self._prompt_broker.lpo_system_prompt(
            inco_terms=inco_terms,
            suppliers=suppliers,
        )

    def packaging_list_user_prompt(self, target_brand: str) -> str:
        return self._prompt_broker.packaging_list_user_prompt(target_brand)

    def bill_user_prompt(self, num_pages: int) -> str:
        return self._prompt_broker.bill_user_prompt(num_pages)

    def stock_sheet_cleaner_prompt(self, canonical_keys: list[str]) -> str:
        return self._prompt_broker.stock_sheet_cleaner_prompt(canonical_keys)
