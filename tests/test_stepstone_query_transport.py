from src.search_intelligence.stepstone_query_transport import (
    TRANSPORT_BASE_PATH_PLUS_Q,
    TRANSPORT_GENERIC_JOBS_PLUS_Q,
    TRANSPORT_SLUG_PATH,
    assess_permutation_pair,
    assess_transport_integrity,
    build_query_transport,
    q_parameter,
)


def test_q_transport_preserves_quotes_parentheses_and_ampersand() -> None:
    intended = (
        'Machine Learning Engineer NOT "Technische Informationsbibliothek (TIB)" '
        'NOT "1&1"'
    )
    transport = build_query_transport(
        mode=TRANSPORT_BASE_PATH_PLUS_Q,
        base_search_term="Machine Learning Engineer",
        location="Hannover",
        intended_query=intended,
    )

    assert q_parameter(transport.requested_url) == intended
    assert "/jobs/machine-learning-engineer/in-hannover?" in transport.requested_url
    integrity = assess_transport_integrity(
        transport=transport,
        final_url=transport.requested_url,
    )
    assert integrity["transport_integrity_pass"] is True


def test_generic_q_transport_uses_neutral_jobs_path() -> None:
    transport = build_query_transport(
        mode=TRANSPORT_GENERIC_JOBS_PLUS_Q,
        base_search_term="Machine Learning Engineer",
        location="Hannover",
        intended_query='Machine Learning Engineer NOT "HDI"',
    )

    assert "/jobs/in-hannover?" in transport.requested_url
    assert q_parameter(transport.requested_url) == transport.intended_query


def test_slug_transport_is_recorded_but_does_not_claim_query_preservation() -> None:
    transport = build_query_transport(
        mode=TRANSPORT_SLUG_PATH,
        base_search_term="Machine Learning Engineer",
        location="Hannover",
        intended_query='Machine Learning Engineer NOT "1&1"',
    )
    integrity = assess_transport_integrity(
        transport=transport,
        final_url=transport.requested_url,
    )

    assert q_parameter(transport.requested_url) is None
    assert integrity["requested_query_preserved"] is None
    assert integrity["final_query_preserved"] is None


def _page(*, aliases: list[str], cards: int, leakage: int = 0) -> dict[str, object]:
    return {
        "filter_aliases": aliases,
        "page_type": "result_page_with_cards" if cards else "explicit_zero_results",
        "parsed_card_count": cards,
        "leakage_count": leakage,
        "transport_integrity_pass": True,
    }


def test_contract_passes_only_for_two_full_leak_free_permutations() -> None:
    first = _page(aliases=["A", "B", "C"], cards=25)
    second = _page(aliases=["C", "B", "A"], cards=25)

    result = assess_permutation_pair(first, second)

    assert result["contract_pass"] is True
    assert result["diagnosis"] == "permutation_invariant_full_page_transport"


def test_zero_nonzero_divergence_fails_transport_contract() -> None:
    first = _page(aliases=["A", "B", "C"], cards=0)
    second = _page(aliases=["C", "B", "A"], cards=25)

    result = assess_permutation_pair(first, second)

    assert result["contract_pass"] is False
    assert result["zero_nonzero_divergence"] is True
    assert result["diagnosis"] == "same_filter_set_zero_nonzero_divergence"


def test_stripped_final_q_fails_transport_integrity() -> None:
    transport = build_query_transport(
        mode=TRANSPORT_BASE_PATH_PLUS_Q,
        base_search_term="Machine Learning Engineer",
        location="Hannover",
        intended_query='Machine Learning Engineer NOT "HDI"',
    )

    integrity = assess_transport_integrity(
        transport=transport,
        final_url="https://www.stepstone.de/jobs/machine-learning-engineer/in-hannover",
    )

    assert integrity["requested_query_preserved"] is True
    assert integrity["final_query_preserved"] is False
    assert integrity["transport_integrity_pass"] is False
