"""Deterministic reconciliation plan for search-term execution state.

Configuration authority lives in active ``search_terms``.  The cycle-state table is
execution state only: retained terms keep their cadence/history, missing active
terms are added, and rows for terms no longer active are removed from the exact
source/profile scope.

This module is pure and owns no database, network, provider, connector, product,
ranking, application, or scheduler authority.
"""
from __future__ import annotations

from dataclasses import dataclass


def normalize_search_term(value: str) -> str:
    """Return the comparison key used for configuration/state reconciliation."""
    return " ".join(value.split()).casefold()


@dataclass(frozen=True)
class CycleStateReconcilePlan:
    active_terms: tuple[str, ...]
    current_terms: tuple[str, ...]
    retained_terms: tuple[str, ...]
    added_terms: tuple[str, ...]
    removed_terms: tuple[str, ...]
    canonicalized_terms: tuple[tuple[str, str], ...]

    @property
    def changed(self) -> bool:
        return bool(self.added_terms or self.removed_terms or self.canonicalized_terms)


def _canonical_map(terms: list[str] | tuple[str, ...], *, label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_term in terms:
        term = " ".join(str(raw_term).split())
        if not term:
            raise ValueError(f"{label} contains an empty search term")
        key = normalize_search_term(term)
        previous = result.get(key)
        if previous is not None and previous != term:
            raise ValueError(
                f"{label} contains duplicate normalized term {key!r}: "
                f"{previous!r} vs {term!r}"
            )
        result[key] = term
    return result


def plan_cycle_state_reconcile(
    *,
    active_terms: list[str] | tuple[str, ...],
    current_terms: list[str] | tuple[str, ...],
) -> CycleStateReconcilePlan:
    """Plan exact reconciliation without mutating state.

    The active configuration must be non-empty. Duplicate normalized current rows
    fail closed because silently choosing which row's cadence/history survives
    would destroy execution history.
    """
    active = _canonical_map(active_terms, label="active_terms")
    if not active:
        raise ValueError("active_terms must not be empty")
    current = _canonical_map(current_terms, label="current_terms")

    active_keys = set(active)
    current_keys = set(current)

    retained = tuple(active[key] for key in sorted(active_keys & current_keys))
    added = tuple(active[key] for key in sorted(active_keys - current_keys))
    removed = tuple(current[key] for key in sorted(current_keys - active_keys))
    canonicalized = tuple(
        (current[key], active[key])
        for key in sorted(active_keys & current_keys)
        if current[key] != active[key]
    )

    return CycleStateReconcilePlan(
        active_terms=tuple(active[key] for key in sorted(active)),
        current_terms=tuple(current[key] for key in sorted(current)),
        retained_terms=retained,
        added_terms=added,
        removed_terms=removed,
        canonicalized_terms=canonicalized,
    )
