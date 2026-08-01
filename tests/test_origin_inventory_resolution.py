from __future__ import annotations

from datetime import date
import json
import sys

import pytest

from scripts.run_origin_inventory_resolution import main as run_resolution
from src.search_intelligence.origin_inventory_resolution import (
    ORIGIN_INVENTORY_RESOLUTION_BOUNDARY,
    ExternalJobSignal,
    OriginCandidateInventory,
    build_source_families,
    plan_reobservation,
    resolve_origin_inventory,
)

AS_OF = date(2026, 8, 1)


def candidate(
    candidate_id: str,
    *,
    role: str = "official_company",
    source_url: str | None = None,
    final_url: str | None = None,
    ats_tenant: str | None = None,
    employer_scope: str | None = "example",
    relevant_jobs: tuple[str, ...] = (),
    observed_job_count: int | None = None,
) -> OriginCandidateInventory:
    observed = len(relevant_jobs) if observed_job_count is None else observed_job_count
    return OriginCandidateInventory(
        candidate_id=candidate_id,
        source_url=source_url or f"https://example.test/{candidate_id.lower()}",
        source_role=role,
        final_url=final_url,
        ats_tenant=ats_tenant,
        employer_scope=employer_scope,
        observed_job_count=observed,
        relevant_job_count=len(relevant_jobs),
        relevant_job_keys=relevant_jobs,
    )


def signal(
    live: bool | None,
    *,
    confidence: float = 0.9,
    observations: int = 1,
    misses: int = 0,
) -> ExternalJobSignal:
    return ExternalJobSignal(
        currently_live=live,
        confidence=confidence,
        observation_count=observations,
        origin_miss_count=misses,
    )


def resolve(
    candidates: tuple[OriginCandidateInventory, ...],
    *,
    external_signal: ExternalJobSignal | None = None,
    failed_attempt: int = 0,
    event: bool = False,
):
    return resolve_origin_inventory(
        company_key="example",
        company_name="Example SE",
        candidates=candidates,
        external_job_signal=external_signal or signal(True),
        as_of=AS_OF,
        failed_reobservation_attempt=failed_attempt,
        new_external_job_event=event,
    )


def test_single_origin_with_relevant_jobs_is_confirmed() -> None:
    result = resolve((candidate("C1", relevant_jobs=("J1",)),))

    assert result.status == "confirmed_origin"
    assert result.selected_candidate_ids == ("C1",)
    assert result.reobservation.mode == "not_required"


def test_equivalent_job_bearing_urls_become_one_source_family() -> None:
    result = resolve(
        (
            candidate(
                "C1",
                role="official_company",
                ats_tenant="tenant-a",
                relevant_jobs=("J1", "J2"),
            ),
            candidate(
                "C2",
                role="official_ats",
                ats_tenant="tenant-a",
                relevant_jobs=("J1", "J2"),
            ),
        )
    )

    assert result.status == "equivalent_source_family"
    assert len(result.source_families) == 1
    assert result.source_families[0].candidate_ids == ("C1", "C2")
    assert result.source_families[0].canonical_candidate_id == "C1"
    assert "same_ats_tenant" in result.source_families[0].equivalence_reasons


def test_distinct_job_bearing_origins_remain_multi_origin_coverage() -> None:
    result = resolve(
        (
            candidate("C1", ats_tenant="tenant-a", relevant_jobs=("J1",)),
            candidate("C2", ats_tenant="tenant-b", relevant_jobs=("J2",)),
        )
    )

    assert result.status == "multi_origin_coverage"
    assert result.selected_candidate_ids == ("C1", "C2")
    assert len(result.selected_source_family_ids) == 2


def test_empty_equivalent_urls_are_grouped_but_remain_dormant() -> None:
    result = resolve(
        (
            candidate("C1", ats_tenant="tenant-a"),
            candidate("C2", role="official_ats", ats_tenant="tenant-a"),
        ),
        external_signal=signal(False),
    )

    assert result.status == "dormant_origin_candidate"
    assert len(result.source_families) == 1
    assert result.selected_candidate_ids == ()
    assert result.reobservation.mode == "scheduled"
    assert result.reobservation.next_observation_on == date(2026, 8, 2)


@pytest.mark.parametrize(
    ("attempt", "expected_date", "expected_mode"),
    [
        (0, date(2026, 8, 2), "scheduled"),
        (1, date(2026, 8, 4), "scheduled"),
        (2, date(2026, 8, 8), "scheduled"),
        (3, date(2026, 8, 15), "scheduled"),
        (4, date(2026, 8, 31), "scheduled"),
        (5, None, "event_only"),
        (8, None, "event_only"),
    ],
)
def test_reobservation_schedule_is_degressive(
    attempt: int,
    expected_date: date | None,
    expected_mode: str,
) -> None:
    plan = plan_reobservation(as_of=AS_OF, failed_attempt=attempt)

    assert plan.mode == expected_mode
    assert plan.next_observation_on == expected_date


def test_new_external_finding_reactivates_immediately() -> None:
    result = resolve(
        (candidate("C1"),),
        external_signal=signal(True),
        failed_attempt=8,
        event=True,
    )

    assert result.status == "official_origin_unproven"
    assert result.reobservation.mode == "immediate_event"
    assert result.reobservation.next_observation_on == AS_OF
    assert result.reobservation.next_attempt == 0


def test_third_party_jobs_create_reversible_hypothesis_not_origin() -> None:
    result = resolve(
        (
            candidate("C1", role="official_company"),
            candidate("C2", role="third_party", relevant_jobs=("J1",)),
        ),
        external_signal=signal(True, observations=2, misses=2),
    )

    assert result.status == "third_party_discovery_only"
    assert result.selected_candidate_ids == ()
    assert result.discovery_candidate_ids == ("C2",)
    assert result.hypothesis == "employer_may_publish_through_third_party_only"
    assert result.hypothesis_level == "probable"


def test_live_external_job_without_origin_inventory_is_unproven() -> None:
    result = resolve(
        (candidate("C1"), candidate("C2", role="official_ats")),
        external_signal=signal(True, confidence=0.82, misses=1),
    )

    assert result.status == "official_origin_unproven"
    assert result.hypothesis == "official_origin_not_observed_for_current_live_job"
    assert result.hypothesis_level == "possible"


def test_low_confidence_external_signal_does_not_create_hypothesis() -> None:
    result = resolve(
        (candidate("C1"),),
        external_signal=signal(True, confidence=0.5),
    )

    assert result.status == "insufficient_evidence"
    assert result.hypothesis is None


def test_same_tenant_different_employer_scopes_do_not_collapse() -> None:
    families = build_source_families(
        (
            candidate(
                "C1",
                ats_tenant="tenant-a",
                employer_scope="parent-company",
                relevant_jobs=("J1",),
            ),
            candidate(
                "C2",
                ats_tenant="tenant-a",
                employer_scope="subsidiary",
                relevant_jobs=("J2",),
            ),
        )
    )

    assert len(families) == 2


def test_boundary_prohibits_baitjob_assertion_and_mutation() -> None:
    assert ORIGIN_INVENTORY_RESOLUTION_BOUNDARY["no_baitjob_assertion"] is True
    assert ORIGIN_INVENTORY_RESOLUTION_BOUNDARY["no_database_write"] is True
    assert ORIGIN_INVENTORY_RESOLUTION_BOUNDARY["no_source_activation"] is True


def test_json_runner_writes_review_only_resolution(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(
        json.dumps(
            {
                "company_key": "example",
                "company_name": "Example SE",
                "as_of": "2026-08-01",
                "external_job_signal": {
                    "currently_live": True,
                    "confidence": 0.9,
                    "observation_count": 1,
                    "origin_miss_count": 0,
                },
                "candidates": [
                    {
                        "candidate_id": "C1",
                        "source_url": "https://example.test/jobs",
                        "source_role": "official_company",
                        "observed_job_count": 1,
                        "relevant_job_count": 1,
                        "relevant_job_keys": ["J1"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_origin_inventory_resolution",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    assert run_resolution() == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["status"] == "confirmed_origin"
    assert output["boundary"]["review_output_only_not_pipeline_input"] is True
