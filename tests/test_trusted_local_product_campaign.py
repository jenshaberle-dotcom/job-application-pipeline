from __future__ import annotations

import pytest

from scripts.run_employer_origin_agent_chain import ChainDecision
from scripts.run_trusted_local_product_campaign import (
    MODE_DB_ONLY,
    decision_execution_policy,
    validate_inputs,
)


def test_allowlisted_db_action_requires_exact_module() -> None:
    decision = ChainDecision(
        action="run_preconnector_precondition_recovery",
        reason="test",
        module="scripts.run_employer_origin_preconnector_precondition_agent",
        args=("--company-key", "valuny"),
    )

    policy = decision_execution_policy(decision, mode=MODE_DB_ONLY)

    assert policy.executable is True
    assert policy.boundary is None


def test_allowlisted_db_action_fails_closed_on_module_drift() -> None:
    decision = ChainDecision(
        action="run_preconnector_precondition_recovery",
        reason="test",
        module="scripts.unexpected_module",
        args=(),
    )

    policy = decision_execution_policy(decision, mode=MODE_DB_ONLY)

    assert policy.executable is False
    assert policy.boundary == "decision_module_mismatch"


def test_repo_mutation_is_an_expected_db_only_boundary() -> None:
    decision = ChainDecision(
        action="run_connector_artifact_generator",
        reason="artifacts missing",
        module="scripts.run_employer_origin_connector_artifact_generator",
        args=("--company-key", "valuny", "--dry-run"),
    )

    policy = decision_execution_policy(decision, mode=MODE_DB_ONLY)

    assert policy.executable is False
    assert policy.boundary == "repo_mutation_required"


def test_explicit_approval_stop_is_never_auto_executed() -> None:
    decision = ChainDecision(
        action="stop_explicit_approval_required",
        reason="approval required",
    )

    policy = decision_execution_policy(decision, mode=MODE_DB_ONLY)

    assert policy.executable is False
    assert policy.boundary == "stop_explicit_approval_required"


def test_unrecognized_action_fails_closed() -> None:
    decision = ChainDecision(
        action="run_unknown_mutator",
        reason="unknown",
        module="scripts.run_unknown_mutator",
        args=(),
    )

    policy = decision_execution_policy(decision, mode=MODE_DB_ONLY)

    assert policy.executable is False
    assert policy.boundary == "unrecognized_chain_action"


def test_command_input_contract() -> None:
    validate_inputs(
        company_key="valuny",
        candidate_id=83,
        target_location="hannover",
        max_steps=12,
        mode=MODE_DB_ONLY,
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"company_key": "VALUNY GmbH"},
        {"candidate_id": 0},
        {"target_location": "hannover\nrm -rf /"},
        {"max_steps": 21},
        {"mode": "full_mutation"},
    ],
)
def test_command_input_contract_fails_closed(kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "company_key": "valuny",
        "candidate_id": 83,
        "target_location": "hannover",
        "max_steps": 12,
        "mode": MODE_DB_ONLY,
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        validate_inputs(**values)  # type: ignore[arg-type]
