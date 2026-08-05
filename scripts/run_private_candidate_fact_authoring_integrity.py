from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping

from src.search_intelligence.candidate_fact_authoring_integrity import (
    REPORT_SCHEMA,
    CandidateFactAuthoringIntegrity,
    validate_candidate_fact_authoring_integrity,
)
from src.search_intelligence.candidate_fact_authoring_pack import (
    PROFILE_FILENAME,
    WORKBOOK_FILENAME,
)


def write_report(
    *,
    output_dir: Path,
    integrity: CandidateFactAuthoringIntegrity,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"candidate_fact_authoring_integrity_{stamp}.json"
    payload: Mapping[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "review_output_only_not_pipeline_input": True,
        "mode": "local_read_only",
        "integrity": integrity.canonical_payload(),
        "redaction": {
            "personal_statements_emitted": False,
            "provenance_references_emitted": False,
            "capability_tag_values_emitted": False,
            "candidate_fact_keys_emitted": False,
            "private_notes_emitted": False,
        },
        "boundaries": {
            "file_writes_except_report": 0,
            "database_reads": 0,
            "database_writes": 0,
            "candidate_fact_import_performed": False,
            "candidate_fact_approval_performed": False,
            "semantic_requirement_comparison_created": False,
            "capability_fit_decision_created": False,
            "assessment_mutation": False,
            "readiness_mutation": False,
            "ranking_scores_created": False,
            "network_requests": 0,
            "provider_requests": 0,
            "source_or_scheduler_activation": False,
            "application_action_performed": False,
        },
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the local private Candidate Fact profile and E.ON authoring "
            "workbook together without deciding semantic fit."
        )
    )
    private_dir = Path("private_candidate_facts")
    parser.add_argument(
        "--profile",
        type=Path,
        default=private_dir / PROFILE_FILENAME,
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        default=private_dir / WORKBOOK_FILENAME,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.profile.is_file():
        raise SystemExit("private Candidate Fact profile does not exist")
    if not args.workbook.is_file():
        raise SystemExit("private E.ON authoring workbook does not exist")

    integrity = validate_candidate_fact_authoring_integrity(
        profile_json=args.profile.read_text(encoding="utf-8"),
        workbook_json=args.workbook.read_text(encoding="utf-8"),
    )
    report_path = write_report(output_dir=args.output_dir, integrity=integrity)

    print("Private Candidate Fact authoring integrity")
    print("mode: local_read_only")
    print(f"integrity_key: {integrity.integrity_key}")
    print(f"profile_version: {integrity.profile_version}")
    print(f"profile_status: {integrity.profile_status}")
    print(f"profile_payload_sha256: {integrity.profile_payload_sha256}")
    print(f"workbook_sha256: {integrity.workbook_sha256}")
    print(f"profile_fact_count: {integrity.profile_fact_count}")
    print(f"requirement_count: {integrity.requirement_count}")
    print(f"unique_employer_tag_count: {integrity.unique_employer_tag_count}")
    print(
        "decision_counts: "
        + ",".join(
            f"{key}={value}" for key, value in integrity.decision_counts.items()
        )
    )
    print(
        "distinct_referenced_fact_count: "
        f"{integrity.distinct_referenced_fact_count}"
    )
    print(f"all_references_exist: {str(integrity.all_references_exist).lower()}")
    print(f"authoring_complete: {str(integrity.authoring_complete).lower()}")
    print(
        "blockers: "
        + (",".join(integrity.blockers) if integrity.blockers else "none")
    )
    print("personal_statements_emitted: false")
    print("provenance_references_emitted: false")
    print("capability_tag_values_emitted: false")
    print("candidate_fact_keys_emitted: false")
    print("database_reads: 0")
    print("database_writes: 0")
    print("semantic_requirement_comparison_created: false")
    print("capability_fit_decision_created: false")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
