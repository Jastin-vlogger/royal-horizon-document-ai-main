"""YAML-backed prompt and API config broker."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config.settings import CONFIG_DIR


class PromptConfigBroker:
    """Load prompts and API defaults from YAML files."""

    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self._config_dir = config_dir

    @staticmethod
    @lru_cache(maxsize=64)
    def _load_yaml(path: str) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise RuntimeError(f"Config file must contain a mapping: {path}")
        return data

    def prompt(self, prompt_file: str, key: str) -> str:
        path = self._config_dir / "prompts" / f"{prompt_file}.yml"
        value = self._load_yaml(str(path)).get(key)
        if value is None:
            raise RuntimeError(f"Prompt '{prompt_file}.{key}' is not configured")
        return str(value)

    def api_config(self, key: str, default: Any = None) -> Any:
        path = self._config_dir / "apis" / "document_defaults.yml"
        data = self._load_yaml(str(path))
        current: Any = data
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    def lpo_system_prompt(self, *, inco_terms: list[str], suppliers: list[str]) -> str:
        template = self.prompt("lpo_invoice", "system_prompt_template")
        inco_terms_str = (
            ", ".join(f'"{item}"' for item in inco_terms)
            if inco_terms
            else "CIF, FOB, EXW, C&F, etc."
        )
        suppliers_str = (
            ", ".join(f'"{item}"' for item in suppliers)
            if suppliers
            else "(any)"
        )
        return template.replace("{inco_terms}", inco_terms_str).replace(
            "{suppliers}",
            suppliers_str,
        )

    def packaging_list_user_prompt(self, target_brand: str) -> str:
        return self.prompt("packaging_list", "user_prompt_template").replace(
            "{target_brand}",
            target_brand,
        )

    def bill_user_prompt(self, num_pages: int) -> str:
        return self.prompt("purchase_tracker_bill_no", "user_prompt_template").replace(
            "{num_pages}",
            str(num_pages),
        )

    def stock_sheet_cleaner_prompt(self, canonical_keys: list[str]) -> str:
        keys = ", ".join(f'"{key}"' for key in canonical_keys)
        return self.prompt("stock_sheet", "cleaner_prompt_template").replace(
            "{canonical_keys}",
            keys,
        )
