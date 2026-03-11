"""Tests for cost calculator."""

from src.utils.cost_calculator import calculate_cost, get_pricing_table


def test_get_pricing_table():
    table = get_pricing_table()
    assert "gpt-4o" in table
    assert table["gpt-4o"]["input"] == 2.50
    assert table["gpt-4o"]["output"] == 10.00


def test_calculate_cost():
    # 1M input + 1M output for gpt-4o = 2.50 + 10.00 = 12.50
    c = calculate_cost("gpt-4o", 1_000_000, 1_000_000)
    assert abs(c - 12.50) < 0.01
    assert calculate_cost("gpt-4o", 0, 0) == 0.0
