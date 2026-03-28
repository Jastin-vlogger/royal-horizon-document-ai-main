"""Post-processing: shipment logistics calculations from LPO data."""

import logging
import math
import re
from typing import Any, Optional

from src.core.commodity_normalizer import get_commodity_container_size

logger = logging.getLogger(__name__)

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
    s = s.replace(",", "")
    for token in ("USD", "$", "AED", "PMT", "MT", "PER"):
        s = s.replace(token, " ")
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
    s = re.sub(r"^[A-Z/]+\s*", "", s, flags=re.IGNORECASE)
    mult_match = re.search(r"(\d+)\s*[xX]\s*(\d+)", s)
    if mult_match:
        return float(int(mult_match.group(1)) * int(mult_match.group(2)))
    match = re.search(r"(\d+\.?\d*)", s)
    if not match:
        raise ValueError(f"Cannot parse packaging KG from: {value!r}")
    return float(match.group(1))


def _parse_quantity_in_bags(quantity_str: Optional[str]) -> Optional[float]:
    """
    Extract numeric quantity from LPO quantity_in_bags field.
    Examples: '15,000.00' -> 15000.0, '48000' -> 48000.0
    """
    if not quantity_str or not isinstance(quantity_str, str):
        return None
    s = quantity_str.strip().replace(",", "")
    match = re.search(r"(\d+\.?\d*)", s)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def calculate_shipment_logistics(parsed_response: dict[str, Any]) -> dict[str, Any]:
    """
    Compute shipment_calculations from LPO data only.
    
    Calculates:
    - container_size: Based on commodity type (rice -> 20ft)
    - quantity_in_mt: Calculated from bags and packaging weight
    - fcl: Number of containers needed
    - bags: Total number of bags (from LPO)
    - bags_per_container: Bags that fit in one container
    - pallets: Number of pallets needed
    - fcl_per_unit: Price per container
    - price_per_mt: Price per metric ton
    
    Returns the same dict with 'shipment_calculations' added/updated.
    """
    lpo = parsed_response.get("lpo_invoice")
    
    if not lpo or not isinstance(lpo, dict):
        logger.warning("LPO data missing, returning empty calculations")
        parsed_response["shipment_calculations"] = {
            "container_size": None,
            "quantity_in_mt": None,
            "fcl": None,
            "bags": None,
            "bags_per_container": None,
            "pallets": None,
            "fcl_per_unit": None,
            "price_per_mt": None,
        }
        return parsed_response
    
    # Extract commodity and determine container size
    commodity = lpo.get("commodity")
    container_size = get_commodity_container_size(commodity)
    
    # Determine container capacity
    container_capacity_mt: Optional[float] = None
    if container_size == 20:
        container_capacity_mt = CONTAINER_20FT_CAPACITY_MT
    elif container_size == 40:
        container_capacity_mt = CONTAINER_40FT_CAPACITY_MT
    
    # Parse packaging weight (kg per bag)
    packing_kg: Optional[float] = None
    if lpo.get("packaging"):
        try:
            packing_kg = parse_packaging_kg(str(lpo["packaging"]))
        except ValueError as e:
            logger.warning(f"Failed to parse packaging: {e}")
    
    # Parse quantity in bags
    quantity_in_bags = _parse_quantity_in_bags(lpo.get("quantity_in_bags"))
    
    # Parse unit price (price per bag)
    price_per_bag: Optional[float] = None
    if lpo.get("unit"):
        try:
            price_per_bag = parse_currency_value(str(lpo["unit"]))
        except ValueError as e:
            logger.warning(f"Failed to parse unit price: {e}")
    
    # Initialize calculation results
    quantity_in_mt: Optional[float] = None
    fcl: Optional[int] = None
    bags: Optional[int] = None
    bags_per_container: Optional[int] = None
    pallets: Optional[int] = None
    fcl_per_unit: Optional[float] = None
    price_per_mt: Optional[float] = None
    
    # Calculate quantity in MT
    if quantity_in_bags is not None and packing_kg is not None and packing_kg > 0:
        quantity_in_mt = (quantity_in_bags * packing_kg) / 1000.0
        quantity_in_mt = round(quantity_in_mt, 2)
        bags = int(quantity_in_bags)
    
    # Calculate FCL and bags per container
    if container_capacity_mt is not None and quantity_in_mt is not None and packing_kg is not None:
        fcl = int(math.ceil(quantity_in_mt / container_capacity_mt))
        container_capacity_kg = container_capacity_mt * 1000
        bags_per_container = int(container_capacity_kg / packing_kg)
        
        # Calculate pallets
        if bags is not None:
            pallets = int(math.ceil(bags / BAGS_PER_PALLET))
        
        # Calculate FCL per unit (price per container)
        if price_per_bag is not None:
            fcl_per_unit = bags_per_container * price_per_bag
            fcl_per_unit = round(fcl_per_unit, 2)
    
    # Calculate price per MT
    if price_per_bag is not None and packing_kg is not None and packing_kg > 0:
        bags_per_mt = 1000.0 / packing_kg
        price_per_mt = price_per_bag * bags_per_mt
        price_per_mt = round(price_per_mt, 2)
    
    shipment_calculations: dict[str, Any] = {
        "container_size": container_size,
        "quantity_in_mt": quantity_in_mt,
        "fcl": fcl,
        "bags": bags,
        "bags_per_container": bags_per_container,
        "pallets": pallets,
        "fcl_per_unit": fcl_per_unit,
        "price_per_mt": price_per_mt,
    }
    
    out = dict(parsed_response)
    out["shipment_calculations"] = shipment_calculations
    return out
