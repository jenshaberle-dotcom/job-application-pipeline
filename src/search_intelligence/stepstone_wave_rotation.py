"""Persistent rotation helpers for the bounded StepStone company-discovery waves."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class WaveTransition:
    current_index: int
    next_index: int
    action: str
    reason: str


def resolve_wave_index(*, persisted_index: int, override_index: int | None) -> int:
    """Use an explicit diagnostic override or the non-negative persisted index."""
    if override_index is not None:
        if override_index < 0:
            raise ValueError("override exclusion wave index must be non-negative")
        return override_index
    if persisted_index < 0:
        raise ValueError("persisted exclusion wave index must be non-negative")
    return persisted_index


def next_wave_transition(
    *,
    current_index: int,
    action: str,
    boundary: Mapping[str, object],
) -> WaveTransition:
    """Advance through the logical cooldown pool without duplicate baselines.

    A successful bounded NOT request advances to the next request window while
    more companies remain. The end of the pool, an explicitly empty later wave,
    or a baseline-only result resets the next cycle to wave zero.
    """
    if current_index < 0:
        raise ValueError("current exclusion wave index must be non-negative")

    pool_size = int(boundary.get("cooldown_pool_size", 0) or 0)
    wave_end = int(boundary.get("wave_end_index", 0) or 0)
    selected_size = int(boundary.get("selected_wave_size", 0) or 0)

    if action == "run_fetch_time_company_not_probe" and selected_size > 0:
        if wave_end < pool_size:
            return WaveTransition(
                current_index=current_index,
                next_index=current_index + 1,
                action=action,
                reason="More companies remain in the logical cooldown pool; advance to the next bounded request wave.",
            )
        return WaveTransition(
            current_index=current_index,
            next_index=0,
            action=action,
            reason="The current request reached the end of the logical cooldown pool; restart at wave zero on the next due cycle.",
        )

    if action == "skip_empty_exclusion_wave":
        return WaveTransition(
            current_index=current_index,
            next_index=0,
            action=action,
            reason="The selected wave is empty; reset instead of performing a duplicate baseline request.",
        )

    return WaveTransition(
        current_index=current_index,
        next_index=0,
        action=action,
        reason="Baseline or unsupported-term cycle keeps the next exclusion wave at zero.",
    )
