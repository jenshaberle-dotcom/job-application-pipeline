from src.search_intelligence.stepstone_wave_rotation import (
    next_wave_transition,
    resolve_wave_index,
)


def test_persisted_wave_is_used_without_diagnostic_override() -> None:
    assert resolve_wave_index(persisted_index=3, override_index=None) == 3
    assert resolve_wave_index(persisted_index=3, override_index=1) == 1


def test_wave_advances_while_logical_pool_has_more_companies() -> None:
    transition = next_wave_transition(
        current_index=0,
        action="run_fetch_time_company_not_probe",
        boundary={
            "cooldown_pool_size": 14,
            "selected_wave_size": 6,
            "wave_end_index": 6,
        },
    )

    assert transition.next_index == 1
    assert "advance" in transition.reason


def test_wave_resets_after_end_of_pool() -> None:
    transition = next_wave_transition(
        current_index=2,
        action="run_fetch_time_company_not_probe",
        boundary={
            "cooldown_pool_size": 14,
            "selected_wave_size": 2,
            "wave_end_index": 14,
        },
    )

    assert transition.next_index == 0


def test_empty_later_wave_resets_without_duplicate_baseline() -> None:
    transition = next_wave_transition(
        current_index=4,
        action="skip_empty_exclusion_wave",
        boundary={
            "cooldown_pool_size": 6,
            "selected_wave_size": 0,
            "wave_end_index": 6,
        },
    )

    assert transition.next_index == 0
    assert "duplicate baseline" in transition.reason
