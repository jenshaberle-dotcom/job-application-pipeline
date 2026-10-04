"""Execute RCC-selected suites from an immutable trusted consumer policy.

This launcher is extracted from the policy's trusted main commit by the workflow.
It owns no test selection, runner lifecycle or workflow dispatch.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def verify(plan, policy, *, source_sha, base_sha):
    expected = {
        "schema_version",
        "repository",
        "source_sha",
        "base_sha",
        "policy_sha",
        "policy_digest",
        "policy_version",
        "runtime_fingerprint",
        "action",
        "suite_ids",
        "selection_reasons",
        "omissions",
        "execution_digest",
        "plan_digest",
    }
    if (
        not isinstance(plan, dict)
        or set(plan) != expected
        or plan["schema_version"] != "rcc.validation_test_plan.v1"
    ):
        raise ValueError("test_plan_shape_invalid")
    if digest({k: v for k, v in plan.items() if k != "plan_digest"}) != plan["plan_digest"]:
        raise ValueError("test_plan_digest_invalid")
    identity_fields = (
        "repository",
        "source_sha",
        "base_sha",
        "policy_sha",
        "policy_digest",
        "runtime_fingerprint",
        "suite_ids",
    )
    if digest({key: plan[key] for key in identity_fields}) != plan["execution_digest"]:
        raise ValueError("test_execution_digest_invalid")
    if (
        plan["source_sha"] != source_sha
        or plan["base_sha"] != base_sha
        or plan["policy_sha"] != base_sha
        or any(
            not re.fullmatch(r"[0-9a-f]{40}", plan[key])
            for key in ("source_sha", "base_sha", "policy_sha")
        )
    ):
        raise ValueError("test_plan_source_mismatch")
    if (
        policy["repository"] != plan["repository"]
        or digest(policy) != plan["policy_digest"]
        or policy["version"] != plan["policy_version"]
    ):
        raise ValueError("test_plan_policy_mismatch")
    action = policy["actions"].get(plan["action"])
    ids = plan["suite_ids"]
    if (
        not action
        or not isinstance(ids, list)
        or not ids
        or len(ids) != len(set(ids))
        or any(key not in policy["suites"] for key in ids)
        or not set(action["required"]).issubset(ids)
    ):
        raise ValueError("test_plan_required_suite_missing")
    for index, key in enumerate(ids):
        if not set(policy["suites"][key]["requires"]).issubset(ids[:index]):
            raise ValueError("test_plan_dependency_missing_or_out_of_order")
    return [command for key in ids for command in policy["suites"][key]["commands"]]


def execute(plan, policy, *, source_sha, base_sha, python, invoke=subprocess.run):
    commands = verify(plan, policy, source_sha=source_sha, base_sha=base_sha)
    for command in commands:
        if not isinstance(command, list) or not command or command[0] != "{python}":
            raise ValueError("trusted_test_command_invalid")
        invoke([python, *command[1:]], check=True)
    return {
        "schema_version": "rcc.validation_test_receipt.v1",
        "source_sha": source_sha,
        "base_sha": base_sha,
        "plan_digest": plan["plan_digest"],
        "execution_digest": plan["execution_digest"],
        "suite_ids": plan["suite_ids"],
        "status": "PASS",
    }


def main():
    raw = os.environ["RCC_TEST_PLAN"]
    if len(raw.encode()) > 4096:
        raise ValueError("test_plan_too_large")
    plan = json.loads(raw)
    trusted_sha = plan["policy_sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", trusted_sha):
        raise ValueError("test_policy_sha_invalid")
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if source != os.environ["SOURCE_SHA"]:
        raise ValueError("test_source_mismatch")
    if plan["runtime_fingerprint"] != os.environ["RCC_TEST_RUNTIME_FINGERPRINT"]:
        raise ValueError("test_runtime_identity_mismatch")
    policy = json.loads(
        subprocess.check_output(
            ["git", "show", f"{trusted_sha}:.rcc/test-management.json"], text=True
        )
    )
    receipt = execute(plan, policy, source_sha=source, base_sha=trusted_sha, python=sys.executable)
    output = Path("artifacts/validation-test-receipt.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
