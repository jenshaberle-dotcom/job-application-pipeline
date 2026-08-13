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


def args(
    *,
    approval_token: str = apply_pass.APPROVAL_TOKEN,
    enable_greenhouse_delegation: bool = False,
    expected_detail_gate_status: str | None = None,
    expected_detail_gate_decision: str | None = None,
    expected_detail_reviewed_by: str | None = None,
) -> Namespace:
    return Namespace(
        candidate_id=46,
        expected_company_key="1_1",
        expected_candidate_status="discovery",
        expected_detail_gate_status=expected_detail_gate_status,
        expected_detail_gate_decision=expected_detail_gate_decision,
        expected_detail_reviewed_by=expected_detail_reviewed_by,
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
        enable_greenhouse_delegation=enable_greenhouse_delegation,
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
    def __init__(self, label: str) -> None:
        self.label = label
        self.active = False
        self.committed = False
        self.rolled_back = False
        self.executed: list[str] = []

    def __enter__(self):
        self.active = True
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.active = False
        return False

    def execute(self, query: str, *_args, **_kwargs):
        self.executed.append(query)
        return self

    def rollback(self) -> None:
        self.rolled_back = True

    def commit(self) -> None:
        self.committed = True


class FakeRepo:
    wrote = False
    gates: dict[str, dict[str, object]] = {}

    def __init__(self, conn) -> None:
        self.conn = conn

    def load_candidate(self, *, candidate_id, company_key):
        assert candidate_id == 46
        assert company_key is None
        return candidate()

    def load_gates(self, candidate_id):
        assert candidate_id == 46
        return dict(type(self).gates)

    def record_detail_evidence_gate(self, *, candidate_id, outcome, reviewed_by):
        assert candidate_id == 46
        assert outcome.gate_status == "passed"
        assert reviewed_by == "jens"
        type(self).wrote = True


def install_fake_runtime(
    monkeypatch,
    outcome: RepairOutcome,
    *,
    greenhouse_outcome: RepairOutcome | None = None,
    gates: dict[str, dict[str, object]] | None = None,
):
    connections: list[FakeConnection] = []
    builder_calls = {"ordinary": 0, "greenhouse": 0}

    def connect(*_args, **_kwargs):
        conn = FakeConnection(f"conn-{len(connections) + 1}")
        connections.append(conn)
        return conn

    def assert_network_phase_has_no_open_db_transaction() -> None:
        assert len(connections) == 1
        assert connections[0].active is False
        assert connections[0].rolled_back is True

    def ordinary_builder(**_kwargs):
        builder_calls["ordinary"] += 1
        assert_network_phase_has_no_open_db_transaction()
        return outcome

    def greenhouse_builder(**_kwargs):
        builder_calls["greenhouse"] += 1
        assert_network_phase_has_no_open_db_transaction()
        return greenhouse_outcome if greenhouse_outcome is not None else outcome

    FakeRepo.wrote = False
    FakeRepo.gates = gates or {}
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setattr(apply_pass.psycopg, "connect", connect)
    monkeypatch.setattr(apply_pass, "GateStateRepository", FakeRepo)
    monkeypatch.setattr(apply_pass, "load_local_env_file", lambda: None)
    monkeypatch.setattr(apply_pass, "build_repair_outcome", ordinary_builder)
    monkeypatch.setattr(apply_pass, "build_greenhouse_delegated_repair_outcome", greenhouse_builder)
    monkeypatch.setattr(apply_pass, "repair_report_lines", lambda *_args: [])
    monkeypatch.setattr(apply_pass, "lock_and_revalidate_candidate", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(apply_pass, "lock_and_revalidate_detail_gate", lambda *_args, **_kwargs: None)
    return connections, builder_calls


def test_reviewed_pass_apply_uses_short_read_snapshot_then_existing_writer(monkeypatch) -> None:
    connections, calls = install_fake_runtime(monkeypatch, passed_outcome())

    assert apply_pass.run_apply(args()) == 0

    assert calls == {"ordinary": 1, "greenhouse": 0}
    assert len(connections) == 2
    assert "SET TRANSACTION READ ONLY" in connections[0].executed
    assert connections[0].rolled_back is True
    assert connections[0].committed is False
    assert FakeRepo.wrote is True
    assert connections[1].committed is True


def test_greenhouse_mode_uses_delegated_builder_not_ordinary_builder(monkeypatch) -> None:
    connections, calls = install_fake_runtime(
        monkeypatch,
        non_pass_outcome(),
        greenhouse_outcome=passed_outcome(),
    )

    assert apply_pass.run_apply(args(enable_greenhouse_delegation=True)) == 0

    assert calls == {"ordinary": 0, "greenhouse": 1}
    assert len(connections) == 2
    assert FakeRepo.wrote is True
    assert connections[1].committed is True


def test_wrong_approval_token_stops_before_connection(monkeypatch) -> None:
    monkeypatch.setattr(
        apply_pass.psycopg,
        "connect",
        lambda *_args, **_kwargs: pytest.fail("DB connection must not occur for a bad token"),
    )

    with pytest.raises(apply_pass.ReviewedPassApplyError, match="approval_token_mismatch"):
        apply_pass.run_apply(args(approval_token="wrong"))


def test_incomplete_detail_gate_precondition_stops_before_connection(monkeypatch) -> None:
    monkeypatch.setattr(
        apply_pass.psycopg,
        "connect",
        lambda *_args, **_kwargs: pytest.fail("DB connection must not occur for incomplete gate precondition"),
    )

    with pytest.raises(
        apply_pass.ReviewedPassApplyError,
        match="incomplete_expected_detail_gate_precondition",
    ):
        apply_pass.run_apply(args(expected_detail_gate_status="manual_review_required"))


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


def test_fresh_non_pass_stops_before_write_connection(monkeypatch) -> None:
    connections, calls = install_fake_runtime(monkeypatch, non_pass_outcome())

    with pytest.raises(apply_pass.ReviewedPassApplyError, match="fresh_detail_evidence_not_passed"):
        apply_pass.run_apply(args())

    assert calls == {"ordinary": 1, "greenhouse": 0}
    assert len(connections) == 1
    assert connections[0].rolled_back is True
    assert FakeRepo.wrote is False
    assert connections[0].committed is False


def test_snapshot_detail_gate_drift_stops_before_network_or_write(monkeypatch) -> None:
    connections, calls = install_fake_runtime(
        monkeypatch,
        passed_outcome(),
        gates={
            apply_pass.DETAIL_EVIDENCE_GATE: {
                "gate_status": "passed",
                "decision": "passed",
                "reviewed_by": "other",
            }
        },
    )

    with pytest.raises(
        apply_pass.ReviewedPassApplyError,
        match="detail_gate_status_mismatch_before_evidence_refresh",
    ):
        apply_pass.run_apply(
            args(
                expected_detail_gate_status="manual_review_required",
                expected_detail_gate_decision="manual_review_required",
                expected_detail_reviewed_by="pipeline_514_runtime",
            )
        )

    assert calls == {"ordinary": 0, "greenhouse": 0}
    assert len(connections) == 1
    assert FakeRepo.wrote is False


def test_write_time_detail_gate_drift_stops_before_existing_writer(monkeypatch) -> None:
    current_gate = {
        apply_pass.DETAIL_EVIDENCE_GATE: {
            "gate_status": "manual_review_required",
            "decision": "manual_review_required",
            "reviewed_by": "pipeline_514_runtime",
        }
    }
    connections, calls = install_fake_runtime(
        monkeypatch,
        passed_outcome(),
        gates=current_gate,
    )

    def reject_gate_drift(*_args, **_kwargs):
        raise apply_pass.ReviewedPassApplyError("detail_gate_status_drift_before_write")

    monkeypatch.setattr(apply_pass, "lock_and_revalidate_detail_gate", reject_gate_drift)

    with pytest.raises(
        apply_pass.ReviewedPassApplyError,
        match="detail_gate_status_drift_before_write",
    ):
        apply_pass.run_apply(
            args(
                expected_detail_gate_status="manual_review_required",
                expected_detail_gate_decision="manual_review_required",
                expected_detail_reviewed_by="pipeline_514_runtime",
            )
        )

    assert calls == {"ordinary": 1, "greenhouse": 0}
    assert len(connections) == 2
    assert FakeRepo.wrote is False
    assert connections[1].committed is False


def test_candidate_identity_guard_rejects_state_drift() -> None:
    drifted = candidate()
    drifted = SourceCandidate(**{**drifted.__dict__, "status": "active_controlled"})

    with pytest.raises(apply_pass.ReviewedPassApplyError, match="candidate_status_mismatch"):
        apply_pass.validate_candidate_identity(
            drifted,
            expected_company_key="1_1",
            expected_status="discovery",
        )
