"""Tax invoice extraction service: vision invocation and response validation."""

import json
import re
from typing import Optional

from pydantic import ValidationError

from src.core.document_processor import detect_file_type, load_image_bytes
from src.core.llm import invoke_vision_extraction
from src.prompts.tax_invoice import (
    get_tax_invoice_extraction_user_message,
    tax_invoice_extraction_prompt,
)
from src.schemas.response import ExtractionMetadata
from src.schemas.tax_invoice import TaxInvoiceExtractionResult, TaxInvoiceLLMOutput

ALLOWED_TYPES = {"pdf", "image"}


def _strip_json_from_llm_text(raw: str) -> str:
    """Extract JSON object text and remove optional code fences."""
    content = raw.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```\s*$", "", content)
        return content.strip()

    match = re.search(r"\{[\s\S]*\}\s*$", content)
    if match:
        return match.group(0).strip()
    return content


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    """Normalize empty/null-like text values to None."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() == "null":
        return None
    return normalized


def parse_tax_invoice_llm_json(content: str) -> TaxInvoiceLLMOutput:
    """Parse and validate tax invoice JSON emitted by the model."""
    stripped = _strip_json_from_llm_text(content)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM output is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("LLM JSON root must be an object")

    try:
        parsed = TaxInvoiceLLMOutput.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"LLM JSON failed schema validation: {exc}") from exc

    return TaxInvoiceLLMOutput(
        po_number=_normalize_optional_text(parsed.po_number),
        invoice_id=_normalize_optional_text(parsed.invoice_id),
        invoice_date=_normalize_optional_text(parsed.invoice_date),
        bill_to=_normalize_optional_text(parsed.bill_to),
    )


def _convert_to_png_first_page(content: bytes, filename: str) -> bytes:
    """Convert PDF/image input into a single PNG image for model processing."""
    file_type = detect_file_type(filename)
    if file_type not in ALLOWED_TYPES:
        raise ValueError(
            f"File must be PDF or image (jpg, jpeg, png). Got: {filename or 'unknown'}"
        )
    return load_image_bytes(content, filename)


def load_tax_invoice_input(file_content: bytes, file_name: str) -> bytes:
    """Validate and convert uploaded file into first-page PNG bytes."""
    if not file_content:
        raise ValueError("A file must be provided.")
    if not file_name or not file_name.strip():
        raise ValueError("Filename is required.")
    return _convert_to_png_first_page(file_content, file_name)


async def extract_tax_invoice(
    image_png_bytes: bytes,
) -> tuple[TaxInvoiceExtractionResult, ExtractionMetadata]:
    """Run tax invoice extraction on a preprocessed PNG image."""
    if not image_png_bytes:
        raise ValueError("Tax invoice image bytes are required")

    system_prompt = tax_invoice_extraction_prompt.strip()
    if not system_prompt:
        raise RuntimeError(
            "tax_invoice_extraction_prompt is empty; set it in src/prompts/tax_invoice.py"
        )

    user_prompt = get_tax_invoice_extraction_user_message().strip()
    if not user_prompt:
        raise RuntimeError(
            "Tax invoice user prompt is empty; set it in src/prompts/tax_invoice.py"
        )

    raw_text, metadata = await invoke_vision_extraction(
        system_prompt=system_prompt,
        image_bytes=image_png_bytes,
        user_text=user_prompt,
    )
    parsed = parse_tax_invoice_llm_json(raw_text)

    result = TaxInvoiceExtractionResult(
        po_number=parsed.po_number,
        invoice_id=parsed.invoice_id,
        invoice_date=parsed.invoice_date,
        bill_to=parsed.bill_to,
    )
    return result, metadata
