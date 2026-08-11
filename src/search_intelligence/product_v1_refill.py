from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar


TRow = TypeVar("TRow")
TResult = TypeVar("TResult")


def _is_current_confirmed(result: object) -> bool:
    if not isinstance(result, dict):
        return False
    exact = result.get("exact_vacancy")
    return bool(
        isinstance(exact, dict)
        and exact.get("status") == "current_vacancy_confirmed"
    )


def run_bounded_refill(
    rows: Sequence[TRow],
    *,
    inspect: Callable[[TRow], TResult],
    target_current_vacancies: int,
    max_network_contenders: int,
) -> tuple[list[TResult], dict[str, object]]:
    """Inspect a bounded contender pool until current-vacancy target or exhaustion.

    This helper controls only inspection order and stopping. It does not decide
    vacancy identity, activity, hard filters, assessment, ranking, or mutation.
    """

    if target_current_vacancies <= 0:
        raise ValueError("target_current_vacancies must be positive")
    if max_network_contenders <= 0:
        raise ValueError("max_network_contenders must be positive")
    if target_current_vacancies > max_network_contenders:
        raise ValueError(
            "target_current_vacancies must be <= max_network_contenders"
        )

    bounded_rows = list(rows[:max_network_contenders])
    results: list[TResult] = []
    current_confirmed = 0

    for row in bounded_rows:
        result = inspect(row)
        results.append(result)
        if _is_current_confirmed(result):
            current_confirmed += 1
            if current_confirmed >= target_current_vacancies:
                break

    inspected = len(results)
    remaining = len(bounded_rows) - inspected
    if current_confirmed >= target_current_vacancies:
        stop_reason = "target_current_vacancies_reached"
    else:
        stop_reason = "bounded_pool_exhausted"

    return results, {
        "strategy": "lazy_until_current_target_or_pool_exhausted",
        "target_current_vacancies": target_current_vacancies,
        "max_network_contenders": max_network_contenders,
        "network_contenders_available": len(bounded_rows),
        "network_contenders_inspected": inspected,
        "current_vacancies_confirmed": current_confirmed,
        "remaining_uninspected": remaining,
        "stop_reason": stop_reason,
    }
