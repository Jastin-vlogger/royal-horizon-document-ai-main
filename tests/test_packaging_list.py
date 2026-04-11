"""Tests for packaging list extraction and container filtering."""

import pytest

from src.schemas.packaging_list import PackagingListContainerInfo, PackagingListExtraction
from src.schemas.response import BillOfLadingContainerRow
from src.utils.container_matcher import (
    _calculate_similarity,
    _normalize_container_number,
    filter_containers_by_packaging_list,
    find_matching_container,
)


class TestContainerMatcher:
    """Test container matching utilities."""

    def test_normalize_container_number(self):
        """Test container number normalization."""
        assert _normalize_container_number("TCLU3895166") == "TCLU3895166"
        assert _normalize_container_number("TCLU 3895166") == "TCLU3895166"
        assert _normalize_container_number("tclu-3895166") == "TCLU3895166"
        assert _normalize_container_number("TCLU-389-5166") == "TCLU3895166"
        assert _normalize_container_number("") == ""

    def test_calculate_similarity_exact_match(self):
        """Test similarity calculation for exact matches."""
        assert _calculate_similarity("TCLU3895166", "TCLU3895166") == 1.0

    def test_calculate_similarity_partial_match(self):
        """Test similarity calculation for partial matches."""
        # Similar strings should have high similarity
        similarity = _calculate_similarity("TCLU3895166", "TCLU3895167")
        assert 0.8 < similarity < 1.0

        # Very different strings should have low similarity
        similarity = _calculate_similarity("TCLU3895166", "ABCD1234567")
        assert similarity < 0.5

    def test_calculate_similarity_empty_strings(self):
        """Test similarity with empty strings."""
        assert _calculate_similarity("", "TCLU3895166") == 0.0
        assert _calculate_similarity("TCLU3895166", "") == 0.0

    def test_find_matching_container_exact_match(self):
        """Test finding container with exact match."""
        bill_containers = [
            BillOfLadingContainerRow(container_no="TCLU3895166", pkg_ct=1000),
            BillOfLadingContainerRow(container_no="UACU3580511", pkg_ct=1200),
        ]

        match = find_matching_container("TCLU3895166", bill_containers)
        assert match is not None
        assert match.container_no == "TCLU3895166"
        assert match.pkg_ct == 1000

    def test_find_matching_container_normalized_match(self):
        """Test finding container with normalized match."""
        bill_containers = [
            BillOfLadingContainerRow(container_no="TCLU3895166", pkg_ct=1000),
        ]

        # Test with spaces and hyphens
        match = find_matching_container("TCLU 389 5166", bill_containers)
        assert match is not None
        assert match.container_no == "TCLU3895166"

    def test_find_matching_container_fuzzy_match(self):
        """Test finding container with fuzzy match."""
        bill_containers = [
            BillOfLadingContainerRow(container_no="TCLU3895166", pkg_ct=1000),
        ]

        # OCR error: last digit different
        match = find_matching_container("TCLU3895167", bill_containers, threshold=0.85)
        assert match is not None
        assert match.container_no == "TCLU3895166"

    def test_find_matching_container_no_match(self):
        """Test finding container when no match exists."""
        bill_containers = [
            BillOfLadingContainerRow(container_no="TCLU3895166", pkg_ct=1000),
        ]

        match = find_matching_container("ABCD1234567", bill_containers)
        assert match is None

    def test_find_matching_container_empty_list(self):
        """Test finding container in empty list."""
        match = find_matching_container("TCLU3895166", [])
        assert match is None

    def test_filter_containers_by_packaging_list(self):
        """Test filtering containers based on packaging list."""
        bill_containers = [
            BillOfLadingContainerRow(container_no="TCLU3895166", pkg_ct=1000),
            BillOfLadingContainerRow(container_no="UACU3580511", pkg_ct=1200),
            BillOfLadingContainerRow(container_no="FCIU2664293", pkg_ct=1100),
        ]

        packaging_container_numbers = ["TCLU3895166", "FCIU2664293"]

        filtered = filter_containers_by_packaging_list(
            bill_containers, packaging_container_numbers
        )

        assert len(filtered) == 2
        assert filtered[0].container_no == "TCLU3895166"
        assert filtered[1].container_no == "FCIU2664293"

    def test_filter_containers_maintains_order(self):
        """Test that filtering maintains original bill order."""
        bill_containers = [
            BillOfLadingContainerRow(container_no="AAAA1111111", pkg_ct=1000),
            BillOfLadingContainerRow(container_no="BBBB2222222", pkg_ct=1200),
            BillOfLadingContainerRow(container_no="CCCC3333333", pkg_ct=1100),
            BillOfLadingContainerRow(container_no="DDDD4444444", pkg_ct=1300),
        ]

        # Packaging list in different order
        packaging_container_numbers = ["DDDD4444444", "BBBB2222222", "AAAA1111111"]

        filtered = filter_containers_by_packaging_list(
            bill_containers, packaging_container_numbers
        )

        # Should maintain bill order: AAAA, BBBB, DDDD
        assert len(filtered) == 3
        assert filtered[0].container_no == "AAAA1111111"
        assert filtered[1].container_no == "BBBB2222222"
        assert filtered[2].container_no == "DDDD4444444"

    def test_filter_containers_with_fuzzy_matching(self):
        """Test filtering with fuzzy matching enabled."""
        bill_containers = [
            BillOfLadingContainerRow(container_no="TCLU3895166", pkg_ct=1000),
            BillOfLadingContainerRow(container_no="UACU3580511", pkg_ct=1200),
        ]

        # OCR error in packaging list
        packaging_container_numbers = ["TCLU3895167", "UACU3580511"]

        filtered = filter_containers_by_packaging_list(
            bill_containers, packaging_container_numbers, fuzzy_threshold=0.85
        )

        assert len(filtered) == 2
        assert filtered[0].container_no == "TCLU3895166"
        assert filtered[1].container_no == "UACU3580511"

    def test_filter_containers_empty_packaging_list(self):
        """Test filtering with empty packaging list."""
        bill_containers = [
            BillOfLadingContainerRow(container_no="TCLU3895166", pkg_ct=1000),
        ]

        filtered = filter_containers_by_packaging_list(bill_containers, [])

        # Should return all containers when packaging list is empty
        assert len(filtered) == 1
        assert filtered[0].container_no == "TCLU3895166"

    def test_filter_containers_empty_bill_list(self):
        """Test filtering with empty bill list."""
        filtered = filter_containers_by_packaging_list(
            [], ["TCLU3895166", "UACU3580511"]
        )

        assert len(filtered) == 0


class TestPackagingListSchemas:
    """Test packaging list Pydantic schemas."""

    def test_packaging_list_container_info_creation(self):
        """Test creating PackagingListContainerInfo."""
        container = PackagingListContainerInfo(
            container_number="TCLU3895166",
            no_of_bags=1000,
            gross_weight="25292.00 KGS",
            net_weight="25000.00 KGS",
        )

        assert container.container_number == "TCLU3895166"
        assert container.no_of_bags == 1000
        assert container.gross_weight == "25292.00 KGS"
        assert container.net_weight == "25000.00 KGS"

    def test_packaging_list_container_info_with_nulls(self):
        """Test creating PackagingListContainerInfo with null values."""
        container = PackagingListContainerInfo(
            container_number="TCLU3895166",
            no_of_bags=None,
            gross_weight=None,
            net_weight=None,
        )

        assert container.container_number == "TCLU3895166"
        assert container.no_of_bags is None
        assert container.gross_weight is None
        assert container.net_weight is None

    def test_packaging_list_extraction_creation(self):
        """Test creating PackagingListExtraction."""
        extraction = PackagingListExtraction(
            brand="AL MUSTSHAR",
            expiry_date="08/2027",
            packing_description="20KG POUCH BAG",
            container_info=[
                PackagingListContainerInfo(
                    container_number="TCLU3895166",
                    no_of_bags=1000,
                    gross_weight="25292.00 KGS",
                    net_weight="25000.00 KGS",
                ),
            ],
            total_bags=1000,
            total_gross_weight="25292.00 KGS",
            total_net_weight="25000.00 KGS",
            container_number_list=["TCLU3895166"],
        )

        assert extraction.brand == "AL MUSTSHAR"
        assert extraction.expiry_date == "08/2027"
        assert len(extraction.container_info) == 1
        assert len(extraction.container_number_list) == 1

    def test_packaging_list_extraction_empty_containers(self):
        """Test PackagingListExtraction with empty containers."""
        extraction = PackagingListExtraction(
            brand="AL MUSTSHAR",
            expiry_date=None,
            packing_description=None,
            container_info=None,
            total_bags=None,
            total_gross_weight=None,
            total_net_weight=None,
            container_number_list=None,
        )

        assert extraction.brand == "AL MUSTSHAR"
        assert extraction.container_info == []
        assert extraction.container_number_list == []

    def test_packaging_list_container_number_stripping(self):
        """Test that container numbers are stripped of whitespace."""
        container = PackagingListContainerInfo(
            container_number="  TCLU3895166  ",
            no_of_bags=1000,
        )

        assert container.container_number == "TCLU3895166"
