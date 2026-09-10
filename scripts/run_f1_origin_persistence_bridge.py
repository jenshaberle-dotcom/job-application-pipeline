"""Bridge F1 origin-jobspace discovery into the canonical candidate URL writer.

F1 discovery remains evidence-only.  This adapter turns a strong F1 selection into
an offline search-result replay for CAND-001, which independently revalidates the
URL before any candidate_url mutation.  CAND-001 remains the sole URL writer.

Dry-run is the default.  Apply requires the existing exact approval token and the
candidate identity loaded from the same DB-backed F1 discovery result.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scripts.run_cand001_validated_origin_url_persistence_gate import run as run_cand001
from scripts.run_origin_source_discovery_agent import run_for_company as run_f1_discovery
from src.search_intelligence.product_e2e_origin_url_bridge import APPROVAL_TOKEN

SCHEMA_VERSION = "f1.origin_persistence_bridge.v1"
BOUNDARY = {
    "f1_discovery_is_evidence_only": True,
    "cand001_is_sole_candidate_url_writer": True,
    "cand001_revalidates_selected_url": True,
    "dry_run_default": True,
    "exact_approval_token_required_for_apply": True,
    "no_source_activation": True,
    "no_bronze_silver_gold_write": True,
    "no_scheduler_mutation": True,
}


def _f1_args(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        market_evidence_limit=args.market_evidence_limit,
        target_location=args.target_location,
        search_results_json=None,
        search_provider=[args.search_provider],
        search_query_limit=args.search_query_limit,
        search_max_results=args.search_max_results,
        search_timeout_seconds=args.timeout_seconds,
        search_depth="basic",
        official_domain_url=[],
        official_domain_provider=args.official_domain_provider,
        official_domain_timeout_seconds=args.timeout_seconds,
        no_probe=False,
        no_surface_expansion=False,
        timeout_seconds=args.timeout_seconds,
        http_request_cap=args.http_request_cap,
        max_candidates=args.max_candidates,
        reviewed_by=args.reviewed_by,
    )


def build_cand001_replay(
    *,
    company_key: str,
    company_name: str,
    selected_url: str,
) -> list[dict[str, str]]:
    """Represent the F1 selection as replay evidence, never as writer authority."""

    return [
        {
            "company_key": company_key,
            "url": selected_url,
            "title": f"{company_name} careers",
            "snippet": (
                "F1 bounded official-domain/career-surface discovery selected this "
                "URL; CAND-001 must independently revalidate it before persistence."
            ),
            "query": "f1-origin-jobspace-replay",
            "provider": "f1_jobspace_bridge",
        }
    ]


def _cand001_args(
    args: argparse.Namespace,
    *,
    company_key: str,
    candidate_id: int,
    replay_path: Path,
    run_dir: Path,
) -> SimpleNamespace:
    return SimpleNamespace(
        benchmark_label=f"f1_origin_persistence_bridge_{run_dir.name}",
        company_key=[company_key],
        candidate_id_by_company_key={company_key: candidate_id},
        target_location=args.target_location,
        target_locale="de",
        reviewed_by=args.reviewed_by,
        apply=args.apply,
        include_active_controlled=False,
        timeout_seconds=args.timeout_seconds,
        max_url_candidates=args.max_candidates,
        market_evidence_limit=args.market_evidence_limit,
        search_provider=["none"],
        search_query_limit=0,
        search_max_results=1,
        search_timeout_seconds=args.timeout_seconds,
        search_depth="basic",
        search_results_json=replay_path,
        no_probe=False,
        max_evidence_candidates=4,
        max_evidence_http_requests=12,
        evidence_timeout_seconds=args.timeout_seconds,
        max_response_bytes=750_000,
        llm_model="disabled",
        llm_reasoning_effort="low",
        llm_max_output_tokens=1,
        llm_reserved_input_tokens=1,
        llm_timeout_seconds=1.0,
        max_estimated_llm_cost_usd_per_company=0.0,
        disable_tavily=True,
        disable_llm=True,
        single_pass_diagnostic=False,
        output_json=run_dir / f"cand001_{company_key}.json",
        output_markdown=run_dir / f"cand001_{company_key}.md",
    )


def _cand_outcome(payload: dict[str, Any], candidate_id: int) -> dict[str, object] | None:
    return next(
        (
            dict(item)
            for item in payload.get("items", [])
            if isinstance(item, dict)
            and int(item.get("candidate_id") or -1) == candidate_id
        ),
        None,
    )


def run(args: argparse.Namespace) -> int:
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit(f"--apply requires --approval-token {APPROVAL_TOKEN}")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = args.output_dir / f"f1_origin_persistence_bridge_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)

    outcomes: list[dict[str, object]] = []
    for company_key in tuple(dict.fromkeys(args.company_key)):
        f1 = run_f1_discovery(_f1_args(args), company_key)
        candidate_id = int(f1["candidate_id"])
        company_name = str(f1.get("company_name") or company_key)
        decision = str(f1.get("decision") or "")
        selected_url = str(f1.get("selected_url") or "").strip()

        outcome: dict[str, object] = {
            "candidate_id": candidate_id,
            "company_key": company_key,
            "company_name": company_name,
            "f1_decision": decision,
            "f1_selected_url": selected_url or None,
            "f1_confidence_score": f1.get("confidence_score"),
            "f1_selected_domain": f1.get("selected_domain"),
            "f1_ats_families": f1.get("f1_ats_families", []),
            "f1_official_domain_evidence_count": f1.get(
                "f1_official_domain_evidence_count", 0
            ),
            "status": "discovery_stop",
            "cand001": None,
        }

        if decision != "origin_url_candidate_selected" or not selected_url:
            outcomes.append(outcome)
            continue

        replay_path = run_dir / f"f1_replay_{candidate_id}_{company_key}.json"
        replay_path.write_text(
            json.dumps(
                build_cand001_replay(
                    company_key=company_key,
                    company_name=company_name,
                    selected_url=selected_url,
                ),
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        cand_payload = run_cand001(
            _cand001_args(
                args,
                company_key=company_key,
                candidate_id=candidate_id,
                replay_path=replay_path,
                run_dir=run_dir,
            )
        )
        cand_item = _cand_outcome(cand_payload, candidate_id)
        outcome["cand001"] = cand_item
        if cand_item is None:
            outcome["status"] = "cand001_missing_outcome"
        elif cand_item.get("applied"):
            outcome["status"] = "persisted"
        elif cand_item.get("decision") == "persist_validated_candidate_url":
            outcome["status"] = "validated_ready_for_apply"
        elif cand_item.get("decision") == "no_action_already_persisted":
            outcome["status"] = "already_persisted"
        else:
            outcome["status"] = "cand001_stop"
        outcomes.append(outcome)

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "boundary": BOUNDARY,
        "outcomes": outcomes,
        "summary": {
            "company_count": len(outcomes),
            "f1_selected_count": sum(
                1 for item in outcomes if item["f1_decision"] == "origin_url_candidate_selected"
            ),
            "persisted_or_ready_count": sum(
                1
                for item in outcomes
                if item["status"]
                in {"persisted", "already_persisted", "validated_ready_for_apply"}
            ),
            "status_counts": {
                status: sum(1 for item in outcomes if item["status"] == status)
                for status in sorted({str(item["status"]) for item in outcomes})
            },
        },
    }
    report_path = run_dir / "result.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("F1 origin persistence bridge")
    print(f"mode: {report['mode']}")
    print(f"companies: {report['summary']['company_count']}")
    print(f"f1_selected: {report['summary']['f1_selected_count']}")
    print(f"persisted_or_ready: {report['summary']['persisted_or_ready_count']}")
    for item in outcomes:
        print(
            "case: "
            f"candidate_id={item['candidate_id']} | company={item['company_key']} | "
            f"f1={item['f1_decision']} | status={item['status']} | "
            f"url={item['f1_selected_url'] or '<none>'}"
        )
    print(f"artifact_json: {report_path}")
    print("F1_ORIGIN_PERSISTENCE_BRIDGE=PASS")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bridge strong F1 jobspace discovery through the canonical CAND-001 URL writer."
    )
    parser.add_argument("--company-key", action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--http-request-cap", type=int, default=48)
    parser.add_argument("--max-candidates", type=int, default=30)
    parser.add_argument("--market-evidence-limit", type=int, default=20)
    parser.add_argument(
        "--official-domain-provider",
        choices=("none", "wikidata"),
        default="wikidata",
    )
    parser.add_argument(
        "--search-provider",
        choices=("none", "tavily"),
        default="none",
    )
    parser.add_argument("--search-query-limit", type=int, default=4)
    parser.add_argument("--search-max-results", type=int, default=5)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
