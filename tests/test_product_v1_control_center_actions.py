from __future__ import annotations

from io import BytesIO
import json

import pytest

from scripts import product_v1_control_center_actions as actions
from scripts import run_product_v1_control_center as server
from scripts.run_employer_origin_final_approval_gate_agent import (
    GateReview,
    SourceCandidate,
)
from src.search_intelligence.connector_autonomy import (
    A1_ALLOWED_ACTIVATION_READINESS,
    A1_AUTONOMY_LEVEL,
    A1_POLICY_KEY,
    ConnectorAutonomyPolicy,
)


def _policy(*, status: str = "approved") -> ConnectorAutonomyPolicy:
    return ConnectorAutonomyPolicy(
        policy_key=A1_POLICY_KEY,
        autonomy_level=A1_AUTONOMY_LEVEL,
        status=status,
        policy_version="control-center-a1-test",
        standing_authorization=True,
        require_connector_validation=True,
        require_exact_activation_readiness=True,
        allowed_activation_readiness=A1_ALLOWED_ACTIVATION_READINESS,
        allow_connector_registration=True,
        allow_controlled_source_activation=True,
        allow_bounded_first_ingestion=True,
        allow_recurring_ingestion=False,
        allow_scheduler_mutation=False,
        allow_provider_requests=False,
        allow_ranking_mutation=False,
        allow_application_actions=False,
        approved_by="jens",
    )


def _candidate() -> SourceCandidate:
    return SourceCandidate(
        id=17,
        company_key="example",
        source_name_candidate="example:hannover",
        status="connector_candidate",
    )


def _validation_gate() -> GateReview:
    return GateReview(
        gate_name="connector_validation_gate",
        gate_status="passed",
        decision="ready_for_final_approval",
        stop_reason=None,
    )


class FakeConnection:
    def __init__(self) -> None:
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1


class FakeRepository:
    def __init__(
        self,
        *,
        gates: dict[str, GateReview] | None = None,
        policy: ConnectorAutonomyPolicy | None = None,
    ) -> None:
        self.candidate = _candidate()
        self.gates = gates if gates is not None else {"connector_validation_gate": _validation_gate()}
        self.policy = policy
        self.recorded: list[tuple[SourceCandidate, object]] = []

    def load_candidate(self, *, candidate_id: int | None, company_key: str | None):
        assert company_key is None
        assert candidate_id == self.candidate.id
        return self.candidate

    def load_gates(self, candidate_id: int):
        assert candidate_id == self.candidate.id
        return self.gates

    def load_autonomy_policy(self):
        return self.policy

    def record_gate(self, *, candidate: SourceCandidate, outcome: object) -> None:
        self.recorded.append((candidate, outcome))


def _install_runtime(monkeypatch, repository: FakeRepository) -> FakeConnection:
    connection = FakeConnection()
    monkeypatch.setattr(actions, "get_database_config", lambda: {})
    monkeypatch.setattr(actions.psycopg, "connect", lambda **kwargs: connection)
    monkeypatch.setattr(actions, "ApprovalRepository", lambda conn: repository)
    return connection


def test_action_payload_requires_exact_allowlist_and_confirmation() -> None:
    assert actions.parse_final_approval_action_payload(
        {
            "candidate_id": 17,
            "confirmation": actions.FINAL_APPROVAL_CONFIRMATION,
        }
    ) == (17, actions.FINAL_APPROVAL_CONFIRMATION)

    with pytest.raises(actions.ControlCenterActionStop, match="unexpected fields: approval_token"):
        actions.parse_final_approval_action_payload(
            {
                "candidate_id": 17,
                "confirmation": actions.FINAL_APPROVAL_CONFIRMATION,
                "approval_token": "forbidden",
            }
        )
    with pytest.raises(actions.ControlCenterActionStop, match="exact final-approval confirmation"):
        actions.parse_final_approval_action_payload(
            {"candidate_id": 17, "confirmation": "yes"}
        )
    with pytest.raises(actions.ControlCenterActionStop, match="positive integer"):
        actions.parse_final_approval_action_payload(
            {
                "candidate_id": True,
                "confirmation": actions.FINAL_APPROVAL_CONFIRMATION,
            }
        )


def test_action_passes_only_via_standing_a1_and_records_existing_audit_contract(
    monkeypatch,
) -> None:
    repository = FakeRepository(policy=_policy())
    connection = _install_runtime(monkeypatch, repository)

    result = actions.apply_final_approval_action(
        candidate_id=17,
        confirmation=actions.FINAL_APPROVAL_CONFIRMATION,
    )

    assert result["status"] == "applied"
    assert result["candidate"]["candidate_id"] == 17
    assert result["gate"]["gate_status"] == "passed"
    assert result["gate"]["decision"] == "approve_connector_registration"
    assert result["gate"]["recorded"] is True
    assert result["authorization"]["mode"] == actions.STANDING_A1_MODE
    assert len(repository.recorded) == 1
    assert connection.commits == 1
    boundary = result["boundary"]
    assert boundary["legacy_approval_token_accepted"] is False
    assert boundary["connector_registration_performed"] is False
    assert boundary["source_activation_performed"] is False
    assert boundary["ingestion_performed"] is False
    assert boundary["provider_requests_performed"] is False
    assert boundary["ranking_mutation_performed"] is False
    assert boundary["application_action_performed"] is False


def test_action_preserves_manual_review_when_a1_is_not_active(monkeypatch) -> None:
    repository = FakeRepository(policy=_policy(status="paused"))
    connection = _install_runtime(monkeypatch, repository)

    result = actions.apply_final_approval_action(
        candidate_id=17,
        confirmation=actions.FINAL_APPROVAL_CONFIRMATION,
    )

    assert result["status"] == "review_required"
    assert result["gate"]["gate_status"] == "manual_review_required"
    assert result["gate"]["decision"] == "approval_token_required"
    assert result["authorization"]["mode"] == "approval_token_required"
    assert len(repository.recorded) == 1
    assert connection.commits == 1


def test_action_preserves_validation_prerequisite(monkeypatch) -> None:
    repository = FakeRepository(gates={}, policy=_policy())
    _install_runtime(monkeypatch, repository)

    result = actions.apply_final_approval_action(
        candidate_id=17,
        confirmation=actions.FINAL_APPROVAL_CONFIRMATION,
    )

    assert result["status"] == "review_required"
    assert result["gate"]["decision"] == "approval_blocked"
    assert result["authorization"]["mode"] == "blocked_missing_connector_validation"
    assert len(repository.recorded) == 1


def _handler(path: str, payload: object | None = None):
    handler = object.__new__(server.ProductV1Handler)
    handler.path = path
    body = b"" if payload is None else json.dumps(payload).encode("utf-8")
    handler.headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    }
    handler.rfile = BytesIO(body)
    responses: list[tuple[dict[str, object], object]] = []

    def send_json(payload: dict[str, object], *, status=200) -> None:
        responses.append((payload, status))

    handler._send_json = send_json  # type: ignore[method-assign]
    return handler, responses


def test_http_post_allowlist_calls_exact_action_once(monkeypatch) -> None:
    calls: list[tuple[int, str]] = []

    def apply_action(*, candidate_id: int, confirmation: str):
        calls.append((candidate_id, confirmation))
        return {"status": "applied", "candidate": {"candidate_id": candidate_id}}

    monkeypatch.setattr(server, "apply_final_approval_action", apply_action)
    handler, responses = _handler(
        actions.FINAL_APPROVAL_ACTION_PATH,
        {
            "candidate_id": 17,
            "confirmation": actions.FINAL_APPROVAL_CONFIRMATION,
        },
    )

    handler.do_POST()

    assert calls == [(17, actions.FINAL_APPROVAL_CONFIRMATION)]
    assert responses[0][0]["status"] == "applied"
    assert int(responses[0][1]) == 200


def test_unknown_post_path_remains_method_not_allowed(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        server,
        "apply_final_approval_action",
        lambda **kwargs: calls.append(1),
    )
    handler, responses = _handler("/api/v1/arbitrary-write", {})

    handler.do_POST()

    assert calls == []
    assert responses[0][0]["status"] == "blocked"
    assert int(responses[0][1]) == 405


def test_http_rejects_legacy_token_field_before_action(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        server,
        "apply_final_approval_action",
        lambda **kwargs: calls.append(1),
    )
    handler, responses = _handler(
        actions.FINAL_APPROVAL_ACTION_PATH,
        {
            "candidate_id": 17,
            "confirmation": actions.FINAL_APPROVAL_CONFIRMATION,
            "approval_token": "forbidden",
        },
    )

    handler.do_POST()

    assert calls == []
    assert responses[0][0]["status"] == "blocked"
    assert "approval_token" in str(responses[0][0]["reason"])
    assert int(responses[0][1]) == 400
