from __future__ import annotations

from argparse import Namespace

import pytest

import scripts.apply_employer_origin_detail_evidence_pass as apply_pass
from scripts.run_employer_origin_detail_evidence_repair_agent import RepairOutcome, SourceCandidate


def candidate() -> SourceCandidate:
    return SourceCandidate(
        id=46,
        company_key="1_1",
        company_name="1&1",
        candidate_url="https://career.example.com/",
        source_name_candidate="1_1:discovery",
        source_family_candidate="1_1",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )


def args(*, approval_token: str = apply_pass.APPROVAL_TOKEN) -> Namespace:
    return Namespace(
        candidate_id=46,
        expected_company_key="1_1",
        expected_candidate_status="discovery",
        approval_token=approval_token,
        target_location="hannover",
        profile_term=None,
        location_term=None,
        max_seed_pages=8,
        max_detail_pages=6,
        max_search_queries=4,
        max_search_results=6,
        search_provider="duckduckgo_html",
        disable_search_discovery=False,
        reviewed_by="jens",
    )


def passed_outcome() -> RepairOutcome:
    return RepairOutcome(
        gate_status="passed",
        decision="passed",
        stop_reason=None,
        details=(object(),),
        rejected_urls=(),
        requested_urls=(),
        evidence={"decision_taxonomy": "accepted"},
    )


def non_pass_outcome() -> RepairOutcome:
    return RepairOutcome(
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="fresh evidence did not pass",
        details=(),
        rejected_urls=(),
        requested_urls=(),
        evidence={"decision_taxonomy": "manual_review_required"},
    )


class FakeConnection:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def commit(self) -> None:
        self.committed = True


class FakeRepo:
    wrote = False

    def __init__(self, conn) -> None:
        self.conn = conn

    def load_candidate(self, *, candidate_id, company_key):
        assert candidate_id == 46
        assert company_key is None
        return candidate()

    def load_gates(self, candidate_id):
        assert candidate_id == 46
        return {}

    def record_detail_evidence_gate(self, *, candidate_id, outcome, reviewed_by):
        assert candidate_id == 46
        assert outcome.gate_status == "passed"
        assert reviewed_by == "jens"
        type(self).wrote = True


def install_fake_runtime(monkeypatch, outcome: RepairOutcome) -> FakeConnection:
    conn = FakeConnection()
    FakeRepo.wrote = False
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setattr(apply_pass.psycopg, "connect", lambda *_args, **_kwargs: conn)
    monkeypatch.setattr(apply_pass, "GateStateRepository", FakeRepo)
    monkeypatch.setattr(apply_pass, "load_local_env_file", lambda: None)
    monkeypatch.setattr(apply_pass, "build_repair_outcome", lambda **_kwargs: outcome)
    monkeypatch.setattr(apply_pass, "repair_report_lines", lambda *_args: [])
    monkeypatch.setattr(apply_pass, "lock_and_revalidate_candidate", lambda *_args, **_kwargs: None)
    return conn


def test_reviewed_pass_apply_writes_only_after_exact_fresh_pass(monkeypatch) -> None:
    conn = install_fake_runtime(monkeypatch, passed_outcome())

    assert apply_pass.run_apply(args()) == 0
    assert FakeRepo.wrote is True
    assert conn.committed is True


def test_wrong_approval_token_stops_before_connection(monkeypatch) -> None:
    monkeypatch.setattr(
        apply_pass.psycopg,
        "connect",
        lambda *_args, **_kwargs: pytest.fail("DB connection must not occur for a bad token"),
    )

    with pytest.raises(apply_pass.ReviewedPassApplyError, match="approval_token_mismatch"):
        apply_pass.run_apply(args(approval_token="wrong"))


def test_company_key_only_apply_is_not_a_supported_cli_shape() -> None:
    parser = apply_pass.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--company-key",
                "1_1",
                "--expected-company-key",
                "1_1",
                "--approval-token",
                apply_pass.APPROVAL_TOKEN,
            ]
        )


def test_fresh_non_pass_stops_before_gate_write(monkeypatch) -> None:
    conn = install_fake_runtime(monkeypatch, non_pass_outcome())

    with pytest.raises(apply_pass.ReviewedPassApplyError, match="fresh_detail_evidence_not_passed"):
        apply_pass.run_apply(args())

    assert FakeRepo.wrote is False
    assert conn.committed is False


def test_candidate_identity_guard_rejects_state_drift() -> None:
    drifted = candidate()
    drifted = SourceCandidate(**{**drifted.__dict__, "status": "active_controlled"})

    with pytest.raises(apply_pass.ReviewedPassApplyError, match="candidate_status_mismatch"):
        apply_pass.validate_candidate_identity(
            drifted,
            expected_company_key="1_1",
            expected_status="discovery",
        )
