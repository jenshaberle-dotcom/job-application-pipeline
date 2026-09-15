from __future__ import annotations

from pathlib import Path


MIGRATION = Path("db/migrations/111_bridge_silver_requirement_evidence_into_hard_filter.sql")


def test_f4b_bridge_uses_silver_sidecar_as_primary_job_requirement_authority() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "LEFT JOIN silver_job_requirement_evidence sidecar" in source
    assert "sidecar.evidence_payload #>> '{fields,employment_type,status}' = 'observed_bounded_text'" in source
    assert "sidecar.evidence_payload #>> '{fields,required_languages,status}' = 'observed_bounded_text'" in source
    assert "sidecar.evidence_payload #>> '{fields,weekly_hours,status}' = 'observed_bounded_text'" in source
    assert "sidecar.evidence_payload #>> '{fields,requirements_seniority,status}' = 'observed_bounded_text'" in source
    assert "sidecar.silver_job_id IS NULL THEN a.employment_evidence_status = 'observed'" in source
    assert "sidecar.silver_job_id IS NULL THEN a.language_evidence_status = 'observed'" in source
    assert "sidecar.silver_job_id IS NULL THEN a.weekly_hours_evidence_status = 'observed'" in source
    assert "sidecar.silver_job_id IS NULL THEN a.seniority_evidence_status = 'observed'" in source


def test_f4b_bridge_fails_closed_for_conflicts_absence_and_unavailable_origin() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    for field in (
        "employment_type",
        "required_languages",
        "weekly_hours",
        "requirements_seniority",
    ):
        assert f"? '{field}'" in source
    assert "observed_bounded_text" in source
    assert "source_absent" not in source.split("CREATE OR REPLACE VIEW", 1)[1]
    assert "origin_unavailable" not in source.split("CREATE OR REPLACE VIEW", 1)[1]
    assert "THEN 'manual_review_required'" in source


def test_f4b_bridge_preserves_candidate_capability_as_separate_authority() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "WHEN e.capability_fit_status = 'failed' THEN 'failed'" in source
    assert "WHEN e.capability_fit_status <> 'passed'" in source
    assert "THEN 'manual_review_required'" in source
    assert "sidecar" not in source.split("WHEN e.capability_fit_status = 'failed'", 1)[1].split("END AS seniority_status", 1)[0]


def test_hard_filter_reviews_are_bound_to_exact_sidecar_revision() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS requirement_evidence_hash TEXT" in source
    assert "trg_bind_product_v1_hard_filter_review_requirement_hash" in source
    assert "trg_supersede_hard_filter_review_on_requirement_change" in source
    assert "AFTER INSERT OR UPDATE OF evidence_hash" in source
    assert "requirement_evidence_hash IS DISTINCT FROM NEW.evidence_hash" in source
    assert "r.requirement_evidence_hash IS NOT DISTINCT FROM d.requirement_evidence_hash" in source
    assert "Existing active reviews predate sidecar-hash binding" in source


def test_bridge_does_not_change_top5_or_ranking_policy() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "product_v1_ranking_policy" not in source
    assert "gold_product_v1_top_jobs" not in source
    assert "application" not in source.casefold().split("CREATE OR REPLACE VIEW", 1)[1]
