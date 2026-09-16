from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "DRJ-BRANCH-DISPOSITIONS.json"
LEDGERS = (
    ROOT / "docs" / "knowledge" / "drj_branch_dispositions_20260916.md",
    ROOT / "docs" / "knowledge" / "drj_branch_dispositions_20260916_batch2.md",
)

EXPECTED_REPOSITORY = "jenshaberle-dotcom/job-application-pipeline"
EXPECTED_REPOSITORY_ID = 1230805345
EXPECTED_SCHEMA = "drj.branch_dispositions.v1"
EXPECTED_BRANCHES = {
    "agent/630-workday-cxs-acquisition",
    "agent/676-external-deterministic-salvage",
    "agent/707-private-candidate-fact-approval",
    "agent/707-private-candidate-fact-approval-refresh",
    "agent/f4a-profile-fit-coverage",
    "agent/origin-entity-locale-and-brand-aliases",
    "agent/origin-evidence-main-integration-001",
    "agent/origin-secret-names-001",
    "agent/p1-full-connector-inventory-audit",
    "agent/p1-generic-origin-z-baseline",
    "agent/p1-origin-initial-proof-revalidation",
    "agent/p1-promote-proven-origin-connectors",
    "agent/v41-manual-hardening",
    "agent/warm-hosted-fallback-jobapp-001a",
    "docs/acq-runtime-api-strategy-reentry",
    "feature/runtime-runner-selector-hardening",
    "hotfix/product-v1-view-type-stability",
}
SEMANTIC = {"RETIRE", "SUPERSEDED", "DEPRECATED"}
UNIQUE_HISTORY = {"CANONICALIZED", "HARVESTED", "REJECTED"}
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _payload() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def _ledger_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in LEDGERS)


def test_branch_dispositions_are_exactly_scoped_and_sha_bound() -> None:
    payload = _payload()
    assert payload["schema_version"] == EXPECTED_SCHEMA
    assert payload["repository"] == EXPECTED_REPOSITORY
    assert payload["repository_id"] == EXPECTED_REPOSITORY_ID

    records = payload["records"]
    assert len(records) == len(EXPECTED_BRANCHES)
    assert {record["branch"] for record in records} == EXPECTED_BRANCHES
    assert len({record["branch"] for record in records}) == len(records)

    for record in records:
        assert set(record) == {
            "branch",
            "expected_sha",
            "semantic_disposition",
            "unique_history_disposition",
            "evidence_refs",
        }
        assert SHA40.fullmatch(record["expected_sha"])
        assert record["semantic_disposition"] in SEMANTIC
        assert record["unique_history_disposition"] in UNIQUE_HISTORY
        assert isinstance(record["evidence_refs"], list)
        assert record["evidence_refs"]
        assert all(isinstance(ref, str) and ref.strip() for ref in record["evidence_refs"])


def test_every_machine_record_has_durable_ledger_entry() -> None:
    ledger = _ledger_text()
    for record in _payload()["records"]:
        heading = f"### `{record['branch']}`"
        if record["branch"].startswith("docs/"):
            heading = f"### `refs/heads/{record['branch']}`"
        assert heading in ledger
        assert record["expected_sha"] in ledger
        assert record["semantic_disposition"] in ledger
        assert record["unique_history_disposition"] in ledger


def test_unresolved_refs_remain_outside_machine_terminal_scope() -> None:
    ledger = _ledger_text()
    expected_mentions = (
        "agent/676-deterministic-connector-builder",
        "agent/p1-connector-delivery-audit",
        "agent/f2-acceptance-cohort",
        "agent/f2-operator-cold-e2e",
        "agent/rcc-step1-wsl-inventory-001a",
        "agent/winapp-020-prebuilt-frontend-startup",
        "rcc-workload-ready-jap-canary",
        "tmp/jap-lockgen-final",
    )
    for mention in expected_mentions:
        assert f"`{mention}`" in ledger
        assert mention not in EXPECTED_BRANCHES


def test_batch_two_is_exactly_three_additional_terminal_records() -> None:
    payload_by_branch = {record["branch"]: record for record in _payload()["records"]}
    assert payload_by_branch["agent/warm-hosted-fallback-jobapp-001a"][
        "expected_sha"
    ] == "62dd3754fadd739a6f8124fa0f8a3cccf2e81bed"
    assert payload_by_branch["docs/acq-runtime-api-strategy-reentry"][
        "expected_sha"
    ] == "7e9d08a2ce2bda0e414f6125a460931eaf287255"
    assert payload_by_branch["feature/runtime-runner-selector-hardening"][
        "expected_sha"
    ] == "1833eafadabd3b8f6dac80de14614929a099d10f"


def test_semantic_evidence_file_contains_no_effect_authority() -> None:
    payload = _payload()
    serialized = json.dumps(payload, sort_keys=True)
    assert "effect_authority" not in serialized
    assert "delete_authority" not in serialized
    assert "DELETE" not in serialized
