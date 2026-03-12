"""Post-processing: shipment logistics and LPO vs PI price reconciliation."""

import logging
import math
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

PRICE_TOLERANCE_PERCENT = 0.0
"""

PRICE_TOLERANCE_PERCENT = 2.0 is the maximum allowed percentage difference between:

LPO price per MT (from LPO unit price and packaging), and
PI price per MT (from Performa price_per_mton),
for the system to consider prices reconciled.
diff_percent = abs(lpo_price_per_mt - pi_price_per_mt) / pi_price_per_mt * 100
is_price_matching = diff_percent <= PRICE_TOLERANCE_PERCENT
So with 2.0, any difference ≤ 2% is treated as a match; above 2% is a mismatch.



Increase => Looser: more matches, fewer flags	
Decrease => Strict: fewer matches, more flags

Decreasing it (e.g. 2.0 → 0.5 or 0)

Effect: Fewer pairs are reconciled; you get more mismatches.
Use case: Stricter control: only very close (or identical) prices count as reconciled.
Example: LPO 980 vs PI 985 → diff ≈ 0.51%. With 2% that’s reconciled; with 0.5% it would be a mismatch.

Increasing it (e.g. 2.0 → 5.0)

Effect: More invoice pairs are marked as reconciled.
Use case: You want to allow more variance (rounding, different units, small FX/rounding differences) and get fewer “price mismatch” flags.
Example: LPO 980 vs PI 1010 → diff ≈ 2.98%. With 2% tolerance that’s a mismatch; with 5% it’s reconciled.

"""

# Container capacity in MT
CONTAINER_20FT_CAPACITY_MT = 25.0
CONTAINER_40FT_CAPACITY_MT = 26.0
BAGS_PER_PALLET = 50


def parse_currency_value(value: str) -> float:
    """
    Strip currency codes (USD, $, AED), 'PMT', 'MT', 'per', commas; return float.
    Raises ValueError if unparseable.
    """
    if not value or not isinstance(value, str):
        raise ValueError("Value is empty or not a string")
    s = value.strip().upper()
    # Remove commas first so "470,400.00" stays as one number
    s = s.replace(",", "")
    # Remove currency codes and common suffixes
    for token in ("USD", "$", "AED", "PMT", "MT", "PER"):
        s = s.replace(token, " ")
    # Extract numeric part (allow decimal)
    match = re.search(r"-?\d+\.?\d*", s)
    if not match:
        raise ValueError(f"Cannot parse numeric value from: {value!r}")
    return float(match.group())


def parse_packaging_kg(value: str) -> float:
    """
    Extract KG per unit from strings like '10 Kg', '40KG', '4X10 KG', 'BAG/1x10kg'.
    For multi-pack (e.g. 4X10), returns total KG (4*10 = 40).
    """
    if not value or not isinstance(value, str):
        raise ValueError("Packaging value is empty or not a string")
    s = value.strip().upper()
    # Remove non-numeric prefix like "BAG/"
    s = re.sub(r"^[A-Z/]+\s*", "", s, flags=re.IGNORECASE)
    # Handle NxM or NXM pattern (e.g. 4X10, 1x10)
    mult_match = re.search(r"(\d+)\s*[xX]\s*(\d+)", s)
    if mult_match:
        return float(int(mult_match.group(1)) * int(mult_match.group(2)))
    # Single number followed by optional KG
    match = re.search(r"(\d+\.?\d*)", s)
    if not match:
        raise ValueError(f"Cannot parse packaging KG from: {value!r}")
    return float(match.group(1))


def _parse_quantity_mt(quantity_str: Optional[str]) -> Optional[float]:
    """Extract quantity in MT from performa_invoice.quantity (e.g. '2500.00 MT' or '480.000 MT (+- 5%)')."""
    if not quantity_str or not isinstance(quantity_str, str):
        return None
    s = quantity_str.strip()
    # Remove "MT" and anything after (e.g. "(+- 5%)")
    s = re.sub(r"\s*MT.*$", "", s, flags=re.IGNORECASE)
    s = s.replace(",", "").strip()
    match = re.search(r"(\d+\.?\d*)", s)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _compute_price_reconciliation(
    lpo_invoice: Optional[dict],
    performa_invoice: Optional[dict],
) -> tuple[
    Optional[bool], Optional[float], Optional[float], Optional[float], Optional[float]
]:
    """
    Compute is_price_matching, lpo_price_per_mt, pi_price_per_mt, mt_variation, diff_percent.
    Returns (None, None, None, None, None) when data is missing or unparseable.
    """
    if not lpo_invoice or not performa_invoice:
        return None, None, None, None, None
    unit_raw = lpo_invoice.get("unit") if isinstance(lpo_invoice, dict) else None
    packaging_raw = (
        lpo_invoice.get("packaging") if isinstance(lpo_invoice, dict) else None
    )
    price_per_mton_raw = (
        performa_invoice.get("price_per_mton")
        if isinstance(performa_invoice, dict)
        else None
    )

    if not unit_raw or not packaging_raw or not price_per_mton_raw:
        return None, None, None, None, None
    if (
        not isinstance(unit_raw, str)
        or not isinstance(packaging_raw, str)
        or not isinstance(price_per_mton_raw, str)
    ):
        return None, None, None, None, None

    try:
        lpo_unit_price = parse_currency_value(unit_raw)
    except ValueError:
        return None, None, None, None, None
    try:
        lpo_packaging_kg = parse_packaging_kg(packaging_raw)
    except ValueError:
        return None, None, None, None, None
    if lpo_packaging_kg <= 0:
        return None, None, None, None, None
    try:
        pi_price_per_mt = parse_currency_value(price_per_mton_raw)
    except ValueError:
        return None, None, None, None, None
    if pi_price_per_mt <= 0:
        return None, None, None, None, None

    bags_per_mt = 1000.0 / lpo_packaging_kg
    lpo_price_per_mt = lpo_unit_price * bags_per_mt
    lpo_price_per_mt = round(lpo_price_per_mt, 2)
    pi_price_per_mt = round(pi_price_per_mt, 2)

    diff_percent = abs(lpo_price_per_mt - pi_price_per_mt) / pi_price_per_mt * 100
    diff_percent = round(diff_percent, 2)
    mt_variation = round(abs(lpo_price_per_mt - pi_price_per_mt), 2)

    is_price_matching = bool(diff_percent <= PRICE_TOLERANCE_PERCENT)

    if not is_price_matching:
        logger.warning(
            "Price reconciliation mismatch: lpo_price_per_mt=%.2f, pi_price_per_mt=%.2f, diff_percent=%.2f%%",
            lpo_price_per_mt,
            pi_price_per_mt,
            diff_percent,
        )
    return (
        is_price_matching,
        lpo_price_per_mt,
        pi_price_per_mt,
        mt_variation,
        diff_percent,
    )


def calculate_shipment_logistics(parsed_response: dict[str, Any]) -> dict[str, Any]:
    """
    Compute shipment_calculations from parsed_response (lpo_invoice, performa_invoice, metadata).
    Adds keys: fcl, bags, container_size (from PI packaging), fcl_size (20ft/40ft), bags_per_container,
    pallets, is_price_matching, lpo_price_per_mt, pi_price_per_mt.
    Returns the same dict with 'shipment_calculations' added/updated.
    """
    lpo = parsed_response.get("lpo_invoice")
    pi = parsed_response.get("performa_invoice")

    # container_size: master bag weight in KG from PI packaging (e.g. 20, 40)
    container_size: Optional[int] = None
    if pi and isinstance(pi, dict) and pi.get("container_size") is not None:
        try:
            container_size = int(pi["container_size"])
        except (TypeError, ValueError):
            pass

    # Defaults for logistics (set to None when missing/unparseable)
    fcl: Optional[int] = None
    bags: Optional[int] = None
    bags_per_container: Optional[int] = None
    pallets: Optional[int] = None

    quantity_mt = _parse_quantity_mt(
        pi.get("quantity") if isinstance(pi, dict) and pi else None
    )
    packing_kg: Optional[float] = None
    if lpo and isinstance(lpo, dict) and lpo.get("packaging"):
        try:
            packing_kg = parse_packaging_kg(str(lpo["packaging"]))
        except ValueError:
            pass

        if container_size is not None and str(container_size) == "20":
            container_capacity_mt = CONTAINER_20FT_CAPACITY_MT

        elif container_size is not None and str(container_size) == "40":
            container_capacity_mt = CONTAINER_40FT_CAPACITY_MT
        else:
            container_size = None
            container_capacity_mt = None
        if (
            container_capacity_mt is not None
            and quantity_mt is not None
            and packing_kg is not None
        ):
            fcl = int(math.ceil(quantity_mt / container_capacity_mt))
            container_capacity_kg = container_capacity_mt * 1000
            bags_per_container = int(container_capacity_kg / packing_kg)
            total_quantity_kg = quantity_mt * 1000
            bags = int(total_quantity_kg / packing_kg)
            pallets = int(math.ceil(bags / BAGS_PER_PALLET))
        else:
            fcl = None
            bags_per_container = None
            bags = None
            pallets = None

    is_price_matching, lpo_price_per_mt, pi_price_per_mt, mt_variation, diff_percent = (
        _compute_price_reconciliation(lpo, pi)
    )

    shipment_calculations: dict[str, Any] = {
        "fcl": fcl,
        "bags": bags,
        "container_size": container_size,
        "bags_per_container": bags_per_container,
        "pallets": pallets,
        "is_price_matching": is_price_matching,
        "lpo_price_per_mt": lpo_price_per_mt,
        "pi_price_per_mt": pi_price_per_mt,
        "mt_variation": mt_variation,
        "diff_percent": diff_percent,
    }
    out = dict(parsed_response)
    out["shipment_calculations"] = shipment_calculations
    return out
