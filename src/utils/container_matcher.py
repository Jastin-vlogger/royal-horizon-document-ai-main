"""Container matching utilities with Levenshtein-based fuzzy matching and fallback support."""

from typing import Optional

from src.config.logger import logger
from src.schemas.response import BillOfLadingContainerRow

FALLBACK_THRESHOLD = 0.80


def _normalize_container_number(container_no: str) -> str:
    """Normalize container number: uppercase, alphanumeric only."""
    if not container_no:
        return ""
    return "".join(c.upper() for c in container_no if c.isalnum())


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute the Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if not s2:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr_row.append(min(
                curr_row[j] + 1,
                prev_row[j + 1] + 1,
                prev_row[j] + cost,
            ))
        prev_row = curr_row

    return prev_row[-1]


def _calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate similarity using Levenshtein distance.

    Returns a value between 0.0 (completely different) and 1.0 (identical).
    For container numbers like MRSU5837270 vs MSUU5837270, a single-character
    substitution yields ~0.909 similarity, which correctly exceeds the 0.90
    fallback threshold.
    """
    if not str1 or not str2:
        return 0.0
    if str1 == str2:
        return 1.0

    max_len = max(len(str1), len(str2))
    distance = _levenshtein_distance(str1, str2)
    return 1.0 - (distance / max_len)


def find_matching_container(
    target_container_no: str,
    bill_containers: list[BillOfLadingContainerRow],
    threshold: float = 0.85,
) -> tuple[Optional[BillOfLadingContainerRow], float, str]:
    """
    Find a matching container from bill extraction using exact or fuzzy matching.

    Returns:
        Tuple of (matched_container_or_none, similarity_score, match_type).
        match_type is one of: "exact", "fuzzy", "none".
    """
    if not target_container_no or not bill_containers:
        return None, 0.0, "none"

    normalized_target = _normalize_container_number(target_container_no)

    for container in bill_containers:
        normalized_bill = _normalize_container_number(container.container_no)
        if normalized_bill == normalized_target:
            logger.debug(
                f"Exact match: {target_container_no} -> {container.container_no}"
            )
            return container, 1.0, "exact"

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
            f"Fuzzy match (score={best_score:.3f}): "
            f"{target_container_no} -> {best_match.container_no}"
        )
        return best_match, best_score, "fuzzy"

    logger.debug(
        f"No match for {target_container_no} at threshold {threshold} "
        f"(best={best_score:.3f} -> {best_match.container_no if best_match else 'N/A'})"
    )
    return None, best_score, "none"


def filter_containers_by_packaging_list(
    bill_containers: list[BillOfLadingContainerRow],
    packaging_container_numbers: list[str],
    fuzzy_threshold: float = 0.85,
) -> list[BillOfLadingContainerRow]:
    """
    Filter bill containers to keep only those present in packaging list.

    Matching strategy (per packaging container):
      1. Exact match on normalized container number.
      2. Fuzzy match at ``fuzzy_threshold`` (default 0.85).
      3. Relaxed fallback at FALLBACK_THRESHOLD (0.80) for any packaging
         containers still unmatched after the first pass. This catches
         up to 2-character OCR misreads in 10-11 char container numbers
         (e.g. MRSU5837270 misread as MSUU5837270 → similarity ~0.818).
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

    matched_bill_indices: set[int] = set()
    unmatched_pkg: list[str] = []

    # --- Pass 1: exact + fuzzy at fuzzy_threshold ---
    for pkg_no in packaging_container_numbers:
        unmatched_bills = [
            c for i, c in enumerate(bill_containers) if i not in matched_bill_indices
        ]
        match, score, match_type = find_matching_container(
            pkg_no, unmatched_bills, threshold=fuzzy_threshold,
        )
        if match:
            idx = next(
                i for i, c in enumerate(bill_containers)
                if c.container_no == match.container_no and i not in matched_bill_indices
            )
            matched_bill_indices.add(idx)
            logger.info(
                f"Pass-1 {match_type} match: pkg={pkg_no} -> bill={match.container_no} "
                f"(score={score:.3f})"
            )
        else:
            unmatched_pkg.append(pkg_no)

    # --- Pass 2: high-confidence fallback for remaining unmatched packaging containers ---
    if unmatched_pkg:
        logger.info(
            f"Pass-2 fallback: {len(unmatched_pkg)} unmatched packaging containers, "
            f"threshold={FALLBACK_THRESHOLD}"
        )
        still_unmatched: list[str] = []
        for pkg_no in unmatched_pkg:
            remaining_bills = [
                c for i, c in enumerate(bill_containers) if i not in matched_bill_indices
            ]
            if not remaining_bills:
                still_unmatched.append(pkg_no)
                continue

            match, score, match_type = find_matching_container(
                pkg_no, remaining_bills, threshold=FALLBACK_THRESHOLD,
            )
            if match:
                idx = next(
                    i for i, c in enumerate(bill_containers)
                    if c.container_no == match.container_no and i not in matched_bill_indices
                )
                matched_bill_indices.add(idx)
                logger.info(
                    f"Pass-2 fallback match: pkg={pkg_no} -> bill={match.container_no} "
                    f"(score={score:.3f})"
                )
            else:
                still_unmatched.append(pkg_no)

        if still_unmatched:
            logger.warning(
                f"Unmatched packaging containers after fallback: {still_unmatched}"
            )

    # Preserve original bill ordering
    filtered = [c for i, c in enumerate(bill_containers) if i in matched_bill_indices]

    logger.info(
        f"Container filtering complete: {len(filtered)}/{len(bill_containers)} "
        f"bill containers matched from {len(packaging_container_numbers)} packaging entries"
    )

    return filtered
