"""Purchase tracker: structured B/L extraction via vision LLM + Pydantic validation."""

from typing import Any, Optional

from pydantic import ValidationError

from src.config.logger import logger
from src.core.llm import invoke_multi_image_vision_extraction
from src.prompts.purchase_tracker_bill_no import (
    get_bill_structured_system_prompt,
    get_bill_structured_user_prompt,
)
from src.schemas.response import (
    BillNoExtractionResponse,
    BillOfLadingStructuredExtraction,
    ExtractionMetadata,
)
from src.utils.utils import parse_json_from_content


def _coerce_legacy_bill_no_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Map legacy bill_no into bl_number when bl_number is absent or empty."""
    out = dict(data)
    bl = out.get("bl_number")
    legacy = out.get("bill_no")
    bl_empty = bl is None or (isinstance(bl, str) and not bl.strip())
    if bl_empty and legacy is not None:
        if isinstance(legacy, str):
            out["bl_number"] = legacy.strip() or None
        else:
            out["bl_number"] = str(legacy).strip() or None
    return out


def _validation_error_summary(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg', 'validation error')}")
    return "; ".join(parts) if parts else "Schema validation failed."


def build_bill_no_api_response(
    extraction: Optional[BillOfLadingStructuredExtraction],
    metadata: ExtractionMetadata,
) -> BillNoExtractionResponse:
    """Map validated LLM payload to the flat /bill-no response shape."""
    if extraction is None:
        return BillNoExtractionResponse(containers=[], metadata=metadata)
    return BillNoExtractionResponse(
        bill_no=extraction.bl_number,
        shipped_on_board_date=extraction.shipped_on_board_date,
        port_of_loading=extraction.port_of_loading,
        port_of_discharge=extraction.port_of_discharge,
        number_of_containers=extraction.number_of_containers,
        number_of_bags=extraction.number_of_bags,
        quantity_mt=extraction.quantity_mt,
        shipping_line=extraction.shipping_line,
        free_detention_days=extraction.free_detention_days,
        maximum_detention_days=extraction.maximum_detention_days,
        freight_prepaid=extraction.freight_prepaid,
        vessel_name=extraction.vessel_name,
        invoice_number=extraction.invoice_number,
        containers=list(extraction.containers),
        metadata=metadata,
    )


async def extract_bill_structured(
    page_png_bytes: list[bytes],
) -> tuple[
    Optional[BillOfLadingStructuredExtraction], ExtractionMetadata, Optional[str]
]:
    """
    Run vision extraction on one or more page images (PNG), validate with Pydantic.

    Returns (extraction_or_none, metadata, parse_error_or_none).
    """
    if not page_png_bytes:
        raise ValueError("At least one page image is required")

    logger.debug(
        f"Structured B/L extraction: {len(page_png_bytes)} page image(s), {sum(len(b) for b in page_png_bytes)} total bytes",
    )
    system_prompt = get_bill_structured_system_prompt()
    user_prompt = get_bill_structured_user_prompt(len(page_png_bytes))

    content, metadata = await invoke_multi_image_vision_extraction(
        system_prompt=system_prompt,
        image_bytes_list=page_png_bytes,
        user_text=user_prompt,
    )

    data = parse_json_from_content(content)
    if data is None:
        logger.warning("Structured B/L: JSON parse failed")
        return None, metadata, "Model output was empty or not valid JSON."

    payload = _coerce_legacy_bill_no_fields(data)
    try:
        extraction = BillOfLadingStructuredExtraction.model_validate(payload)
    except ValidationError as e:
        msg = _validation_error_summary(e)
        logger.warning(f"Structured B/L: Pydantic validation failed: {msg}")
        return None, metadata, msg

    return extraction, metadata, None


