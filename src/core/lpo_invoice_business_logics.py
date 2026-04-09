"""Business logic for LPO document extraction: prompt + LLM + parse."""

import json
import re
from typing import List, Optional, Tuple

from src.core.llm import invoke_vision_extraction
from src.core.commodity_normalizer import normalize_commodity
from src.prompts.lpo_invoice import get_lpo_invoice_system_prompt
from src.schemas.response import ExtractionMetadata, LPOInvoiceResult, LPOLineItem
from src.config.logger import logger


def normalize_packaging_uom(value: Optional[str]) -> Optional[str]:
    """
    Normalize packaging UOM to format like 1X10KG, 4X10KG.
    Input: "10kg", "1x10kg", "BAG/1x10kg", "4*10 kg"
    Output: "1X10KG", "4X10KG", "10KG"
    """
    if value is None or not isinstance(value, str) or not value.strip():
        return value if value is None else None
    s = value.strip().upper()
    # Remove prefix like "BAG/"
    s = re.sub(r"^[A-Z/]+\s*", "", s)
    # NxM or N*M pattern -> NXMKG
    mult_match = re.search(r"(\d+)\s*[xX*]\s*(\d+)\s*(?:kg|KG)?", s)
    if mult_match:
        n, m = int(mult_match.group(1)), int(mult_match.group(2))
        return f"{n}X{m}KG"
    # Single number + optional KG -> NKG
    single_match = re.search(r"(\d+\.?\d*)\s*(?:kg|KG)?", s)
    if single_match:
        return f"{int(float(single_match.group(1)))}KG"
    return value.strip() or value


def _normalize_inco_text_for_match(text: str) -> str:
    """Uppercase, trim, strip trailing punctuation, normalize C&F spellings."""
    s = text.strip().upper()
    s = s.rstrip(".;:, ")
    s = re.sub(r"\s*&\s*", "&", s)
    s = re.sub(r"\s+AND\s+", "&", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_inco_terms_to_allowed(
    extracted: Optional[str],
    allowed: List[str],
) -> Optional[str]:
    """
    Map free-text extracted inco terms (e.g. 'CIF JABEL ALI UAE.') to exactly one
    value from ``allowed`` (e.g. 'CIF'). Preserves the casing/spelling of the matched
    entry from ``allowed``. Returns None if nothing matches.
    """
    if not extracted or not isinstance(extracted, str) or not extracted.strip():
        return None
    cleaned = [a.strip() for a in allowed if isinstance(a, str) and a.strip()]
    if not cleaned:
        return None

    norm_extracted = _normalize_inco_text_for_match(extracted)
    if not norm_extracted:
        return None

    # Longest allowed first so e.g. C&F wins over C if both exist
    for term in sorted(cleaned, key=len, reverse=True):
        nt = _normalize_inco_text_for_match(term)
        if not nt:
            continue
        if norm_extracted == nt:
            return term
        if norm_extracted.startswith(nt + " ") or norm_extracted.startswith(nt + "."):
            return term
        # Token appears as a whole word in the phrase
        padded = f" {norm_extracted} "
        if f" {nt} " in padded:
            return term
        # Prefix when extract is exactly code + boundary
        if len(norm_extracted) > len(nt) and norm_extracted.startswith(nt):
            next_ch = norm_extracted[len(nt)]
            if next_ch in " \t.,;:/":
                return term
        if norm_extracted.startswith(nt) and len(norm_extracted) == len(nt):
            return term

    # First token only (e.g. "CIF." -> "CIF")
    parts = norm_extracted.split()
    if parts:
        first = parts[0].rstrip(".;:, ")
        for term in sorted(cleaned, key=len, reverse=True):
            nt = _normalize_inco_text_for_match(term)
            if first == nt:
                return term

    logger.warning(
        "inco_terms could not be mapped to allowed list: extracted=%r allowed=%r",
        extracted,
        cleaned,
    )
    return None


def normalize_payment_terms(value: Optional[str]) -> Optional[str]:
    """
    Remove spaces between numeric amounts and '%' so API output matches e.g. '100%'
    instead of '100 %'.
    """
    if value is None or not isinstance(value, str):
        return value
    if not value.strip():
        return value
    # e.g. "100 % CAD" -> "100% CAD"; "50.5  %" -> "50.5%"
    return re.sub(r"(\d+(?:[.,]\d+)?)\s+%", r"\1%", value)


def canonical_buying_unit_from_uom(uom: Optional[str]) -> Optional[str]:
    """
    From UOM cell text like 'BAGS/1*40KG' or 'BAG/1x40kg', return canonical buying unit (e.g. BAG).
    Uses the segment before the first '/'.
    """
    if not uom or not isinstance(uom, str):
        return None
    prefix = uom.strip().split("/")[0].strip().upper()
    if not prefix:
        return None
    if prefix in ("BAGS", "BAG"):
        return "BAG"
    if prefix.endswith("S") and len(prefix) > 1:
        singular = prefix[:-1]
        if singular in ("BAG", "TON", "BOX", "SACK", "DRUM"):
            return singular
    return prefix


def _parse_json_from_content(content: str) -> Optional[dict]:
    """Extract JSON object from model output (may be wrapped in markdown)."""
    if not content or not content.strip():
        return None
    text = content.strip()
    # Remove optional markdown code block
    if "```json" in text:
        text = re.sub(r"^.*?```json\s*", "", text, flags=re.DOTALL)
    if "```" in text:
        text = re.sub(r"```\s*.*$", "", text, flags=re.DOTALL)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def extract_lpo_invoice(
    image_bytes: bytes,
    inco_terms_list: Optional[List[str]] = None,
    suppliers: Optional[List[str]] = None,
) -> Tuple[Optional[LPOInvoiceResult], Optional[ExtractionMetadata]]:
    """
    Run LPO extraction on the given image bytes.
    inco_terms_list and suppliers are injected into the prompt for validation/matching.
    Returns (parsed result, metadata). Result is None if parsing failed.
    """
    logger.debug("Extracting LPO Invoice")
    inco_list = inco_terms_list if inco_terms_list is not None else []
    supplier_list = suppliers if suppliers is not None else []
    system_prompt = get_lpo_invoice_system_prompt(
        inco_terms_list=inco_list,
        suppliers=supplier_list,
    )
    content, metadata = await invoke_vision_extraction(
        system_prompt=system_prompt,
        image_bytes=image_bytes,
        user_text="Extract the required fields and return only valid JSON.",
    )
    logger.debug(f"LPO Invoice Extracted: {content}")
    data = _parse_json_from_content(content)
    if data is None:
        logger.warning("LPO Invoice Parsed Failed, returning None")
        return None, metadata
    
    # Ensure data is a dict (not a list)
    if isinstance(data, list):
        logger.warning("LPO extraction returned a list instead of dict, taking first element")
        data = data[0] if len(data) > 0 and isinstance(data[0], dict) else {}

    # Post-process: inco_terms must be exactly one value from inco_terms_list
    raw_inco = data.get("inco_terms")
    if raw_inco is not None and inco_list:
        mapped = normalize_inco_terms_to_allowed(
            raw_inco if isinstance(raw_inco, str) else str(raw_inco),
            inco_list,
        )
        data["inco_terms"] = mapped

    raw_payment = data.get("payment_terms")
    if raw_payment is not None:
        data["payment_terms"] = normalize_payment_terms(
            raw_payment if isinstance(raw_payment, str) else str(raw_payment)
        )

    # Post-process: add default null fields for header (ensure keys exist for API contract)
    defaults = {
        "vendor_email": None,
        "port_of_loading": None,
        "port_of_discharge": None,
        "bank_name": None,
        "pi_number": None,
        "pi_date": None,
    }
    for key, value in defaults.items():
        if key not in data:
            data[key] = value

    for key in ("vendor_email", "port_of_loading", "port_of_discharge", "bank_name", "pi_number", "pi_date"):
        val = data.get(key)
        if isinstance(val, str) and not val.strip():
            data[key] = None

    # Post-process: normalize each line item
    items_raw = data.get("items", [])
    if not isinstance(items_raw, list):
        logger.warning("items field is not a list, setting to empty list")
        items_raw = []
    
    processed_items = []
    for item_data in items_raw:
        if not isinstance(item_data, dict):
            logger.warning(f"Skipping non-dict item: {item_data}")
            continue
        
        # Extract and remove uom_raw (internal field)
        uom_raw = item_data.pop("uom_raw", None)
        
        # Derive packaging and buying_unit from uom_raw
        if isinstance(uom_raw, str) and uom_raw.strip():
            uom_raw = uom_raw.strip()
            item_data["packaging"] = normalize_packaging_uom(uom_raw)
            item_data["buying_unit"] = canonical_buying_unit_from_uom(uom_raw)
        elif item_data.get("packaging"):
            item_data["packaging"] = normalize_packaging_uom(item_data["packaging"])
        
        # Normalize buying_unit if present
        if item_data.get("buying_unit") and isinstance(item_data["buying_unit"], str):
            bu = item_data["buying_unit"].strip()
            if "/" not in bu:
                item_data["buying_unit"] = canonical_buying_unit_from_uom(f"{bu}/")
            else:
                item_data["buying_unit"] = canonical_buying_unit_from_uom(bu)
        
        # Normalize commodity
        if item_data.get("commodity"):
            item_data["commodity"] = normalize_commodity(item_data["commodity"])
        
        try:
            line_item = LPOLineItem(**item_data)
            processed_items.append(line_item)
        except Exception as e:
            logger.warning(f"Failed to parse line item: {e}, data: {item_data}")
            continue
    
    # Update data with processed items
    data["items"] = processed_items

    try:
        result = LPOInvoiceResult(**data)
    except Exception as e:
        logger.warning(f"LPO Invoice Parsed Failed: {e}, returning empty result")
        result = LPOInvoiceResult()
    logger.debug(f"LPO Invoice Result: {result}")
    return result, metadata
