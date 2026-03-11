"""Document-specific extraction prompts."""

from src.prompts.performa_invoice import get_performa_invoice_system_prompt
from src.prompts.lpo_invoice import get_lpo_invoice_system_prompt

__all__ = ["get_performa_invoice_system_prompt", "get_lpo_invoice_system_prompt"]
