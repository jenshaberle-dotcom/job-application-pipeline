from pathlib import Path

from scripts.run_stepstone_filter_matrix_probe import (
    diagnose_matrix,
    first_cumulative_break,
    select_current_a0_candidates,
)


RUNNER = Path("scripts/run_stepstone_filter_matrix_probe.py")


def _card(company: str, company_key: str) -> dict[str, object]:
    return {
        "company": company,
        "company_key": company_key,
        "job_key": f"job:{company_key}",
    }


def _result(
    aliases: list[str],
    *,
    outcome: str = "filter_effective_full_refill",
    count: int | None = None,
) -> dict[str, object]:
    return {
        "outcome": outcome,
        "filter_count": count if count is not None else len(aliases),
        "filter_aliases": aliases,
        "parsed_card_count": 25,
    }


def test_runner_is_bounded_and_read_only() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "DEFAULT_MAX_COMPANIES = 5" in source
    assert "DEFAULT_MAX_REQUESTS = 16" in source
    assert '"page_one_only": True' in source
    assert '"no_pagination": True' in source
    assert '"no_detail_pages": True' in source
    assert '"no_database_write": True' in source
    assert '"no_candidate_creation": True' in source
    assert '"no_provider_call": True' in source
    assert "individual outcomes:" in source
    assert "cumulative outcomes:" in source
    assert "leave_one_out" in source


def test_selects_candidates_only_from_current_a0_distribution() -> None:
    cards = [
        _card("TIB", "tib"),
        _card("TIB", "tib"),
        _card("TIB", "tib"),
        _card("Ratiodata", "ratiodata"),
        _card("Ratiodata", "ratiodata"),
        _card("HDI", "hdi"),
    ]

    candidates = select_current_a0_candidates(cards, max_companies=3)

    assert [item["company_key"] for item in candidates] == [
        "tib",
        "ratiodata",
        "hdi",
    ]
    assert [item["card_count"] for item in candidates] == [3, 2, 1]
    assert [item["rank"] for item in candidates] == [1, 2, 3]
    assert all(item["filter_alias"] for item in candidates)


def test_first_cumulative_break_returns_first_nonproductive_result() -> None:
    cumulative = [
        _result(["A"], count=1),
        _result(["A", "B"], count=2),
        _result(
            ["A", "B", "C"],
            outcome="filter_effective_no_refill",
            count=3,
        ),
        _result(
            ["A", "B", "C", "D"],
            outcome="filter_effective_no_refill",
            count=4,
        ),
    ]

    broken = first_cumulative_break(cumulative)

    assert broken is cumulative[2]
    assert broken["filter_count"] == 3


def test_diagnoses_individual_filter_term_failure_before_cardinality() -> None:
    individual = [
        _result(["TIB"]),
        _result(["Problem Term"], outcome="filter_effective_no_refill"),
    ]
    cumulative = [
        _result(["TIB"], count=1),
        _result(
            ["TIB", "Problem Term"],
            outcome="filter_effective_no_refill",
            count=2,
        ),
    ]

    diagnosis = diagnose_matrix(
        individual=individual,
        cumulative=cumulative,
        reverse=None,
        leave_one_out=[],
    )

    assert diagnosis["primary_diagnosis"] == "individual_filter_term_failure"
    assert diagnosis["failed_individual_aliases"] == ["Problem Term"]


def test_diagnoses_order_sensitivity_for_same_filter_set() -> None:
    individual = [_result([name]) for name in ["A", "B", "C"]]
    cumulative = [
        _result(["A"], count=1),
        _result(["A", "B"], count=2),
        _result(
            ["A", "B", "C"],
            outcome="filter_effective_no_refill",
            count=3,
        ),
    ]
    reverse = _result(["C", "B", "A"], count=3)

    diagnosis = diagnose_matrix(
        individual=individual,
        cumulative=cumulative,
        reverse=reverse,
        leave_one_out=[],
    )

    assert diagnosis["primary_diagnosis"] == "filter_order_sensitive"


def test_diagnoses_cardinality_when_every_single_omission_recovers() -> None:
    individual = [_result([name]) for name in ["A", "B", "C"]]
    cumulative = [
        _result(["A"], count=1),
        _result(["A", "B"], count=2),
        _result(
            ["A", "B", "C"],
            outcome="filter_effective_no_refill",
            count=3,
        ),
    ]
    reverse = _result(
        ["C", "B", "A"],
        outcome="filter_effective_no_refill",
        count=3,
    )
    leave_one_out = [
        {
            **_result(["A", "B"], count=2),
            "omitted_company": {"filter_alias": "C"},
        },
        {
            **_result(["A", "C"], count=2),
            "omitted_company": {"filter_alias": "B"},
        },
        {
            **_result(["B", "C"], count=2),
            "omitted_company": {"filter_alias": "A"},
        },
    ]

    diagnosis = diagnose_matrix(
        individual=individual,
        cumulative=cumulative,
        reverse=reverse,
        leave_one_out=leave_one_out,
    )

    assert (
        diagnosis["primary_diagnosis"]
        == "cardinality_or_total_query_complexity_boundary"
    )
    assert set(diagnosis["successful_omission_aliases"]) == {"A", "B", "C"}


def test_diagnoses_specific_interaction_when_only_one_omission_recovers() -> None:
    individual = [_result([name]) for name in ["A", "B", "C"]]
    cumulative = [
        _result(["A"], count=1),
        _result(["A", "B"], count=2),
        _result(
            ["A", "B", "C"],
            outcome="filter_effective_no_refill",
            count=3,
        ),
    ]
    reverse = _result(
        ["C", "B", "A"],
        outcome="filter_effective_no_refill",
        count=3,
    )
    leave_one_out = [
        {
            **_result(["A", "B"], count=2),
            "omitted_company": {"filter_alias": "C"},
        },
        {
            **_result(
                ["A", "C"],
                outcome="filter_effective_no_refill",
                count=2,
            ),
            "omitted_company": {"filter_alias": "B"},
        },
        {
            **_result(
                ["B", "C"],
                outcome="filter_effective_no_refill",
                count=2,
            ),
            "omitted_company": {"filter_alias": "A"},
        },
    ]

    diagnosis = diagnose_matrix(
        individual=individual,
        cumulative=cumulative,
        reverse=reverse,
        leave_one_out=leave_one_out,
    )

    assert diagnosis["primary_diagnosis"] == "specific_filter_interaction"
    assert diagnosis["successful_omission_aliases"] == ["C"]
