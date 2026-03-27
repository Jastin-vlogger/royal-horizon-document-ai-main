"""Unit tests for shipment_calculations post-processing (LPO-only logistics)."""

import pytest

from src.core.lpo_invoice_business_logics import (
    canonical_buying_unit_from_uom,
    normalize_inco_terms_to_allowed,
)
from src.core.shipment_calculations import (
    calculate_shipment_logistics,
    parse_currency_value,
    parse_packaging_kg,
)


def test_shipment_logistics_rice_example():
    """
    Example: 15,000 bags of 40kg rice.
    - quantity_in_mt: 15000 * 40 / 1000 = 600 MT
    - container_size: 20 (rice default)
    - fcl: ceil(600 / 25) = 24
    - bags_per_container: 25000 / 40 = 625
    - pallets: ceil(15000 / 50) = 300
    - fcl_per_unit: 625 * 22.40 = 14,000
    - price_per_mt: 22.40 * 25 = 560
    """
    parsed = {
        "lpo_invoice": {
            "commodity": "rice",
            "quantity_in_bags": "15,000.00",
            "unit": "22.40",
            "packaging": "BAG/1x40kg",
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    
    assert sc["container_size"] == 20
    assert sc["quantity_in_mt"] == 600.0
    assert sc["fcl"] == 24
    assert sc["bags"] == 15000
    assert sc["bags_per_container"] == 625
    assert sc["pallets"] == 300
    assert sc["fcl_per_unit"] == 14000.0
    assert sc["price_per_mt"] == 560.0


def test_shipment_logistics_small_batch():
    """
    Small batch: 1,000 bags of 10kg rice.
    - quantity_in_mt: 1000 * 10 / 1000 = 10 MT
    - fcl: ceil(10 / 25) = 1
    - bags_per_container: 25000 / 10 = 2500
    - pallets: ceil(1000 / 50) = 20
    """
    parsed = {
        "lpo_invoice": {
            "commodity": "rice",
            "quantity_in_bags": "1000",
            "unit": "9.80",
            "packaging": "10KG",
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    
    assert sc["container_size"] == 20
    assert sc["quantity_in_mt"] == 10.0
    assert sc["fcl"] == 1
    assert sc["bags"] == 1000
    assert sc["bags_per_container"] == 2500
    assert sc["pallets"] == 20


def test_shipment_logistics_missing_commodity():
    """If commodity is missing, container_size should be None."""
    parsed = {
        "lpo_invoice": {
            "commodity": None,
            "quantity_in_bags": "1000",
            "unit": "9.80",
            "packaging": "10KG",
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    
    assert sc["container_size"] is None
    assert sc["fcl"] is None


def test_shipment_logistics_missing_packaging():
    """If packaging is missing, calculations should be None."""
    parsed = {
        "lpo_invoice": {
            "commodity": "rice",
            "quantity_in_bags": "1000",
            "unit": "9.80",
            "packaging": None,
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    
    assert sc["quantity_in_mt"] is None
    assert sc["fcl"] is None
    assert sc["price_per_mt"] is None


def test_shipment_logistics_missing_lpo():
    """If LPO is missing, all calculations should be None."""
    parsed = {
        "lpo_invoice": None,
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    
    assert sc["container_size"] is None
    assert sc["quantity_in_mt"] is None
    assert sc["fcl"] is None
    assert sc["bags"] is None
    assert sc["pallets"] is None
    assert sc["fcl_per_unit"] is None
    assert sc["price_per_mt"] is None


def test_parse_currency_value():
    """parse_currency_value strips USD, PMT, commas."""
    assert parse_currency_value("USD 985.00 PMT") == 985.0
    assert parse_currency_value("9.80") == 9.8
    assert parse_currency_value("470,400.00") == 470400.0
    assert parse_currency_value("22.40") == 22.4


def test_parse_currency_value_invalid():
    """parse_currency_value raises ValueError when unparseable."""
    with pytest.raises(ValueError, match="Cannot parse"):
        parse_currency_value("N/A")
    with pytest.raises(ValueError, match="empty or not"):
        parse_currency_value("")


def test_parse_packaging_kg():
    """parse_packaging_kg handles 10 Kg, 40KG, 4X10 KG, BAG/1x10kg."""
    assert parse_packaging_kg("10 Kg") == 10.0
    assert parse_packaging_kg("40 KG") == 40.0
    assert parse_packaging_kg("4X10 KG") == 40.0
    assert parse_packaging_kg("BAG/1x10kg") == 10.0
    assert parse_packaging_kg("1X40KG") == 40.0


def test_parse_packaging_kg_invalid():
    """parse_packaging_kg raises ValueError when unparseable."""
    with pytest.raises(ValueError, match="Cannot parse"):
        parse_packaging_kg("N/A")
    with pytest.raises(ValueError, match="empty or not"):
        parse_packaging_kg("")


def test_canonical_buying_unit_from_uom():
    """UOM column prefix before slash maps to canonical unit (e.g. BAGS -> BAG)."""
    assert canonical_buying_unit_from_uom("BAGS/1*40KG") == "BAG"
    assert canonical_buying_unit_from_uom("BAG/1x40kg") == "BAG"
    assert canonical_buying_unit_from_uom("TONS/50") == "TON"


def test_normalize_inco_terms_to_allowed():
    """Extracted phrase maps to a single value from the allowed list."""
    allowed = ["CIF", "FOB", "EXWORKS", "C&F"]
    assert normalize_inco_terms_to_allowed("CIF JABEL ALI UAE.", allowed) == "CIF"
    assert normalize_inco_terms_to_allowed("CIF JABEL ALI UAE", allowed) == "CIF"
    assert normalize_inco_terms_to_allowed("C & F MUNDRA", ["C&F", "FOB"]) == "C&F"
    assert normalize_inco_terms_to_allowed("FOB", allowed) == "FOB"
    assert normalize_inco_terms_to_allowed("Unknown", allowed) is None
