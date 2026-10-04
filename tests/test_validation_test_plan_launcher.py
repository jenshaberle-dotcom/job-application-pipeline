import copy
import json
import subprocess
from pathlib import Path

import pytest

from scripts.run_validation_test_plan import digest, execute, verify


def fixture(action="merge", ids=None):
    policy = json.loads(Path(".rcc/test-management.json").read_text())
    ids = ids or ["full"]
    plan = {
        "schema_version": "rcc.validation_test_plan.v1",
        "repository": policy["repository"],
        "source_sha": "a" * 40,
        "base_sha": "b" * 40,
        "policy_sha": "b" * 40,
        "policy_digest": digest(policy),
        "policy_version": 1,
        "runtime_fingerprint": "d" * 64,
        "action": action,
        "suite_ids": ids,
        "selection_reasons": {},
        "omissions": {},
    }
    fields = (
        "repository",
        "source_sha",
        "base_sha",
        "policy_sha",
        "policy_digest",
        "runtime_fingerprint",
        "suite_ids",
    )
    plan["execution_digest"] = digest({key: plan[key] for key in fields})
    plan["plan_digest"] = digest(plan)
    return plan, policy


def test_launcher_executes_trusted_commands_without_shell_and_returns_bound_receipt():
    plan, policy = fixture("diagnostic", ["census", "factory"])
    calls = []
    receipt = execute(
        plan,
        policy,
        source_sha="a" * 40,
        base_sha="b" * 40,
        python="/qualified/python",
        invoke=lambda argv, **kwargs: calls.append((argv, kwargs)),
    )
    assert len(calls) == 2
    assert calls[0][0][0] == "/qualified/python"
    assert calls[0][1] == {"check": True}
    assert receipt["plan_digest"] == plan["plan_digest"]
    assert receipt["status"] == "PASS"


def test_forged_smaller_merge_plan_is_rejected_even_with_recomputed_digest():
    plan, policy = fixture("merge", ["census"])
    with pytest.raises(ValueError, match="required_suite_missing"):
        verify(plan, policy, source_sha="a" * 40, base_sha="b" * 40)


@pytest.mark.parametrize("kind", ["plan", "source", "policy"])
def test_tampering_source_and_policy_mismatch_fail_closed(kind):
    plan, policy = fixture()
    if kind == "plan":
        plan["suite_ids"] = ["census"]
    elif kind == "policy":
        policy = copy.deepcopy(policy)
        policy["version"] = 2
    with pytest.raises(ValueError):
        verify(
            plan, policy, source_sha=("c" * 40 if kind == "source" else "a" * 40), base_sha="b" * 40
        )


def test_failed_suite_cannot_create_success_receipt():
    plan, policy = fixture()

    def failed(argv, **kwargs):
        raise subprocess.CalledProcessError(1, argv)

    with pytest.raises(subprocess.CalledProcessError):
        execute(
            plan,
            policy,
            source_sha="a" * 40,
            base_sha="b" * 40,
            python="/qualified/python",
            invoke=failed,
        )
