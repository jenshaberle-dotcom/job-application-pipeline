from __future__ import annotations

import argparse
from pathlib import Path

from src.search_intelligence.candidate_fact_authoring_pack import (
    OVERWRITE_TOKEN,
    write_candidate_fact_authoring_pack,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a local private Candidate Fact authoring pack without inferring "
            "candidate facts, reading the database or performing an import."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home()
        / "projects"
        / "job-application-pipeline"
        / "private_candidate_facts",
    )
    parser.add_argument("--profile-version", required=True)
    parser.add_argument(
        "--overwrite-token",
        help=(
            "Exact token required only when replacing existing private pack files: "
            f"{OVERWRITE_TOKEN}"
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        pack = write_candidate_fact_authoring_pack(
            output_dir=args.output_dir,
            profile_version=args.profile_version,
            overwrite_token=args.overwrite_token,
        )
    except (ValueError, FileExistsError) as exc:
        raise SystemExit(str(exc)) from exc

    print("Private Candidate Fact authoring pack")
    print("mode: local_private_authoring_scaffold")
    print(f"profile_version: {pack.profile_version}")
    print(f"statement_count: {pack.statement_count}")
    print(f"unique_tag_count: {pack.unique_tag_count}")
    print("draft_profile_status: draft")
    print("draft_fact_count: 0")
    print("candidate_fact_statements_generated: 0")
    print("provenance_references_generated: 0")
    print("capability_claims_inferred: 0")
    print("database_reads: 0")
    print("database_writes: 0")
    print("candidate_fact_import_performed: false")
    print("candidate_fact_approval_performed: false")
    print("capability_fit_decision_created: false")
    print(f"profile: {pack.profile_path}")
    print(f"workbook: {pack.workbook_path}")
    print(f"readme: {pack.readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
