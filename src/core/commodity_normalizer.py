"""Commodity normalization for extensible commodity type handling."""

from typing import Optional

ALLOWED_COMMODITIES = ["rice", "sugar"]


def normalize_commodity(raw_value: Optional[str]) -> Optional[str]:
    """
    Normalize commodity value to allowed list.
    
    Args:
        raw_value: Raw commodity string from extraction
        
    Returns:
        Normalized commodity name (lowercase) or None if empty
        
    Examples:
        "Rice" -> "rice"
        "RICE - Indian Basmati" -> "rice"
        "Sugar" -> "sugar"
        "Unknown" -> "unknown" (returns as-is for extensibility)
    """
    if not raw_value or not isinstance(raw_value, str):
        return None
    
    normalized = raw_value.strip().lower()
    
    for allowed in ALLOWED_COMMODITIES:
        if allowed in normalized:
            return allowed
    
    return normalized


def get_commodity_container_size(commodity: Optional[str]) -> Optional[int]:
    """
    Get default container size based on commodity type.
    
    Args:
        commodity: Normalized commodity name
        
    Returns:
        Container size in feet (20 or 40) or None if not mapped
        
    Examples:
        "rice" -> 20
        "sugar" -> 20
    """
    COMMODITY_CONTAINER_SIZE = {
        "rice": 20,
        "sugar": 20,
    }
    
    if not commodity:
        return None
    
    return COMMODITY_CONTAINER_SIZE.get(commodity.lower())
