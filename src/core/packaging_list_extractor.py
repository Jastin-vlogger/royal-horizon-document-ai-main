"""Packaging List document extraction logic."""

from typing import Optional

from pydantic import ValidationError

from src.config.logger import logger
from src.core.llm import invoke_multi_image_vision_extraction
from src.prompts.packaging_list import (
    get_packaging_list_user_message,
    packaging_list_extraction_prompt,
)
from src.schemas.packaging_list import PackagingListExtraction
from src.schemas.response import ExtractionMetadata
from src.utils.utils import parse_json_from_content


def _validation_error_summary(exc: ValidationError) -> str:
    """Generate a human-readable summary of validation errors."""
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg', 'validation error')}")
    return "; ".join(parts) if parts else "Schema validation failed."


async def extract_packaging_list_structured(
    page_png_bytes: list[bytes],
    target_brand: str,
) -> tuple[Optional[PackagingListExtraction], ExtractionMetadata, Optional[str]]:
    """
    Extract structured data from Packaging List document for a specific brand.

    Args:
        page_png_bytes: List of PNG image bytes (max 2 pages)
        target_brand: Brand name to extract data for

    Returns:
        Tuple of (extraction_or_none, metadata, parse_error_or_none)
    """
    if not page_png_bytes:
        raise ValueError("At least one page image is required")

    if not target_brand or not target_brand.strip():
        raise ValueError("target_brand must be provided")

    logger.debug(
        f"Packaging List extraction: {len(page_png_bytes)} page(s), "
        f"{sum(len(b) for b in page_png_bytes)} total bytes, brand='{target_brand}'"
    )

    system_prompt = packaging_list_extraction_prompt
    user_prompt = get_packaging_list_user_message(target_brand.strip())

    content, metadata = await invoke_multi_image_vision_extraction(
        system_prompt=system_prompt,
        image_bytes_list=page_png_bytes,
        user_text=user_prompt,
    )

    data = parse_json_from_content(content)
    if data is None:
        logger.warning("Packaging List: JSON parse failed")
        return None, metadata, "Model output was empty or not valid JSON."

    try:
        extraction = PackagingListExtraction.model_validate(data)
    except ValidationError as e:
        msg = _validation_error_summary(e)
        logger.warning(f"Packaging List: Pydantic validation failed: {msg}")
        return None, metadata, msg

    # Validate consistency: container_info count should match container_number_list count
    if len(extraction.container_info) != len(extraction.container_number_list):
        logger.warning(
            f"Packaging List: container_info count ({len(extraction.container_info)}) "
            f"!= container_number_list count ({len(extraction.container_number_list)})"
        )

    return extraction, metadata, None
