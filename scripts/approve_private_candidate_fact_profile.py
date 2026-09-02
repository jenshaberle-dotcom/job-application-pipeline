from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping

from src.search_intelligence.candidate_fact_profile import (
    ensure_no_capability_claim_from_direction,
    load_candidate_fact_profile_json,
)


APPROVAL_TOKEN = "CANDIDATE-FACT-PROFILE-APPROVE-001"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def build_approved_payload(
    payload: Mapping[str, Any],
    *,
    approved_by: str,
    approved_at: str,
) -> dict[str, Any]:
    """Promote an explicitly reviewed local draft without inventing facts.

    Every fact must already exist and be ``proposed``. The function changes only
    profile/fact approval metadata and statuses. Statements, capability tags,
    limitations, provenance and validity windows are preserved byte-for-value at
    the JSON data-model level.
    """

    _require(str(payload.get("status") or "") == "draft", "profile must be draft")
    facts_raw = payload.get("facts")
    _require(isinstance(facts_raw, list) and bool(facts_raw), "draft must contain facts")

    facts: list[dict[str, Any]] = []
    for index, raw in enumerate(facts_raw):
        _require(isinstance(raw, Mapping), f"facts[{index}] must be an object")
        _require(
            str(raw.get("approval_status") or "") == "proposed",
            f"facts[{index}] must be proposed before batch approval",
        )
        fact = dict(raw)
        fact["approval_status"] = "approved"
        fact["approved_by"] = approved_by
        fact["approved_at"] = approved_at
        facts.append(fact)

    result = dict(payload)
    result["status"] = "approved"
    result["approved_by"] = approved_by
    result["approved_at"] = approved_at
    result["facts"] = facts

    # Re-parse through the canonical strict contract before anything is written.
    profile = load_candidate_fact_profile_json(
        json.dumps(result, ensure_ascii=False, sort_keys=True)
    )
    ensure_no_capability_claim_from_direction(profile.facts)
    return profile.canonical_payload()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Approve an already-reviewed local Candidate Fact draft without DB, "
            "network or provider access."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approved-by", default="jens")
    parser.add_argument("--approval-token", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.approval_token != APPROVAL_TOKEN:
        raise SystemExit("invalid candidate fact local approval token")
    approved_by = args.approved_by.strip()
    if not approved_by:
        raise SystemExit("approved_by must not be blank")
    if not args.input.is_file():
        raise SystemExit("candidate fact draft input file does not exist")
    if args.output.exists():
        raise SystemExit("approved output already exists; refuse overwrite")

    source = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(source, Mapping):
        raise SystemExit("candidate fact draft root must be an object")
    approved_at = datetime.now(UTC).isoformat()
    approved = build_approved_payload(
        source,
        approved_by=approved_by,
        approved_at=approved_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(approved, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    profile = load_candidate_fact_profile_json(
        json.dumps(approved, ensure_ascii=False, sort_keys=True)
    )
    summary = profile.redacted_summary()
    print("Private Candidate Fact local approval")
    print("mode: local_operator_approval")
    print(f"profile_key: {profile.profile_key}")
    print(f"profile_version: {profile.profile_version}")
    print(f"payload_sha256: {profile.payload_sha256}")
    print(f"fact_count: {summary['fact_count']}")
    print(f"approved_fact_count: {summary['approved_fact_count']}")
    print(
        "capability_evidence_fact_count: "
        f"{summary['capability_evidence_fact_count']}"
    )
    print(
        "production_evidence_fact_count: "
        f"{summary['production_evidence_fact_count']}"
    )
    print("personal_statements_emitted: false")
    print("provenance_references_emitted: false")
    print("database_reads: 0")
    print("database_writes: 0")
    print("network_requests: 0")
    print("provider_requests: 0")
    print("capability_fit_decision_created: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
