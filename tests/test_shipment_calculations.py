"""Unit tests for shipment_calculations post-processing (LPO-only logistics)."""

import pytest

from src.processing.extractions import (
    canonical_buying_unit_from_uom,
    normalize_inco_terms_to_allowed,
    normalize_payment_terms,
)
from src.processing.shipment.shipment_calculations import (
    calculate_shipment_logistics,
    parse_currency_value,
    parse_packaging_kg,
)


def test_shipment_logistics_rice_example():
    """
    Example: Single item with 15,000 bags of 40kg rice.
    - quantity_in_mt: 15000 * 40 / 1000 = 600 MT
    - container_size: 20 (rice default)
    - fcl: ceil(600 / 25) = 24
    - bags_per_container: ceil(15000 / 24) = 625
    - pallets: ceil(15000 / 50) = 300
    - fcl_per_unit: (15000 * 22.40) / 24 = 14,000
    - price_per_mt: (15000 * 22.40) / 600 = 560
    """
    parsed = {
        "lpo_invoice": {
            "items": [
                {
                    "commodity": "rice",
                    "quantity_in_bags": "15,000.00",
                    "unit": "22.40",
                    "packaging": "1X40KG",
                }
            ]
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
    Small batch: Single item with 1,000 bags of 10kg rice.
    - quantity_in_mt: 1000 * 10 / 1000 = 10 MT
    - fcl: ceil(10 / 25) = 1
    - bags_per_container: ceil(1000 / 1) = 1000
    - pallets: ceil(1000 / 50) = 20
    """
    parsed = {
        "lpo_invoice": {
            "items": [
                {
                    "commodity": "rice",
                    "quantity_in_bags": "1000",
                    "unit": "9.80",
                    "packaging": "10KG",
                }
            ]
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    
    assert sc["container_size"] == 20
    assert sc["quantity_in_mt"] == 10.0
    assert sc["fcl"] == 1
    assert sc["bags"] == 1000
    assert sc["bags_per_container"] == 1000
    assert sc["pallets"] == 20


def test_shipment_logistics_missing_commodity():
    """If commodity is missing, container_size should be None."""
    parsed = {
        "lpo_invoice": {
            "items": [
                {
                    "commodity": None,
                    "quantity_in_bags": "1000",
                    "unit": "9.80",
                    "packaging": "10KG",
                }
            ]
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
            "items": [
                {
                    "commodity": "rice",
                    "quantity_in_bags": "1000",
                    "unit": "9.80",
                    "packaging": None,
                }
            ]
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


def test_normalize_payment_terms_percent_spacing():
    """Spaces between a number and % are removed in API output."""
    assert (
        normalize_payment_terms("Payment 100 % CAD Bank to Bank.")
        == "Payment 100% CAD Bank to Bank."
    )
    assert normalize_payment_terms("100% CAD") == "100% CAD"
    assert normalize_payment_terms("50.5  % advance") == "50.5% advance"
    assert normalize_payment_terms(None) is None


def test_shipment_logistics_multi_item_same_packaging():
    """
    Multi-item LPO with same packaging (both 10kg).
    Item 1: 10,000 bags × 10kg = 100 MT @ 11.50/bag = 115,000
    Item 2: 5,000 bags × 10kg = 50 MT @ 12.00/bag = 60,000
    
    Aggregates:
    - Total bags: 15,000
    - Total MT: 150 MT
    - Total price: 175,000
    - FCL: ceil(150 / 25) = 6
    - Bags per container: ceil(15000 / 6) = 2500
    - Pallets: ceil(15000 / 50) = 300
    - FCL per unit: 175000 / 6 = 29,166.67
    - Price per MT: 175000 / 150 = 1,166.67
    """
    parsed = {
        "lpo_invoice": {
            "items": [
                {
                    "item_code": "1-RH1-01A-0016",
                    "commodity": "rice",
                    "item": "Rice - Type A 10 Kg",
                    "quantity_in_bags": "10,000.00",
                    "unit": "11.50",
                    "packaging": "1X10KG",
                },
                {
                    "item_code": "1-RH1-01A-0017",
                    "commodity": "rice",
                    "item": "Rice - Type B 10 Kg",
                    "quantity_in_bags": "5,000.00",
                    "unit": "12.00",
                    "packaging": "1X10KG",
                }
            ]
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    
    assert sc["container_size"] == 20
    assert sc["quantity_in_mt"] == 150.0
    assert sc["fcl"] == 6
    assert sc["bags"] == 15000
    assert sc["bags_per_container"] == 2500
    assert sc["pallets"] == 300
    assert sc["fcl_per_unit"] == 29166.67
    assert sc["price_per_mt"] == 1166.67


def test_shipment_logistics_multi_item_mixed_packaging():
    """
    Multi-item LPO with mixed packaging (from the provided image example).
    Item 1: 25,000 bags × 10kg = 250 MT @ 11.85/bag = 296,250.00
    Item 2: 10,000 bags × 25kg = 250 MT @ 29.63/bag = 296,300.00
    
    Aggregates:
    - Total bags: 35,000
    - Total MT: 500 MT
    - Total price: 592,550.00
    - Container size: 20ft (rice)
    - FCL: ceil(500 / 25) = 20 containers
    - Bags per container: ceil(35000 / 20) = 1750 bags/container (mixed)
    - Pallets: ceil(35000 / 50) = 700 pallets
    - FCL per unit: 592550 / 20 = 29,627.50
    - Price per MT: 592550 / 500 = 1,185.10
    """
    parsed = {
        "lpo_invoice": {
            "items": [
                {
                    "item_code": "1-RH1-01A-0016",
                    "commodity": "rice",
                    "item": "Rice - Melyar 10 Kg",
                    "quantity_in_bags": "25,000.00",
                    "unit": "11.85",
                    "packaging": "1X10KG",
                },
                {
                    "item_code": "1-RH1-01A-0081",
                    "commodity": "rice",
                    "item": "Rice - Melyar Rice 25 Kg",
                    "quantity_in_bags": "10,000.00",
                    "unit": "29.63",
                    "packaging": "1X25KG",
                }
            ]
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    
    assert sc["container_size"] == 20
    assert sc["quantity_in_mt"] == 500.0
    assert sc["fcl"] == 20
    assert sc["bags"] == 35000
    assert sc["bags_per_container"] == 1750
    assert sc["pallets"] == 700
    assert sc["fcl_per_unit"] == 29627.5
    assert sc["price_per_mt"] == 1185.1


def test_shipment_logistics_empty_items():
    """If items array is empty, all calculations should be None."""
    parsed = {
        "lpo_invoice": {
            "items": []
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    
    assert sc["container_size"] is None
    assert sc["quantity_in_mt"] is None
    assert sc["fcl"] is None
    assert sc["bags"] is None
    assert sc["bags_per_container"] is None
    assert sc["pallets"] is None
    assert sc["fcl_per_unit"] is None
    assert sc["price_per_mt"] is None


def test_shipment_logistics_three_items():
    """
    Three items with different packaging.
    Item 1: 5,000 bags × 10kg = 50 MT @ 10.00/bag = 50,000
    Item 2: 3,000 bags × 25kg = 75 MT @ 25.00/bag = 75,000
    Item 3: 2,000 bags × 40kg = 80 MT @ 40.00/bag = 80,000
    
    Aggregates:
    - Total bags: 10,000
    - Total MT: 205 MT
    - Total price: 205,000
    - FCL: ceil(205 / 25) = 9
    - Bags per container: ceil(10000 / 9) = 1112
    - Pallets: ceil(10000 / 50) = 200
    - FCL per unit: 205000 / 9 = 22,777.78
    - Price per MT: 205000 / 205 = 1,000.00
    """
    parsed = {
        "lpo_invoice": {
            "items": [
                {
                    "commodity": "rice",
                    "quantity_in_bags": "5,000",
                    "unit": "10.00",
                    "packaging": "1X10KG",
                },
                {
                    "commodity": "rice",
                    "quantity_in_bags": "3,000",
                    "unit": "25.00",
                    "packaging": "1X25KG",
                },
                {
                    "commodity": "rice",
                    "quantity_in_bags": "2,000",
                    "unit": "40.00",
                    "packaging": "1X40KG",
                }
            ]
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    
    assert sc["container_size"] == 20
    assert sc["quantity_in_mt"] == 205.0
    assert sc["fcl"] == 9
    assert sc["bags"] == 10000
    assert sc["bags_per_container"] == 1112
    assert sc["pallets"] == 200
    assert sc["fcl_per_unit"] == 22777.78
    assert sc["price_per_mt"] == 1000.0
