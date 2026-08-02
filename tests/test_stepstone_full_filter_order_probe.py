from pathlib import Path

from scripts.run_stepstone_full_filter_order_probe import (
    build_order_strategies,
    diagnose_order_results,
)


RUNNER = Path("scripts/run_stepstone_full_filter_order_probe.py")


def _candidate(
    rank: int,
    alias: str,
    *,
    parentheses: bool = False,
) -> dict[str, object]:
    return {
        "rank": rank,
        "company_key": f"company_{rank}",
        "company_name": f"Company {rank}",
        "card_count": 1,
        "filter_alias": alias,
        "filter_alias_length": len(alias),
        "contains_parentheses": parentheses,
        "word_count": len(alias.split()),
    }


def test_runner_is_bounded_read_only_and_diagnostic_only() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "DEFAULT_MAX_REQUESTS = 8" in source
    assert "DEFAULT_COMPANY_COUNT = 5" in source
    assert '"page_one_only": True' in source
    assert '"diagnostic_only": True' in source
    assert '"production_order_policy_allowed": False' in source
    assert '"no_pagination": True' in source
    assert '"no_detail_pages": True' in source
    assert '"no_database_write": True' in source
    assert '"no_candidate_creation": True' in source
    assert '"no_provider_call": True' in source


def test_order_strategies_use_same_five_candidates_in_distinct_orders() -> None:
    candidates = [
        _candidate(1, "Technische Informationsbibliothek (TIB)", parentheses=True),
        _candidate(2, "HDI"),
        _candidate(3, "Sopra Steria"),
        _candidate(4, "1&1"),
        _candidate(5, "adesso"),
    ]

    strategies = build_order_strategies(candidates)
    orders = [tuple(item["aliases"]) for item in strategies]

    assert 3 <= len(strategies) <= 5
    assert len(orders) == len(set(orders))
    assert all(
        set(order) == {item["filter_alias"] for item in candidates}
        for order in orders
    )


def test_zero_and_nonzero_orders_are_transport_failure_not_policy() -> None:
    results = [
        {
            "strategy_name": "dominance_order",
            "outcome": "filter_effective_no_refill",
            "parsed_card_count": 0,
            "filter_aliases": ["TIB", "HDI", "Sopra", "1&1", "adesso"],
        },
        {
            "strategy_name": "reverse_dominance",
            "outcome": "filter_effective_full_refill",
            "parsed_card_count": 25,
            "filter_aliases": ["adesso", "1&1", "Sopra", "HDI", "TIB"],
        },
    ]

    diagnosis = diagnose_order_results(results)

    assert diagnosis["primary_diagnosis"] == "same_filter_set_not_permutation_invariant"
    assert diagnosis["recommended_strategy"] is None
    assert diagnosis["recommended_alias_order"] == []
    assert diagnosis["production_order_policy_allowed"] is False


def test_all_usable_orders_still_do_not_authorize_transport_or_order_policy() -> None:
    results = [
        {
            "strategy_name": "dominance_order",
            "outcome": "filter_effective_full_refill",
            "parsed_card_count": 25,
            "filter_aliases": ["A", "B", "C", "D", "E"],
        },
        {
            "strategy_name": "reverse_dominance",
            "outcome": "filter_effective_full_refill",
            "parsed_card_count": 25,
            "filter_aliases": ["E", "D", "C", "B", "A"],
        },
    ]

    diagnosis = diagnose_order_results(results)

    assert diagnosis["primary_diagnosis"] == "orders_usable_but_transport_semantics_unvalidated"
    assert diagnosis["recommended_strategy"] is None
    assert diagnosis["production_order_policy_allowed"] is False


def test_indeterminate_response_blocks_conclusion() -> None:
    results = [
        {
            "strategy_name": "dominance_order",
            "outcome": "indeterminate_page_type",
            "parsed_card_count": 0,
            "filter_aliases": ["A", "B", "C", "D", "E"],
        }
    ]

    diagnosis = diagnose_order_results(results)

    assert diagnosis["primary_diagnosis"] == "five_filter_order_test_indeterminate"
    assert diagnosis["production_order_policy_allowed"] is False
