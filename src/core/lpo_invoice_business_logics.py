"""Business logic for LPO document extraction: prompt + LLM + parse."""

import json
import re
from typing import List, Optional, Tuple

from src.core.llm import invoke_vision_extraction
from src.core.commodity_normalizer import normalize_commodity
from src.prompts.lpo_invoice import get_lpo_invoice_system_prompt
from src.schemas.response import ExtractionMetadata, LPOInvoiceResult
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
    # If model returned a list (multiple line items), take first and flatten
    if isinstance(data, list) and len(data) > 0:
        data = data[0] if isinstance(data[0], dict) else data

    # Post-process: UOM column drives packaging + buying_unit; uom_raw is internal only
    uom_raw = data.pop("uom_raw", None)
    if isinstance(uom_raw, str) and uom_raw.strip():
        uom_raw = uom_raw.strip()
        data["packaging"] = normalize_packaging_uom(uom_raw)
        data["buying_unit"] = canonical_buying_unit_from_uom(uom_raw)
    elif data.get("packaging"):
        data["packaging"] = normalize_packaging_uom(data["packaging"])

    if data.get("buying_unit") and isinstance(data["buying_unit"], str):
        bu = data["buying_unit"].strip()
        if "/" not in bu:
            data["buying_unit"] = canonical_buying_unit_from_uom(f"{bu}/")
        else:
            data["buying_unit"] = canonical_buying_unit_from_uom(bu)

    # Post-process: inco_terms must be exactly one value from inco_terms_list
    raw_inco = data.get("inco_terms")
    if raw_inco is not None and inco_list:
        mapped = normalize_inco_terms_to_allowed(
            raw_inco if isinstance(raw_inco, str) else str(raw_inco),
            inco_list,
        )
        data["inco_terms"] = mapped

    # Post-process: normalize commodity to allowed values
    if data.get("commodity"):
        data["commodity"] = normalize_commodity(data["commodity"])
    
    # Post-process: add default null fields
    defaults = {
        "port_of_loading": None,
        "port_of_discharge": None,
        "pi_number": None,
        "pi_date": None,
    }
    for key, value in defaults.items():
        if key not in data:
            data[key] = value

    try:
        result = LPOInvoiceResult(**data)
    except Exception:
        logger.warning("LPO Invoice Parsed Failed, returning None")
        result = LPOInvoiceResult()
    logger.debug(f"LPO Invoice Result: {result}")
    return result, metadata
