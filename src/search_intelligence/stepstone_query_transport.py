"""Pure StepStone query-transport construction and validation contracts.

The public StepStone result URL is treated as a transport boundary. A logical
query must not be considered supported merely because one ordering returns
cards. The same filter set must remain usable and leak-free across at least two
permutations before a transport can pass this diagnostic contract.

This module performs no network requests and has no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from src.connectors.stepstone import (
    STEPSTONE_BASE_URL,
    build_stepstone_search_url,
    slugify_stepstone_segment,
)

TRANSPORT_SLUG_PATH = "slug_path"
TRANSPORT_BASE_PATH_PLUS_Q = "base_path_plus_q"
TRANSPORT_GENERIC_JOBS_PLUS_Q = "generic_jobs_plus_q"
SUPPORTED_TRANSPORTS = (
    TRANSPORT_SLUG_PATH,
    TRANSPORT_BASE_PATH_PLUS_Q,
    TRANSPORT_GENERIC_JOBS_PLUS_Q,
)


@dataclass(frozen=True)
class StepStoneQueryTransport:
    mode: str
    base_search_term: str
    location: str
    intended_query: str
    requested_url: str
    q_parameter_required: bool


def build_query_transport(
    *,
    mode: str,
    base_search_term: str,
    location: str,
    intended_query: str,
) -> StepStoneQueryTransport:
    """Build one explicit candidate transport without claiming it is valid."""
    if mode not in SUPPORTED_TRANSPORTS:
        raise ValueError(f"Unsupported StepStone query transport: {mode}")

    if mode == TRANSPORT_SLUG_PATH:
        requested_url = build_stepstone_search_url(
            search_term=intended_query,
            search_location=location,
        )
        q_parameter_required = False
    else:
        location_slug = slugify_stepstone_segment(location)
        query_string = urlencode({"q": intended_query})
        if mode == TRANSPORT_BASE_PATH_PLUS_Q:
            base_slug = slugify_stepstone_segment(base_search_term)
            path = f"/jobs/{base_slug}/in-{location_slug}"
        else:
            path = f"/jobs/in-{location_slug}"
        requested_url = f"{STEPSTONE_BASE_URL}{path}?{query_string}"
        q_parameter_required = True

    return StepStoneQueryTransport(
        mode=mode,
        base_search_term=base_search_term,
        location=location,
        intended_query=intended_query,
        requested_url=requested_url,
        q_parameter_required=q_parameter_required,
    )


def q_parameter(url: str) -> str | None:
    values = parse_qs(urlparse(url).query, keep_blank_values=True).get("q", [])
    return values[0] if values else None


def assess_transport_integrity(
    *,
    transport: StepStoneQueryTransport,
    final_url: str,
) -> dict[str, Any]:
    requested_q = q_parameter(transport.requested_url)
    final_q = q_parameter(final_url)

    if transport.q_parameter_required:
        requested_query_preserved = requested_q == transport.intended_query
        final_query_preserved = final_q == transport.intended_query
        integrity_pass = requested_query_preserved and final_query_preserved
    else:
        requested_query_preserved = None
        final_query_preserved = None
        integrity_pass = True

    return {
        "mode": transport.mode,
        "q_parameter_required": transport.q_parameter_required,
        "requested_q": requested_q,
        "final_q": final_q,
        "requested_query_preserved": requested_query_preserved,
        "final_query_preserved": final_query_preserved,
        "transport_integrity_pass": integrity_pass,
    }


def assess_permutation_pair(
    first: dict[str, Any],
    second: dict[str, Any],
    *,
    page_card_limit: int = 25,
) -> dict[str, Any]:
    """Apply the strict transport contract to two orders of the same filter set."""
    first_aliases = tuple(str(value) for value in first["filter_aliases"])
    second_aliases = tuple(str(value) for value in second["filter_aliases"])
    same_filter_set = sorted(first_aliases) == sorted(second_aliases)
    distinct_permutations = first_aliases != second_aliases
    page_types_equal = first["page_type"] == second["page_type"]
    leakage_free = first["leakage_count"] == 0 and second["leakage_count"] == 0
    full_page_both = (
        first["parsed_card_count"] == page_card_limit
        and second["parsed_card_count"] == page_card_limit
    )
    zero_nonzero_divergence = (
        (first["parsed_card_count"] == 0)
        != (second["parsed_card_count"] == 0)
    )
    transport_integrity_both = (
        first["transport_integrity_pass"]
        and second["transport_integrity_pass"]
    )
    contract_pass = all(
        (
            same_filter_set,
            distinct_permutations,
            page_types_equal,
            leakage_free,
            full_page_both,
            not zero_nonzero_divergence,
            transport_integrity_both,
        )
    )

    if contract_pass:
        diagnosis = "permutation_invariant_full_page_transport"
    elif zero_nonzero_divergence:
        diagnosis = "same_filter_set_zero_nonzero_divergence"
    elif not transport_integrity_both:
        diagnosis = "logical_query_not_preserved_by_transport"
    elif not leakage_free:
        diagnosis = "excluded_company_leakage"
    elif not page_types_equal:
        diagnosis = "permutation_changes_page_type"
    elif not full_page_both:
        diagnosis = "transport_not_stably_full_page"
    else:
        diagnosis = "transport_contract_not_met"

    return {
        "contract_pass": contract_pass,
        "diagnosis": diagnosis,
        "same_filter_set": same_filter_set,
        "distinct_permutations": distinct_permutations,
        "page_types_equal": page_types_equal,
        "leakage_free_both": leakage_free,
        "full_page_both": full_page_both,
        "zero_nonzero_divergence": zero_nonzero_divergence,
        "transport_integrity_both": transport_integrity_both,
        "first_card_count": first["parsed_card_count"],
        "second_card_count": second["parsed_card_count"],
        "first_page_type": first["page_type"],
        "second_page_type": second["page_type"],
    }
