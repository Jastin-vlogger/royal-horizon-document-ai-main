"""Tests for stock-sheet table parsing helpers."""

from src.core.stock_sheet.constants import CANONICAL_COLUMNS
from src.core.stock_sheet.table_parser import map_rows_to_canonical, parse_stock_table
from src.core.stock_sheet.total_row import repair_total_row_from_tables


def test_parse_stock_table_merges_tables_and_slices_stock_columns():
    raw_tables = [
        [
            ["Item", "Unit", "Abu Dhabi Musaffah", "Total Bags", "Remarks"],
            ["Row 1", "20", "1,250", "1,250", ""],
        ],
        [
            ["Item", "Unit", "Abu Dhabi Musaffah", "Total Bags", "Remarks"],
            ["Row 2", "10", "-", "500", "N/A"],
        ],
    ]

    headers, rows = parse_stock_table(raw_tables)

    assert headers == CANONICAL_COLUMNS
    assert list(rows[0].keys()) == CANONICAL_COLUMNS
    assert rows[0]["Unit"] == 20
    assert rows[0]["Abu Dhabi Musaffah"] == 1250
    assert rows[0]["Total Bags"] == 1250
    assert rows[0]["ALAin Mazyad"] is None
    assert rows[1]["Unit"] == 10
    assert rows[1]["Abu Dhabi Musaffah"] is None
    assert rows[1]["Total Bags"] == 500


def test_map_rows_to_canonical_enforces_full_schema():
    rows = map_rows_to_canonical(
        [
            {
                "unit": 20,
                "dic 9 (strategic)": 450,
                "totalbags": 470,
            }
        ]
    )

    assert rows[0]["Unit"] == 20
    assert rows[0]["DIC9 (Strategic)"] == 450
    assert rows[0]["Total Bags"] == 470
    assert list(rows[0].keys()) == CANONICAL_COLUMNS
    assert rows[0]["Abu Dhabi Musaffah"] is None


def test_repair_total_row_from_tables_keeps_tail_columns_aligned():
    early_table = [
        [
            "",
            "Unit",
            "Abu Dhabi Musaffah",
            "Al Ain Mazyad",
            "Al Ain Maryad (Strategic)",
            "Al Ain Maryad (Acc)",
            "AJ Ain Sanaya B Block A",
            "Al Ain Sanaya B Block - B",
            "AI Ain Sanaya B Block C",
            "Al Ain Sanaya B Block - D",
            "Mazyad (6 months contr)",
            "DIC 1",
            "DIC 2",
            "DIC 3",
            "DIC 4",
        ],
        [
            "Qty",
            "",
            "8,328",
            "12,779",
            "47,400",
            "-",
            "-",
            ".",
            "-",
            ".",
            "109,137",
            "-",
            "-",
            "-",
            "-",
        ],
    ]
    tail_table = [
        [
            "DIC 5",
            "DIC 6",
            "DIC 7",
            "DIC 8",
            "DIC 9",
            "DIC 9 (Strategic)",
            "DIC 10",
            "DIC 11",
            "Sharja Sajaa Block B",
            "Sharja Sajaa Block C",
            "Total Bags",
            "Total MT",
            "Shipment No.",
        ],
        [
            "-",
            "84,921",
            "48,089",
            "49,702",
            "60,000",
            "8,528",
            "-",
            "28,232",
            "-",
            "-",
            "457,116",
            "6,574",
            "",
        ],
    ]

    row = repair_total_row_from_tables(early_table, tail_table)

    assert row["Abu Dhabi Musaffah"] == 8328
    assert row["ALAin Mazyad"] == 12779
    assert row["AlAin Maryad (Strategic)"] == 47400
    assert row["Mazyad (6 months contr)"] == 109137
    assert row["DIC5"] is None
    assert row["DIC6"] == 84921
    assert row["DIC7"] == 48089
    assert row["DIC8"] == 49702
    assert row["DIC9"] == 60000
    assert row["DIC9 (Strategic)"] == 8528
    assert row["DIC10"] is None
    assert row["DIC11"] == 28232
    assert row["Sharja Sajaa Block B"] is None
    assert row["Sharja Sajaa Block C"] is None
    assert row["Total Bags"] == 457116
