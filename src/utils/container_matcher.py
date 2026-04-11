"""Container matching utilities with fuzzy matching support."""

from typing import Optional

from src.config.logger import logger
from src.schemas.response import BillOfLadingContainerRow


def _normalize_container_number(container_no: str) -> str:
    """
    Normalize container number for comparison.
    
    - Convert to uppercase
    - Remove spaces, hyphens, and other separators
    - Keep only alphanumeric characters
    """
    if not container_no:
        return ""
    return "".join(c.upper() for c in container_no if c.isalnum())


def _calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate similarity ratio between two strings using simple character matching.
    
    Returns a value between 0.0 (no match) and 1.0 (exact match).
    Uses a simple approach: count matching characters in order.
    """
    if not str1 or not str2:
        return 0.0
    
    if str1 == str2:
        return 1.0
    
    # Simple Levenshtein-like approach for fuzzy matching
    len1, len2 = len(str1), len(str2)
    max_len = max(len1, len2)
    
    if max_len == 0:
        return 1.0
    
    # Count matching characters at same positions
    matches = sum(c1 == c2 for c1, c2 in zip(str1, str2))
    
    # Penalize length difference
    length_penalty = abs(len1 - len2) / max_len
    
    # Calculate similarity score
    similarity = (matches / max_len) * (1 - length_penalty * 0.5)
    
    return similarity


def find_matching_container(
    target_container_no: str,
    bill_containers: list[BillOfLadingContainerRow],
    threshold: float = 0.85,
) -> Optional[BillOfLadingContainerRow]:
    """
    Find a matching container from bill extraction using exact or fuzzy matching.
    
    Args:
        target_container_no: Container number from packaging list
        bill_containers: List of containers from bill extraction
        threshold: Minimum similarity score for fuzzy match (0.0 to 1.0)
    
    Returns:
        Matching container or None if no match found
    """
    if not target_container_no or not bill_containers:
        return None
    
    normalized_target = _normalize_container_number(target_container_no)
    
    # First pass: exact match
    for container in bill_containers:
        normalized_bill = _normalize_container_number(container.container_no)
        if normalized_bill == normalized_target:
            logger.debug(f"Exact match found: {target_container_no} -> {container.container_no}")
            return container
    
    # Second pass: fuzzy match
    best_match: Optional[BillOfLadingContainerRow] = None
    best_score = 0.0
    
    for container in bill_containers:
        normalized_bill = _normalize_container_number(container.container_no)
        similarity = _calculate_similarity(normalized_target, normalized_bill)
        
        if similarity > best_score:
            best_score = similarity
            best_match = container
    
    if best_score >= threshold and best_match:
        logger.info(
            f"Fuzzy match found (score={best_score:.2f}): "
            f"{target_container_no} -> {best_match.container_no}"
        )
        return best_match
    
    logger.warning(
        f"No match found for container {target_container_no} "
        f"(best score: {best_score:.2f}, threshold: {threshold})"
    )
    return None


def filter_containers_by_packaging_list(
    bill_containers: list[BillOfLadingContainerRow],
    packaging_container_numbers: list[str],
    fuzzy_threshold: float = 0.85,
) -> list[BillOfLadingContainerRow]:
    """
    Filter bill containers to keep only those present in packaging list.
    
    Maintains the original order from bill extraction.
    Uses exact matching first, then falls back to fuzzy matching.
    
    Args:
        bill_containers: Original list of containers from bill extraction
        packaging_container_numbers: List of container numbers from packaging list
        fuzzy_threshold: Minimum similarity for fuzzy matching (0.0 to 1.0)
    
    Returns:
        Filtered list of containers in original order
    """
    if not packaging_container_numbers:
        logger.warning("No packaging container numbers provided, returning all bill containers")
        return bill_containers
    
    if not bill_containers:
        logger.warning("No bill containers to filter")
        return []
    
    logger.debug(
        f"Filtering {len(bill_containers)} bill containers against "
        f"{len(packaging_container_numbers)} packaging list containers"
    )
    
    # Track which bill containers have been matched
    matched_containers: list[BillOfLadingContainerRow] = []
    matched_bill_indices: set[int] = set()
    
    # For each packaging container, find its match in bill containers
    for pkg_container_no in packaging_container_numbers:
        # Search only in unmatched bill containers
        unmatched_bill_containers = [
            container for i, container in enumerate(bill_containers)
            if i not in matched_bill_indices
        ]
        
        match = find_matching_container(
            pkg_container_no,
            unmatched_bill_containers,
            threshold=fuzzy_threshold,
        )
        
        if match:
            # Find the original index to track it
            original_index = next(
                i for i, c in enumerate(bill_containers)
                if c.container_no == match.container_no and i not in matched_bill_indices
            )
            matched_bill_indices.add(original_index)
            matched_containers.append(match)
    
    # Sort matched containers by their original order in bill extraction
    matched_with_indices = [
        (i, container) for i, container in enumerate(bill_containers)
        if i in matched_bill_indices
    ]
    matched_with_indices.sort(key=lambda x: x[0])
    filtered_containers = [container for _, container in matched_with_indices]
    
    logger.info(
        f"Container filtering complete: {len(filtered_containers)}/{len(bill_containers)} "
        f"containers matched from packaging list"
    )
    
    return filtered_containers
