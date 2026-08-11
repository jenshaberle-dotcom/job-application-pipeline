from __future__ import annotations

import pytest

from src.search_intelligence.product_v1_refill import run_bounded_refill


def result(status: str) -> dict[str, object]:
    return {"exact_vacancy": {"status": status}}


def test_refill_continues_past_first_five_until_current_target_reached() -> None:
    rows = list(range(20))
    current_at = {5, 7, 9, 11, 13}

    results, evidence = run_bounded_refill(
        rows,
        inspect=lambda row: result(
            "current_vacancy_confirmed"
            if row in current_at
            else "exact_vacancy_not_found"
        ),
        target_current_vacancies=5,
        max_network_contenders=20,
    )

    assert len(results) == 14
    assert evidence == {
        "strategy": "lazy_until_current_target_or_pool_exhausted",
        "target_current_vacancies": 5,
        "max_network_contenders": 20,
        "network_contenders_available": 20,
        "network_contenders_inspected": 14,
        "current_vacancies_confirmed": 5,
        "remaining_uninspected": 6,
        "stop_reason": "target_current_vacancies_reached",
    }


def test_refill_exhausts_bounded_pool_without_forcing_five_results() -> None:
    rows = list(range(25))

    results, evidence = run_bounded_refill(
        rows,
        inspect=lambda row: result(
            "current_vacancy_confirmed"
            if row in {4, 19}
            else "exact_vacancy_not_found"
        ),
        target_current_vacancies=5,
        max_network_contenders=25,
    )

    assert len(results) == 25
    assert evidence["current_vacancies_confirmed"] == 2
    assert evidence["remaining_uninspected"] == 0
    assert evidence["stop_reason"] == "bounded_pool_exhausted"


def test_refill_never_inspects_beyond_hard_network_envelope() -> None:
    rows = list(range(40))
    inspected: list[int] = []

    _, evidence = run_bounded_refill(
        rows,
        inspect=lambda row: (
            inspected.append(row) or result("exact_vacancy_not_found")
        ),
        target_current_vacancies=5,
        max_network_contenders=25,
    )

    assert inspected == list(range(25))
    assert evidence["network_contenders_available"] == 25
    assert evidence["network_contenders_inspected"] == 25


def test_refill_uses_downstream_current_confirmation_only() -> None:
    rows = [1, 2, 3]
    statuses = {
        1: "inactive_vacancy_confirmed",
        2: "exact_vacancy_current_state_unverifiable",
        3: "current_vacancy_confirmed",
    }

    results, evidence = run_bounded_refill(
        rows,
        inspect=lambda row: result(statuses[row]),
        target_current_vacancies=1,
        max_network_contenders=3,
    )

    assert len(results) == 3
    assert evidence["current_vacancies_confirmed"] == 1
    assert evidence["stop_reason"] == "target_current_vacancies_reached"


@pytest.mark.parametrize(
    ("target", "maximum"),
    [(0, 25), (5, 0), (6, 5)],
)
def test_refill_invalid_bounds_fail_closed(target: int, maximum: int) -> None:
    with pytest.raises(ValueError):
        run_bounded_refill(
            [],
            inspect=lambda row: row,
            target_current_vacancies=target,
            max_network_contenders=maximum,
        )
