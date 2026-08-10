from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

import scripts.run_cand001_validated_origin_url_persistence_gate as cand_runner
from src.search_intelligence.cand001_validated_origin_url_persistence import (
    BOUNDARY,
    CandidatePersistenceSnapshot,
    OriginUrlValidationEvidence,
    build_persistence_plan_item,
    evidence_from_origin_discovery_payload,
    markdown_report,
    report_payload,
    summarize_plan,
)


def candidate(
    candidate_url: str | None = None,
    status: str = "discovery",
) -> CandidatePersistenceSnapshot:
    return CandidatePersistenceSnapshot(
        candidate_id=36,
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        status=status,
        candidate_url=candidate_url,
        risk_level="medium",
    )


def good_evidence(
    url: str = "https://jobs.hannover-re.com/",
) -> OriginUrlValidationEvidence:
    return OriginUrlValidationEvidence(
        selected_url=url,
        success_tier="A",
        decision="origin_url_candidate_selected",
        confidence_score=1.0,
        reason="reachable career/job-like URL",
        risk_level="low",
    )


def test_empty_candidate_url_recommends_sz1_persistence() -> None:
    item = build_persistence_plan_item(candidate(), good_evidence())
    assert item.decision == "persist_validated_candidate_url"
    assert item.review_status == "write_recommended"
    assert item.apply_allowed is True
    assert item.manual_review_required is True
    assert item.safety_zone == "SZ1_CANDIDATE_METADATA"


def test_active_controlled_is_protected_by_default() -> None:
    item = build_persistence_plan_item(
        candidate(status="active_controlled"), good_evidence()
    )
    assert item.decision == "skip_protected_active_controlled"
    assert item.apply_allowed is False
    assert item.review_status == "skipped"


def test_existing_same_url_is_no_action() -> None:
    item = build_persistence_plan_item(
        candidate("https://jobs.hannover-re.com"), good_evidence()
    )
    assert item.decision == "no_action_already_persisted"
    assert item.manual_review_required is False


def test_existing_different_url_requires_manual_review() -> None:
    item = build_persistence_plan_item(
        candidate("https://example.com/careers"), good_evidence()
    )
    assert item.decision == "manual_review_required_url_conflict"
    assert item.apply_allowed is False
    assert item.manual_review_required is True


def test_weak_url_finder_evidence_is_not_written() -> None:
    weak = OriginUrlValidationEvidence(
        selected_url="https://jobs.hannover-re.com/",
        success_tier="D",
        decision="not_found",
        confidence_score=0.2,
        reason="weak",
        risk_level="medium",
    )
    item = build_persistence_plan_item(candidate(), weak)
    assert item.decision == "manual_review_required"
    assert item.apply_allowed is False


def test_duplicate_selected_url_requires_manual_review() -> None:
    item = build_persistence_plan_item(
        candidate(), good_evidence(), duplicate_selected_url_exists=True
    )
    assert item.decision == "manual_review_required_duplicate_url"
    assert item.apply_allowed is False


def test_summary_and_markdown_report_include_boundaries() -> None:
    item = build_persistence_plan_item(candidate(), good_evidence())
    summary = summarize_plan([item])
    assert summary.write_recommended_count == 1
    assert summary.boundary["no_export_as_input_source_of_truth"] is True
    payload = report_payload(benchmark_label="cand001_test", items=[item])
    md = markdown_report(payload)
    assert "CAND-001 Validated Origin URL Persistence Gate" in md
    assert "persist_validated_candidate_url" in md
    assert "URL-Finder report exports are review context" in md


def test_migration_and_docs_exist() -> None:
    migration = Path(
        "db/migrations/073_create_candidate_origin_url_persistence_reviews.sql"
    ).read_text(encoding="utf-8")
    assert "candidate_origin_url_persistence_reviews" in migration
    assert "no scheduler changes" in migration
    doc = Path(
        "docs/archive/planning/cand001_validated_origin_url_persistence_gate.md"
    ).read_text(encoding="utf-8")
    assert "CAND-001" in doc
    assert "not source-of-truth inputs" in doc


def test_boundary_is_sz1_only() -> None:
    assert BOUNDARY["sz1_candidate_metadata_transition"] is True
    assert BOUNDARY["no_gate_write"] is True
    assert BOUNDARY["no_source_activation"] is True


def test_live_origin_payload_without_explicit_tier_derives_a_tier() -> None:
    evidence = evidence_from_origin_discovery_payload(
        {
            "selected_url": "https://jobs.hannover-re.com/",
            "decision": "origin_url_candidate_selected",
            "confidence_score": 1.0,
            "reason": "reachable career/job-like URL",
            "risk_level": "low",
        }
    )

    assert evidence.success_tier == "A"
    item = build_persistence_plan_item(candidate(), evidence)
    assert item.decision == "persist_validated_candidate_url"
    assert item.review_status == "write_recommended"
    assert item.apply_allowed is True


def test_apply_sql_handles_null_and_empty_candidate_url() -> None:
    script = Path(
        "scripts/run_cand001_validated_origin_url_persistence_gate.py"
    ).read_text(encoding="utf-8")
    assert "candidate_url IS NULL OR btrim(candidate_url) = ''" in script


class FakeCursor:
    def __init__(self, row: dict[str, object] | None) -> None:
        self.row = row
        self.executed: list[tuple[str, tuple[object, ...] | None]] = []
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, query: str, params=None) -> None:
        self.executed.append((query, params))

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row: dict[str, object] | None) -> None:
        self.cursor_instance = FakeCursor(row)

    def cursor(self, **_kwargs):
        return self.cursor_instance


def exact_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": 36,
        "company_key": "hannover_ruck",
        "company_name": "Hannover Rück SE",
        "status": "discovery",
        "candidate_url": None,
        "risk_level": "medium",
    }
    row.update(overrides)
    return row


def test_exact_candidate_load_queries_by_id_not_latest_company_row() -> None:
    conn = FakeConnection(exact_row())

    loaded = cand_runner.load_candidate(
        conn,
        "hannover_ruck",
        candidate_id=36,
    )

    query, params = conn.cursor_instance.executed[0]
    assert "WHERE id = %s" in query
    assert "ORDER BY updated_at" not in query
    assert params == (36,)
    assert loaded.candidate_id == 36


def test_exact_candidate_load_rejects_company_key_mismatch() -> None:
    conn = FakeConnection(exact_row(company_key="wrong_company"))

    with pytest.raises(SystemExit, match="Exact candidate identity mismatch"):
        cand_runner.load_candidate(
            conn,
            "hannover_ruck",
            candidate_id=36,
        )


def test_exact_identity_map_refuses_company_key_only_fallback() -> None:
    args = Namespace(candidate_id_by_company_key={"hannover_ruck": 36})
    assert cand_runner._exact_candidate_id_for_company(args, "hannover_ruck") == 36

    with pytest.raises(SystemExit, match="refusing company-key-only fallback"):
        cand_runner._exact_candidate_id_for_company(args, "other_company")

    assert (
        cand_runner._exact_candidate_id_for_company(Namespace(), "hannover_ruck")
        is None
    )


def test_write_fails_closed_on_locked_status_drift(monkeypatch) -> None:
    conn = FakeConnection(exact_row(status="manual_review_required"))
    item = build_persistence_plan_item(candidate(), good_evidence())
    monkeypatch.setattr(cand_runner, "_db_object_exists", lambda *_args: True)

    with pytest.raises(SystemExit, match="status drift"):
        cand_runner.write_review_and_candidate_url(
            conn,
            item=item,
            evidence=good_evidence(),
            reviewed_by="test",
        )

    query, params = conn.cursor_instance.executed[0]
    assert "FOR UPDATE" in query
    assert params == (36,)


def test_write_fails_closed_on_locked_url_drift(monkeypatch) -> None:
    conn = FakeConnection(
        exact_row(candidate_url="https://already.example/careers")
    )
    item = build_persistence_plan_item(candidate(), good_evidence())
    monkeypatch.setattr(cand_runner, "_db_object_exists", lambda *_args: True)

    with pytest.raises(SystemExit, match="URL drift"):
        cand_runner.write_review_and_candidate_url(
            conn,
            item=item,
            evidence=good_evidence(),
            reviewed_by="test",
        )
