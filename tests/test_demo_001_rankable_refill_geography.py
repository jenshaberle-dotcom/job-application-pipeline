from __future__ import annotations

from scripts.run_demo_001_rankable_refill_apply import _selected_candidates
from src.job_lifecycle_health import OUTCOME_SEEN_ACTIVE


def _candidate(*, silver_job_id: int, geography_eligible: bool) -> dict[str, object]:
    return {
        "silver_job_id": silver_job_id,
        "live_outcome": OUTCOME_SEEN_ACTIVE,
        "role_relevant": True,
        "geography_eligible": geography_eligible,
        "candidate_fact_matches": [
            {
                "fact_key": "training.data-engineering.python-sql",
                "matched_capability_tags": ["sql"],
            }
        ],
    }


def test_refill_selection_excludes_explicit_outside_germany_candidate() -> None:
    rows = [
        _candidate(silver_job_id=654, geography_eligible=False),
        _candidate(silver_job_id=646, geography_eligible=True),
    ]

    selected = _selected_candidates(rows, candidate_cap=10)

    assert [row["silver_job_id"] for row in selected] == [646]


def test_refill_scout_persists_geography_gate_and_source_fields() -> None:
    source = open(
        "scripts/run_demo_001_rankable_refill_scout.py",
        encoding="utf-8",
    ).read()

    assert "readiness.city" in source
    assert "readiness.country" in source
    assert "readiness.work_model" in source
    assert "readiness.commute_minutes" in source
    assert '"geography_eligible": geography.eligible_for_bounded_pool' in source
    assert 'and row["geography_eligible"]' in source
    assert '"explicit_outside_germany_excluded": True' in source
