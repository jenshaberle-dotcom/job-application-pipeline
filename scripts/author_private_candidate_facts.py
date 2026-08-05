from __future__ import annotations

import argparse
from pathlib import Path

from src.search_intelligence.candidate_fact_authoring_pack import (
    PROFILE_FILENAME,
    WORKBOOK_FILENAME,
)
from src.search_intelligence.candidate_fact_guided_authoring import (
    load_private_authoring_payloads,
    run_guided_authoring_session,
    save_private_authoring_payloads,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Guide the operator through private Candidate Fact authoring without "
            "opening or directly editing JSON files."
        )
    )
    private_dir = Path("private_candidate_facts")
    parser.add_argument(
        "--profile",
        type=Path,
        default=private_dir / PROFILE_FILENAME,
        help="Private candidate_fact_profile.v1 path.",
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        default=private_dir / WORKBOOK_FILENAME,
        help="Private E.ON authoring workbook path.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    profile_payload, workbook_payload, initial_integrity = (
        load_private_authoring_payloads(
            profile_path=args.profile,
            workbook_path=args.workbook,
        )
    )

    print("Private Candidate Fact guided authoring")
    print("mode: local_interactive_operator_authorship")
    print(f"profile_version: {initial_integrity.profile_version}")
    print(f"profile_fact_count: {initial_integrity.profile_fact_count}")
    print(f"requirement_count: {initial_integrity.requirement_count}")
    print(
        "initial_decision_counts: "
        + ",".join(
            f"{key}={value}"
            for key, value in initial_integrity.decision_counts.items()
        )
    )
    print("automatic_personal_fact_extraction_performed: false")
    print("candidate_fact_import_performed: false")
    print("candidate_fact_approval_performed: false")
    print("database_reads: 0")
    print("database_writes: 0")
    print("provider_requests: 0")
    print("semantic_requirement_comparison_created: false")
    print("capability_fit_decision_created: false")
    print()

    session = run_guided_authoring_session(
        profile_payload=profile_payload,
        workbook_payload=workbook_payload,
    )

    if session.quit_without_save or not session.save_confirmed:
        print()
        print("Guided authoring result")
        print("private_files_written: false")
        print("backup_created: false")
        print("candidate_fact_import_performed: false")
        print("candidate_fact_approval_performed: false")
        print("capability_fit_decision_created: false")
        return 0

    if not session.changed:
        print()
        print("Guided authoring result")
        print("private_files_written: false")
        print("backup_created: false")
        print("reason: no_payload_change")
        print("candidate_fact_import_performed: false")
        print("candidate_fact_approval_performed: false")
        print("capability_fit_decision_created: false")
        return 0

    saved = save_private_authoring_payloads(
        profile_path=args.profile,
        workbook_path=args.workbook,
        profile_payload=session.profile_payload,
        workbook_payload=session.workbook_payload,
    )

    summary = session.redacted_summary()
    print()
    print("Guided authoring result")
    print("private_files_written: true")
    print("backup_created: true")
    print(f"backup_dir: {saved.backup_dir}")
    print(f"profile_version: {summary['profile_version']}")
    print(f"profile_fact_count: {summary['profile_fact_count']}")
    print(f"requirement_count: {summary['requirement_count']}")
    print(
        "decision_counts: "
        + ",".join(
            f"{key}={value}" for key, value in summary["decision_counts"].items()
        )
    )
    print(f"authoring_complete: {str(summary['authoring_complete']).lower()}")
    print(
        "blockers: "
        + (",".join(summary["blockers"]) if summary["blockers"] else "none")
    )
    print("personal_statements_emitted_in_summary: false")
    print("provenance_references_emitted_in_summary: false")
    print("capability_tag_values_emitted_in_summary: false")
    print("database_reads: 0")
    print("database_writes: 0")
    print("candidate_fact_import_performed: false")
    print("candidate_fact_approval_performed: false")
    print("semantic_requirement_comparison_created: false")
    print("capability_fit_decision_created: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
