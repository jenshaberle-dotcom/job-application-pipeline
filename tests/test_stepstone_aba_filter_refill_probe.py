from pathlib import Path

from scripts.run_stepstone_aba_filter_refill_probe import (
    classify_page,
    compare_probe,
    select_exclusion_company,
)


RUNNER = Path("scripts/run_stepstone_aba_filter_refill_probe.py")


def _card(job_id: str, company: str, company_key: str) -> dict[str, object]:
    return {
        "job_key": f"stepstone:{job_id}",
        "company": company,
        "company_key": company_key,
    }


def _page(
    cards: list[dict[str, object]],
    *,
    page_type: str = "result_page_with_cards",
) -> dict[str, object]:
    return {
        "cards": cards,
        "parsed_card_count": len(cards),
        "page_type": page_type,
    }


def test_probe_is_exactly_three_page_one_requests_and_read_only() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert '"request_count": 3' in source
    assert "PAGE_CARD_LIMIT = 25" in source
    assert "A0: baseline query" in source
    assert "B:  the same query excluding exactly one" in source
    assert "A1: baseline query repeated" in source
    assert '"no_database_write": True' in source
    assert '"no_pagination": True' in source
    assert '"no_detail_pages": True' in source
    assert '"no_candidate_creation": True' in source
    assert '"no_provider_call": True' in source


def test_selects_strongest_company_from_current_a0_only() -> None:
    cards = [
        _card("1", "TIB", "tib"),
        _card("2", "TIB", "tib"),
        _card("3", "TIB", "tib"),
        _card("4", "HDI", "hdi"),
        _card("5", "HDI", "hdi"),
        _card("6", "Other", "other"),
    ]

    selected = select_exclusion_company(
        cards=cards,
        explicit_company=None,
    )

    assert selected["company_key"] == "tib"
    assert selected["card_count"] == 3
    assert selected["selection_mode"] == "strongest_a0_company"
    assert selected["dominant_threshold_met"] is True


def test_explicit_company_must_exist_in_current_a0() -> None:
    cards = [_card("1", "TIB", "tib")]

    try:
        select_exclusion_company(
            cards=cards,
            explicit_company="HDI",
        )
    except RuntimeError as exc:
        assert "not present in A0" in str(exc)
    else:
        raise AssertionError("Expected explicit non-A0 company to be rejected")


def test_classifies_cards_zero_results_and_parser_mismatch() -> None:
    assert (
        classify_page(raw_html="<html></html>", parsed_card_count=2)
        == "result_page_with_cards"
    )
    assert (
        classify_page(
            raw_html="<html>Keine Jobs gefunden</html>",
            parsed_card_count=0,
        )
        == "explicit_zero_results"
    )
    assert (
        classify_page(
            raw_html=(
                '<article data-testid="job-item" id="changed-format">'
                "broken parser fixture</article>"
            ),
            parsed_card_count=0,
        )
        == "parser_mismatch"
    )


def test_aba_confirms_filter_and_full_refill() -> None:
    a0 = _page(
        [
            _card("1", "TIB", "tib"),
            _card("2", "TIB", "tib"),
            _card("3", "HDI", "hdi"),
        ]
        + [_card(str(i), f"Company {i}", f"company_{i}") for i in range(4, 26)]
    )
    b = _page(
        [_card("3", "HDI", "hdi")]
        + [_card(str(i), f"Company {i}", f"company_{i}") for i in range(4, 26)]
        + [
            _card("26", "New A", "new_a"),
            _card("27", "New B", "new_b"),
        ]
    )
    a1 = _page(a0["cards"])
    excluded = {
        "company_key": "tib",
        "company_name": "TIB",
        "card_count": 2,
    }

    verdict = compare_probe(a0=a0, b=b, a1=a1, excluded=excluded)

    assert verdict["filter_answer"] == "yes_confirmed_by_a0_b_a1"
    assert verdict["refill_answer"] == "yes_full_page_refill"
    assert verdict["excluded_company_leakage_count"] == 0
    assert verdict["new_job_count_b_vs_a0"] == 2
    assert verdict["new_company_count_b_vs_a0"] == 2


def test_aba_reports_filter_failure_when_company_leaks() -> None:
    a0 = _page([_card("1", "TIB", "tib")])
    b = _page([_card("1", "TIB", "tib")])
    a1 = _page([_card("1", "TIB", "tib")])
    excluded = {
        "company_key": "tib",
        "company_name": "TIB",
        "card_count": 1,
    }

    verdict = compare_probe(a0=a0, b=b, a1=a1, excluded=excluded)

    assert verdict["filter_answer"] == "no_excluded_company_leaked"
    assert verdict["excluded_company_leakage_count"] == 1


def test_zero_result_page_is_no_refill_but_filter_can_be_confirmed() -> None:
    a0 = _page([_card("1", "TIB", "tib")])
    b = _page([], page_type="explicit_zero_results")
    a1 = _page([_card("1", "TIB", "tib")])
    excluded = {
        "company_key": "tib",
        "company_name": "TIB",
        "card_count": 1,
    }

    verdict = compare_probe(a0=a0, b=b, a1=a1, excluded=excluded)

    assert verdict["filter_answer"] == "yes_confirmed_by_a0_b_a1"
    assert verdict["refill_answer"] == "no_refill_observed"


def test_unknown_b_page_keeps_both_answers_indeterminate() -> None:
    a0 = _page([_card("1", "TIB", "tib")])
    b = _page([], page_type="challenge_or_block_page")
    a1 = _page([_card("1", "TIB", "tib")])
    excluded = {
        "company_key": "tib",
        "company_name": "TIB",
        "card_count": 1,
    }

    verdict = compare_probe(a0=a0, b=b, a1=a1, excluded=excluded)

    assert verdict["filter_answer"] == "indeterminate_page_type"
    assert verdict["refill_answer"] == "indeterminate_page_type"
