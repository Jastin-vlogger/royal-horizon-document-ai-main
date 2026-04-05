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
    Compute aggregate shipment_calculations from LPO data with multiple line items.
    
    For multi-item LPOs, aggregates across all items:
    - container_size: Based on first item's commodity type (rice -> 20ft)
    - quantity_in_mt: Sum of all item weights
    - fcl: Total containers needed for all items
    - bags: Total bags across all items
    - bags_per_container: Average bags per container (total_bags / fcl)
    - pallets: Total pallets needed
    - fcl_per_unit: Total price / fcl (price per container)
    - price_per_mt: Total price / total MT
    
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
    
    # Get items array
    items = lpo.get("items", [])
    if not isinstance(items, list) or len(items) == 0:
        logger.warning("No items found in LPO, returning empty calculations")
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
    
    # Extract commodity from first item for container size determination
    first_commodity = None
    for item in items:
        if isinstance(item, dict):
            first_commodity = item.get("commodity")
            break
    
    container_size = get_commodity_container_size(first_commodity)
    
    # Determine container capacity
    container_capacity_mt: Optional[float] = None
    if container_size == 20:
        container_capacity_mt = CONTAINER_20FT_CAPACITY_MT
    elif container_size == 40:
        container_capacity_mt = CONTAINER_40FT_CAPACITY_MT
    
    # Aggregate calculations across all items
    total_bags: float = 0.0
    total_mt: float = 0.0
    total_price: float = 0.0
    items_processed: int = 0
    
    for item in items:
        # Handle both dict and object (Pydantic model) items
        if hasattr(item, "model_dump"):
            item_dict = item.model_dump()
        elif isinstance(item, dict):
            item_dict = item
        else:
            logger.warning(f"Skipping invalid item type: {type(item)}")
            continue
        
        # Parse quantity in bags for this item
        item_quantity = _parse_quantity_in_bags(item_dict.get("quantity_in_bags"))
        if item_quantity is None:
            logger.warning(f"Skipping item with no quantity: {item_dict.get('item_code')}")
            continue
        
        # Parse packaging weight for this item
        item_packaging_kg: Optional[float] = None
        if item_dict.get("packaging"):
            try:
                item_packaging_kg = parse_packaging_kg(str(item_dict["packaging"]))
            except ValueError as e:
                logger.warning(f"Failed to parse packaging for item {item_dict.get('item_code')}: {e}")
                continue
        else:
            logger.warning(f"Skipping item with no packaging: {item_dict.get('item_code')}")
            continue
        
        # Parse unit price for this item
        item_price_per_bag: Optional[float] = None
        if item_dict.get("unit"):
            try:
                item_price_per_bag = parse_currency_value(str(item_dict["unit"]))
            except ValueError as e:
                logger.warning(f"Failed to parse unit price for item {item_dict.get('item_code')}: {e}")
        
        # Calculate item weight in MT
        item_mt = (item_quantity * item_packaging_kg) / 1000.0
        
        # Accumulate totals
        total_bags += item_quantity
        total_mt += item_mt
        
        if item_price_per_bag is not None:
            total_price += item_quantity * item_price_per_bag
        
        items_processed += 1
        logger.debug(
            f"Item {item_dict.get('item_code')}: "
            f"{item_quantity} bags × {item_packaging_kg}kg = {item_mt:.2f} MT @ {item_price_per_bag}/bag"
        )
    
    if items_processed == 0:
        logger.warning("No valid items to calculate, returning empty calculations")
        parsed_response["shipment_calculations"] = {
            "container_size": container_size,
            "quantity_in_mt": None,
            "fcl": None,
            "bags": None,
            "bags_per_container": None,
            "pallets": None,
            "fcl_per_unit": None,
            "price_per_mt": None,
        }
        return parsed_response
    
    # Round total MT
    total_mt = round(total_mt, 2)
    total_bags_int = int(total_bags)
    
    # Calculate FCL (containers needed)
    fcl: Optional[int] = None
    bags_per_container: Optional[int] = None
    fcl_per_unit: Optional[float] = None
    
    if container_capacity_mt is not None and total_mt > 0:
        fcl = int(math.ceil(total_mt / container_capacity_mt))
        
        # Bags per container (average across mixed packaging)
        bags_per_container = int(math.ceil(total_bags / fcl))
        
        # FCL per unit (price per container)
        if total_price > 0:
            fcl_per_unit = total_price / fcl
            fcl_per_unit = round(fcl_per_unit, 2)
    
    # Calculate pallets
    pallets: Optional[int] = None
    if total_bags_int > 0:
        pallets = int(math.ceil(total_bags_int / BAGS_PER_PALLET))
    
    # Calculate price per MT
    price_per_mt: Optional[float] = None
    if total_price > 0 and total_mt > 0:
        price_per_mt = total_price / total_mt
        price_per_mt = round(price_per_mt, 2)
    
    shipment_calculations: dict[str, Any] = {
        "container_size": container_size,
        "quantity_in_mt": total_mt if total_mt > 0 else None,
        "fcl": fcl,
        "bags": total_bags_int if total_bags_int > 0 else None,
        "bags_per_container": bags_per_container,
        "pallets": pallets,
        "fcl_per_unit": fcl_per_unit,
        "price_per_mt": price_per_mt,
    }
    
    logger.debug(f"Aggregate calculations: {shipment_calculations}")
    
    out = dict(parsed_response)
    out["shipment_calculations"] = shipment_calculations
    return out
