from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "DRJ-BRANCH-DISPOSITIONS.json"
LEDGER = ROOT / "docs" / "knowledge" / "drj_branch_dispositions_20260916.md"

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
    "hotfix/product-v1-view-type-stability",
}
SEMANTIC = {"RETIRE", "SUPERSEDED", "DEPRECATED"}
UNIQUE_HISTORY = {"CANONICALIZED", "HARVESTED", "REJECTED"}
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _payload() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


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
    ledger = LEDGER.read_text(encoding="utf-8")
    for record in _payload()["records"]:
        assert f"### `{record['branch']}`" in ledger
        assert record["expected_sha"] in ledger
        assert record["semantic_disposition"] in ledger
        assert record["unique_history_disposition"] in ledger


def test_batch_one_explicitly_preserves_unresolved_refs() -> None:
    ledger = LEDGER.read_text(encoding="utf-8")
    expected_mentions = (
        "agent/676-deterministic-connector-builder",
        "agent/p1-connector-delivery-audit",
        "agent/f2-acceptance-cohort",
        "agent/f2-operator-cold-e2e",
        "agent/rcc-step1-wsl-inventory-001a",
        "agent/warm-hosted-fallback-jobapp-001a",
        "agent/winapp-020-prebuilt-frontend-startup",
        "refs/heads/docs/acq-runtime-api-strategy-reentry",
        "feature/runtime-runner-selector-hardening",
        "rcc-workload-ready-jap-canary",
        "tmp/jap-lockgen-final",
    )
    for mention in expected_mentions:
        assert f"`{mention}`" in ledger

    assert "docs/acq-runtime-api-strategy-reentry" not in EXPECTED_BRANCHES
    for mention in expected_mentions:
        branch = mention.removeprefix("refs/heads/")
        assert branch not in EXPECTED_BRANCHES


def test_semantic_evidence_file_contains_no_effect_authority() -> None:
    payload = _payload()
    serialized = json.dumps(payload, sort_keys=True)
    assert "effect_authority" not in serialized
    assert "delete_authority" not in serialized
    assert "DELETE" not in serialized
