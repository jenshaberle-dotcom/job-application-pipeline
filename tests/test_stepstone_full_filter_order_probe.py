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


def test_runner_is_bounded_and_read_only() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "DEFAULT_MAX_REQUESTS = 8" in source
    assert "DEFAULT_COMPANY_COUNT = 5" in source
    assert '"page_one_only": True' in source
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
    assert all(set(order) == {item["filter_alias"] for item in candidates} for order in orders)
    assert orders[0][0] == "Technische Informationsbibliothek (TIB)"
    assert any(order[-1] == "Technische Informationsbibliothek (TIB)" for order in orders)


def test_diagnosis_supports_five_filters_when_one_order_fully_refills() -> None:
    results = [
        {
            "strategy_name": "dominance_order",
            "outcome": "filter_effective_no_refill",
            "filter_aliases": ["TIB", "HDI", "Sopra", "1&1", "adesso"],
        },
        {
            "strategy_name": "syntax_risk_ascending",
            "outcome": "filter_effective_full_refill",
            "filter_aliases": ["HDI", "adesso", "Sopra", "1&1", "TIB"],
        },
    ]

    diagnosis = diagnose_order_results(results)

    assert (
        diagnosis["primary_diagnosis"]
        == "five_filter_cardinality_supported_with_order_policy"
    )
    assert diagnosis["recommended_strategy"] == "syntax_risk_ascending"
    assert diagnosis["full_refill_strategy_count"] == 1


def test_diagnosis_reports_partial_five_filter_support() -> None:
    results = [
        {
            "strategy_name": "reverse_dominance",
            "outcome": "filter_effective_partial_refill",
            "filter_aliases": ["adesso", "1&1", "Sopra", "HDI", "TIB"],
        }
    ]

    diagnosis = diagnose_order_results(results)

    assert (
        diagnosis["primary_diagnosis"]
        == "five_filter_cardinality_supported_with_partial_refill"
    )
    assert diagnosis["recommended_strategy"] == "reverse_dominance"


def test_diagnosis_keeps_indeterminate_pages_separate() -> None:
    results = [
        {
            "strategy_name": "dominance_order",
            "outcome": "indeterminate_page_type",
            "filter_aliases": ["A", "B", "C", "D", "E"],
        }
    ]

    diagnosis = diagnose_order_results(results)

    assert diagnosis["primary_diagnosis"] == "five_filter_order_test_indeterminate"
    assert diagnosis["recommended_strategy"] is None


def test_diagnosis_does_not_claim_five_filter_support_without_working_order() -> None:
    results = [
        {
            "strategy_name": "dominance_order",
            "outcome": "filter_effective_no_refill",
            "filter_aliases": ["A", "B", "C", "D", "E"],
        },
        {
            "strategy_name": "reverse_dominance",
            "outcome": "filter_effective_no_refill",
            "filter_aliases": ["E", "D", "C", "B", "A"],
        },
    ]

    diagnosis = diagnose_order_results(results)

    assert (
        diagnosis["primary_diagnosis"]
        == "five_filter_cardinality_or_higher_order_interaction_not_resolved"
    )
    assert diagnosis["recommended_strategy"] is None
