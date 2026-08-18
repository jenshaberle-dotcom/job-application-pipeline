"""Run one bounded Product V1 AI-booster campaign from authoritative read truth.

The runner reuses the Product V1 downstream-preview runtime boundary: exactly one
DB-backed employer-origin job must already be validated and active, and exactly
one current public HTTPS detail page is fetched without persisting raw HTML.
Deterministic Assessment and Ranking evidence always run first.

Provider execution is opt-in. Before any model callback can be constructed, the
runner computes the canonical Product V1 replay fingerprint for the exact
unresolved scope. A caller-supplied previous terminal fingerprint suppresses an
unchanged campaign completely. No cache/database/product write path exists here.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path

from scripts.product_v1_downstream_preview_runtime import (
    DownstreamEvidenceMaterialization,
    load_downstream_evidence_materialization,
)
from scripts.run_origin_source_discovery_agent import load_local_env_file
from src.search_intelligence.product_v1_assessment_booster import (
    AssessmentHypothesisObservation,
    ProductV1AssessmentBoosterExecution,
    execute_product_v1_assessment_booster,
    openai_assessment_model_callback,
)
from src.search_intelligence.product_v1_assessment_evidence import (
    ProductV1AssessmentEvidence,
    extract_product_v1_assessment_evidence,
)
from src.search_intelligence.product_v1_booster_replay import (
    assessment_booster_input,
    ranking_booster_input,
)
from src.search_intelligence.product_v1_ranking_booster import (
    ProductV1RankingBoosterExecution,
    RankingHypothesisObservation,
    execute_product_v1_ranking_booster,
    openai_ranking_model_callback,
)
from src.search_intelligence.product_v1_ranking_evidence import (
    ProductV1RankingEvidence,
    build_product_v1_ranking_evidence,
)

SCHEMA_VERSION = "product_v1.ai_booster_campaign.v1"
SURFACES = ("assessment", "ranking")


def _missing_secret(value: str | None) -> bool:
    text = str(value or "").strip()
    lowered = text.casefold()
    return (
        not text
        or text == "..."
        or text in {"<YOUR_API_KEY>", "YOUR_API_KEY", "changeme"}
        or "your_api_key" in lowered
        or "realer_key" in lowered
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one replay-safe Product V1 Assessment or Ranking AI-booster campaign."
    )
    parser.add_argument("--silver-job-id", type=int, required=True)
    parser.add_argument("--surface", choices=SURFACES, required=True)
    parser.add_argument(
        "--previous-terminal-fingerprint",
        action="append",
        default=[],
        help=(
            "Repeat only for a previous terminal reusable result. An exact match "
            "suppresses provider execution for unchanged input/scope."
        ),
    )
    parser.add_argument(
        "--execute-provider-booster",
        action="store_true",
        help="Opt in to the existing bounded Luna -> Terra -> Sol -> Luna-max cascade.",
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if int(args.silver_job_id) <= 0:
        raise SystemExit("--silver-job-id must be positive")
    if str(args.surface) not in SURFACES:
        raise SystemExit("unsupported Product V1 booster surface")


def _materialize_deterministic_evidence(
    materialization: DownstreamEvidenceMaterialization,
) -> tuple[ProductV1AssessmentEvidence, ProductV1RankingEvidence, str, str]:
    row = materialization.row
    title = str(row.get("title") or materialization.fetched_title or "").strip()
    if not title:
        raise ValueError("Product V1 campaign target title is missing")
    company_name = str(row.get("company_name") or "").strip()
    assessment = extract_product_v1_assessment_evidence(
        description=materialization.detail_text,
        title=title,
        source_url=materialization.final_url,
    )
    ranking = build_product_v1_ranking_evidence(
        title=title,
        description=materialization.detail_text,
        origin_validation_status="validated",
        activity_status="active",
        assessment_evidence=assessment,
    )
    return assessment, ranking, title, company_name


def _assessment_scope(
    evidence: ProductV1AssessmentEvidence,
) -> tuple[str, ...]:
    """Ask the existing executor for its exact unresolved scope with zero provider work."""

    def blocked(_stage, _requested):  # type: ignore[no-untyped-def]
        return AssessmentHypothesisObservation(
            status="failed_closed",
            request_attempted=False,
            field_values={},
            evidence_references=(),
            rationale="campaign_replay_preflight_only",
        )

    probe = execute_product_v1_assessment_booster(
        deterministic_evidence=evidence,
        model=blocked,
    )
    if probe.provider_requests != 0 or probe.llm_requests != 0:
        raise RuntimeError("assessment replay preflight attempted a provider request")
    return probe.requested_fields


def _ranking_scope(
    evidence: ProductV1RankingEvidence,
) -> tuple[str, ...]:
    """Ask the existing executor for its exact unresolved scope with zero provider work."""

    def blocked(_stage, _requested):  # type: ignore[no-untyped-def]
        return RankingHypothesisObservation(
            status="failed_closed",
            request_attempted=False,
            references=(),
            rationale="campaign_replay_preflight_only",
        )

    probe = execute_product_v1_ranking_booster(
        deterministic_evidence=evidence,
        model=blocked,
    )
    if probe.provider_requests != 0 or probe.llm_requests != 0:
        raise RuntimeError("ranking replay preflight attempted a provider request")
    return probe.requested_factors


def _failed_closed(execution: object) -> bool:
    stages = getattr(execution, "stages", ())
    return any(str(getattr(stage, "status", "")) == "failed_closed" for stage in stages)


def _execution_outcome(
    execution: ProductV1AssessmentBoosterExecution | ProductV1RankingBoosterExecution,
) -> tuple[str, bool]:
    if _failed_closed(execution):
        return "provider_or_validation_failed_closed", False
    if isinstance(execution, ProductV1AssessmentBoosterExecution):
        unresolved = execution.unresolved_fields
    else:
        unresolved = execution.unresolved_factors
    if unresolved:
        return "terminal_residual_unresolved", True
    return "booster_resolved", True


def _base_payload(
    *,
    args: argparse.Namespace,
    materialization: DownstreamEvidenceMaterialization,
    title: str,
    company_name: str,
) -> dict[str, object]:
    row = materialization.row
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "surface": str(args.surface),
        "target": {
            "silver_job_id": int(row.get("silver_job_id") or args.silver_job_id),
            "title": title,
            "company_name": company_name,
            "source_url": row.get("source_url"),
            "final_url": materialization.final_url,
            "canonical_source_type": row.get("canonical_source_type"),
            "origin_validation_status": row.get("origin_validation_status"),
            "activity_status": row.get("activity_status"),
            "raw_html_persisted": False,
        },
        "provider_execution_requested": bool(args.execute_provider_booster),
        "provider_requests": 0,
        "llm_requests": 0,
        "estimated_model_cost_usd": 0.0,
        "database_writes": 0,
        "gate_writes": 0,
        "lifecycle_writes": 0,
        "hard_filter_writes": 0,
        "ranking_writes": 0,
        "top5_writes": 0,
        "application_writes": 0,
        "product_writes": 0,
        "candidate_fact_authority": False,
        "capability_fit_authority": False,
        "hard_filter_authority": False,
        "ranking_authority": False,
        "top5_authority": False,
        "application_authority": False,
        "product_authority": False,
    }


def run(args: argparse.Namespace) -> dict[str, object]:
    _validate_args(args)
    materialization = load_downstream_evidence_materialization(int(args.silver_job_id))
    assessment, ranking, title, company_name = _materialize_deterministic_evidence(
        materialization
    )
    payload = _base_payload(
        args=args,
        materialization=materialization,
        title=title,
        company_name=company_name,
    )

    if args.surface == "assessment":
        deterministic = assessment
        scope = _assessment_scope(assessment)
        booster_input = assessment_booster_input(assessment)
    else:
        deterministic = ranking
        scope = _ranking_scope(ranking)
        booster_input = ranking_booster_input(
            ranking,
            source_identity=materialization.final_url,
        )

    payload["deterministic_evidence"] = deterministic.canonical_payload()
    payload["unresolved_scope"] = list(scope)

    if not scope:
        payload.update(
            {
                "outcome": "deterministic_resolved",
                "replay_preflight": None,
                "terminal_replay_reusable": False,
                "terminal_fingerprint": None,
            }
        )
        return payload

    replay = booster_input.replay_decision(
        unresolved_scope=scope,
        prior_terminal_input_fingerprints=tuple(
            str(item).strip()
            for item in (args.previous_terminal_fingerprint or ())
            if str(item).strip()
        ),
    )
    payload["replay_preflight"] = replay.to_json()

    if replay.replay_suppressed:
        payload.update(
            {
                "outcome": "unchanged_terminal_replay_skipped",
                "terminal_replay_reusable": True,
                "terminal_fingerprint": replay.input_fingerprint,
            }
        )
        return payload

    if not args.execute_provider_booster:
        payload.update(
            {
                "outcome": "provider_execution_disabled",
                "terminal_replay_reusable": False,
                "terminal_fingerprint": None,
            }
        )
        return payload

    api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    if _missing_secret(api_key):
        payload.update(
            {
                "outcome": "provider_configuration_blocked",
                "terminal_replay_reusable": False,
                "terminal_fingerprint": None,
            }
        )
        return payload

    if args.surface == "assessment":
        callback = openai_assessment_model_callback(
            company_name=company_name,
            detail_url=materialization.final_url,
            title=title,
            detail_text=materialization.detail_text,
            api_key=api_key,
        )
        execution: ProductV1AssessmentBoosterExecution | ProductV1RankingBoosterExecution = (
            execute_product_v1_assessment_booster(
                deterministic_evidence=assessment,
                model=callback,
            )
        )
    else:
        callback = openai_ranking_model_callback(
            company_name=company_name,
            detail_url=materialization.final_url,
            title=title,
            detail_text=materialization.detail_text,
            api_key=api_key,
        )
        execution = execute_product_v1_ranking_booster(
            deterministic_evidence=ranking,
            model=callback,
        )

    outcome, terminal_reusable = _execution_outcome(execution)
    payload.update(
        {
            "outcome": outcome,
            "execution": execution.to_json(),
            "provider_requests": execution.provider_requests,
            "llm_requests": execution.llm_requests,
            "estimated_model_cost_usd": round(execution.estimated_model_cost_usd, 8),
            "terminal_replay_reusable": terminal_reusable,
            "terminal_fingerprint": replay.input_fingerprint if terminal_reusable else None,
        }
    )
    return payload


def main() -> int:
    load_local_env_file()
    args = build_parser().parse_args()
    payload = run(args)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
