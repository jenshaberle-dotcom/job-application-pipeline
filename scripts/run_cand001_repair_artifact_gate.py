"""Plan or apply CAND-001 from one strictly validated repair artifact.

This path prevents a successful origin search from being repeated merely to move
its already validated result into the persistence review gate. The artifact is
not trusted implicitly: schema, age, company identity, selected state, URL,
boundary and anti-repeat evidence are checked before a persistence plan is built.
Default execution is a dry-run and rolls the database transaction back.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from scripts.run_cand001_validated_origin_url_persistence_gate import (
    DEFAULT_OUTPUT_DIR,
    connect,
    duplicate_selected_url_exists,
    load_candidate,
    write_review_and_candidate_url,
)
from scripts.run_origin_source_discovery_agent import load_local_env_file
from src.search_intelligence.cand001_validated_origin_url_persistence import (
    build_persistence_plan_item,
    evidence_from_origin_discovery_payload,
    markdown_report,
    report_payload,
)
from src.search_intelligence.origin_repair_artifact import (
    ArtifactValidationError,
    load_validated_repair_payload,
)


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    items = []
    artifact_sources: list[dict[str, object]] = []

    with connect() as conn:
        for company_key in args.company_key:
            try:
                discovery_payload = load_validated_repair_payload(
                    args.repair_artifact,
                    company_key=company_key,
                    max_age_hours=args.max_artifact_age_hours,
                )
            except ArtifactValidationError as exc:
                raise SystemExit(
                    f"Repair artifact validation failed for {company_key}: {exc}"
                ) from exc

            candidate = load_candidate(conn, company_key)
            artifact_company_name = str(
                discovery_payload.get("company_name") or ""
            ).strip()
            if artifact_company_name != candidate.company_name:
                raise SystemExit(
                    "Repair artifact company_name does not match current candidate "
                    f"for {company_key}: artifact={artifact_company_name!r} "
                    f"database={candidate.company_name!r}"
                )

            evidence = replace(
                evidence_from_origin_discovery_payload(discovery_payload),
                source="validated_repair_artifact",
            )
            duplicate_exists = duplicate_selected_url_exists(
                conn,
                candidate=candidate,
                selected_url=evidence.selected_url,
            )
            planned = build_persistence_plan_item(
                candidate,
                evidence,
                include_active_controlled=args.include_active_controlled,
                duplicate_selected_url_exists=duplicate_exists,
            )

            if args.apply and planned.apply_allowed:
                review_id = write_review_and_candidate_url(
                    conn,
                    item=planned,
                    evidence=evidence,
                    reviewed_by=args.reviewed_by,
                )
                planned = build_persistence_plan_item(
                    candidate,
                    evidence,
                    include_active_controlled=args.include_active_controlled,
                    duplicate_selected_url_exists=duplicate_exists,
                    applied=True,
                    audit_review_id=review_id,
                )
                print(
                    "candidate_url_applied_from_artifact: "
                    f"company_key={company_key} "
                    f"url={planned.selected_url} review_id={review_id}"
                )
            else:
                print(
                    "candidate_url_artifact_plan: "
                    f"company_key={company_key} decision={planned.decision} "
                    f"status={planned.review_status} "
                    f"selected_url={planned.selected_url or '<none>'} "
                    f"apply_allowed={planned.apply_allowed} provider_rerun=False"
                )

            provenance = discovery_payload.get("artifact_reuse")
            if isinstance(provenance, dict):
                artifact_sources.append(dict(provenance))
            items.append(planned)

        if args.apply:
            conn.commit()
        else:
            conn.rollback()

    payload = report_payload(
        benchmark_label=args.benchmark_label,
        items=items,
    )
    payload["validated_repair_artifact_reuse"] = True
    payload["provider_rerun"] = False
    payload["repair_artifact"] = str(args.repair_artifact.resolve())
    payload["artifact_sources"] = artifact_sources
    payload["boundary_extension"] = {
        "artifact_schema_validated": True,
        "artifact_age_validated": True,
        "artifact_company_identity_validated": True,
        "artifact_selected_state_validated": True,
        "artifact_boundary_validated": True,
        "explicit_apply_required": True,
        "default_dry_run_rolls_back": True,
        "provider_rerun": False,
    }

    json_path = args.output_json or output_dir / f"{args.benchmark_label}.json"
    md_path = args.output_markdown or output_dir / f"{args.benchmark_label}.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_text = markdown_report(payload)
    md_text += (
        "\n## Validated Repair Artifact Reuse\n\n"
        f"- Artifact: `{args.repair_artifact.resolve()}`\n"
        "- Provider rerun: no\n"
        f"- Maximum accepted age: {args.max_artifact_age_hours:g} hours\n"
        f"- Apply requested: {'yes' if args.apply else 'no'}\n"
    )
    md_path.write_text(md_text, encoding="utf-8")
    print("json_report_written: " + str(json_path))
    print("markdown_report_written: " + str(md_path))
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CAND-001 plan/apply from a validated origin-repair artifact."
    )
    parser.add_argument("--benchmark-label", required=True)
    parser.add_argument("--repair-artifact", type=Path, required=True)
    parser.add_argument("--company-key", action="append", required=True)
    parser.add_argument("--max-artifact-age-hours", type=float, default=24.0)
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--include-active-controlled", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser


def main() -> None:
    load_local_env_file()
    args = build_parser().parse_args()
    if args.max_artifact_age_hours <= 0:
        raise SystemExit("--max-artifact-age-hours must be positive")
    run(args)


if __name__ == "__main__":
    main()
