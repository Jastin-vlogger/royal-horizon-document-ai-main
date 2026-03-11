"""Unit tests for shipment_calculations post-processing (logistics + price reconciliation)."""

import pytest

from src.core.shipment_calculations import (
    calculate_shipment_logistics,
    parse_currency_value,
    parse_packaging_kg,
)


def test_is_matching_mt_within_tolerance():
    """9.80/bag * 100 bags/MT = 980 vs 985 → 0.5% diff → True."""
    parsed = {
        "lpo_invoice": {
            "unit": "9.80",
            "packaging": "10 Kg",
        },
        "performa_invoice": {
            "quantity": "480.000 MT (+- 5%)",
            "price_per_mton": "USD 985.00 PMT",
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    assert sc["price_reconciled"] is True
    assert sc["lpo_price_per_mt"] == 980.00
    assert sc["pi_price_per_mt"] == 985.00


def test_is_matching_mt_mismatch():
    """Large price gap → price_reconciled False, both price fields present."""
    parsed = {
        "lpo_invoice": {
            "unit": "9.80",
            "packaging": "10 Kg",
        },
        "performa_invoice": {
            "quantity": "100.00 MT",
            "price_per_mton": "USD 1500.00 PMT",
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    assert sc["price_reconciled"] is False
    assert sc["lpo_price_per_mt"] == 980.00
    assert sc["pi_price_per_mt"] == 1500.00


def test_is_matching_mt_null_on_missing_price():
    """If price_per_mton is null → price_reconciled, lpo_price_per_mt, pi_price_per_mt are None."""
    parsed = {
        "lpo_invoice": {
            "unit": "9.80",
            "packaging": "10 Kg",
        },
        "performa_invoice": {
            "quantity": "100.00 MT",
            "price_per_mton": None,
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    assert sc["price_reconciled"] is None
    assert sc["lpo_price_per_mt"] is None
    assert sc["pi_price_per_mt"] is None


def test_is_matching_mt_null_on_missing_lpo_unit():
    """Missing LPO unit → price reconciliation fields None."""
    parsed = {
        "lpo_invoice": {
            "unit": None,
            "packaging": "10 Kg",
        },
        "performa_invoice": {
            "quantity": "100.00 MT",
            "price_per_mton": "USD 985.00 PMT",
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    assert sc["price_reconciled"] is None
    assert sc["lpo_price_per_mt"] is None
    assert sc["pi_price_per_mt"] is None


def test_shipment_logistics_example():
    """Quantity 2500 MT, packaging 10 Kg → fcl, container_size, bags_per_container, bags, pallets."""
    parsed = {
        "lpo_invoice": {
            "unit": "9.80",
            "packaging": "10 Kg",
        },
        "performa_invoice": {
            "quantity": "2500.00 MT",
            "price_per_mton": "USD 985.00 PMT",
        },
        "metadata": None,
    }
    result = calculate_shipment_logistics(parsed)
    sc = result["shipment_calculations"]
    # quantity_mt 2500 > 25 → 40ft, capacity 26 MT
    assert sc["container_size"] == "40ft"
    assert sc["fcl"] == 97  # ceil(2500 / 26)
    assert sc["bags_per_container"] == 2600  # 26000 / 10
    assert sc["bags"] == 250000
    assert sc["pallets"] == 5000  # ceil(250000 / 50)


def test_parse_currency_value():
    """parse_currency_value strips USD, PMT, commas."""
    assert parse_currency_value("USD 985.00 PMT") == 985.0
    assert parse_currency_value("9.80") == 9.8
    assert parse_currency_value("470,400.00") == 470400.0


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
