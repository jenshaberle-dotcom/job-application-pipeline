"""Deterministically revalidate one freshly proposed URL before CAND-001 Apply.

This adapter exists for the two-phase portfolio flow authorized by Pipeline #514:

1. the canonical origin cascade discovers a candidate URL in a dry-run;
2. Apply does **not** rerun stochastic model/search discovery;
3. the exact proposed URL is treated as untrusted input, fetched again through the
   stable default origin contracts with LLM and Tavily hard-disabled;
4. the stable path must select that exact normalized URL again and CAND-001 must
   still classify it A/B-tier before the existing exact-row `FOR UPDATE` writer
   may persist it.

The adapter never turns a prior model result into persistence truth.  It only
removes nondeterministic rediscovery from the Apply phase while retaining fresh
HTTP/company-identity/career-origin validation, duplicate checks, exact candidate
identity checks, and the existing CAND-001 audit/write boundary.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scripts import run_cand001_validated_origin_url_persistence_gate as cand001
from scripts import run_origin_url_default_repair as default_repair
from scripts.run_origin_source_discovery_agent import load_local_env_file
from src.search_intelligence.cand001_validated_origin_url_persistence import (
    OriginUrlValidationEvidence,
    build_persistence_plan_item,
    evidence_from_origin_discovery_payload,
    markdown_report,
    normalize_url,
    report_payload,
)

DEFAULT_OUTPUT_DIR = Path("exports/cand001_proposed_url_revalidation_apply")
PROVENANCE = "fresh_proposed_url_revalidation"


def build_parser() -> argparse.ArgumentParser:
    parser = cand001.build_parser()
    parser.description = (
        "CAND-001 exact proposed-URL revalidation and persistence without "
        "stochastic rediscovery."
    )
    parser.add_argument("--candidate-id", type=int, required=True)
    parser.add_argument("--proposed-url", required=True)
    return parser


def _origin_args(args: argparse.Namespace) -> SimpleNamespace:
    origin_args = cand001.origin_args_from_cli(args)
    # `operator_url` is used only as the stable controller's direct URL input.
    # Authority remains deterministic validation; provenance is overwritten below
    # to make clear this is a prior discovery proposal, not an operator assertion.
    origin_args.operator_url = [args.proposed_url]
    origin_args.disable_llm = True
    origin_args.disable_tavily = True
    origin_args.search_provider = ["none"]
    return origin_args


def _exact_revalidation_evidence(
    payload: dict[str, Any],
    *,
    proposed_url: str,
) -> OriginUrlValidationEvidence:
    evidence = evidence_from_origin_discovery_payload(payload)
    evidence = replace(evidence, source=PROVENANCE)
    if normalize_url(evidence.selected_url) == normalize_url(proposed_url):
        return evidence
    selected = evidence.selected_url or "<none>"
    return replace(
        evidence,
        selected_url=None,
        decision="proposed_url_revalidation_failed",
        confidence_score=0.0,
        url_finder_tier=None,
        reason=(
            "Fresh stable validation did not reselect the exact proposed URL; "
            f"proposed={proposed_url!r}, selected={selected!r}. No alternate URL "
            "may be substituted during CAND-001 Apply."
        ),
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    if len(args.company_key) != 1:
        raise SystemExit(
            "Proposed-URL revalidation requires exactly one --company-key per run."
        )
    proposed_url = str(args.proposed_url or "").strip()
    if not proposed_url:
        raise SystemExit("--proposed-url must not be empty")
    company_key = str(args.company_key[0])
    output_dir = DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    with cand001.connect() as conn:
        candidate = cand001.load_candidate(
            conn,
            company_key,
            candidate_id=int(args.candidate_id),
        )
        payload = default_repair.run_default_repair_for_company(
            _origin_args(args),
            company_key,
        )
        evidence = _exact_revalidation_evidence(
            payload,
            proposed_url=proposed_url,
        )
        duplicate_exists = cand001.duplicate_selected_url_exists(
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
            review_id = cand001.write_review_and_candidate_url(
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
            conn.commit()
            print(
                "candidate_proposed_url_applied: "
                f"candidate_id={planned.candidate_id} company_key={company_key} "
                f"url={planned.selected_url} review_id={review_id}"
            )
        else:
            conn.rollback()
            repair = payload.get("default_repair")
            repair_state = (
                repair.get("final_state")
                if isinstance(repair, dict)
                else "proposed_url_revalidation"
            )
            print(
                "candidate_proposed_url_plan: "
                f"candidate_id={candidate.candidate_id} company_key={company_key} "
                f"decision={planned.decision} status={planned.review_status} "
                f"selected_url={planned.selected_url or '<none>'} "
                f"apply_allowed={planned.apply_allowed} repair_state={repair_state}"
            )

    result = report_payload(
        benchmark_label=args.benchmark_label,
        items=[planned],
    )
    result["proposed_url_revalidation"] = {
        "proposed_url": proposed_url,
        "provenance": PROVENANCE,
        "llm_disabled": True,
        "tavily_disabled": True,
        "exact_url_reselection_required": True,
        "alternate_url_substitution_allowed": False,
    }
    json_path = args.output_json or output_dir / f"{args.benchmark_label}.json"
    md_path = args.output_markdown or output_dir / f"{args.benchmark_label}.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    md_path.write_text(markdown_report(result), encoding="utf-8")
    print("json_report_written: " + str(json_path))
    print("markdown_report_written: " + str(md_path))
    return result


def main() -> None:
    load_local_env_file()
    args = build_parser().parse_args()
    if args.single_pass_diagnostic:
        raise SystemExit(
            "Proposed-URL Apply always uses the stable default validation path; "
            "--single-pass-diagnostic is forbidden."
        )
    if args.no_probe:
        raise SystemExit("Proposed-URL revalidation requires fresh HTTP probing.")
    run(args)


if __name__ == "__main__":
    main()
