"""Run bounded primary-to-escalation LLM review on eligible origin decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping

from src.search_intelligence.origin_llm_model_campaign import (
    MODEL_PRICES_USD_PER_MILLION,
    adjudicate_with_escalation,
)
from src.search_intelligence.origin_source_evidence import (
    OriginEvidenceAssessment,
    OriginEvidenceDecision,
)

SCHEMA_VERSION = "origin_llm_escalation.v1"
BOUNDARY = (
    "immutable_origin_evidence_input_only",
    "maximum_two_provider_attempts_per_case",
    "provider_candidate_ids_only",
    "provider_review_signal_only",
    "provider_disagreement_requires_manual_review",
    "no_pipeline_mutation",
)


def _decision_from_json(payload: Mapping[str, object]) -> OriginEvidenceDecision:
    assessments = tuple(
        OriginEvidenceAssessment(
            **{
                **dict(item),
                "sample_job_urls": tuple(item.get("sample_job_urls") or ()),
                "reasons": tuple(item.get("reasons") or ()),
            }
        )
        for item in payload.get("assessments", [])
        if isinstance(item, Mapping)
    )
    return OriginEvidenceDecision(
        company_key=str(payload["company_key"]),
        company_name=str(payload["company_name"]),
        deterministic_decision=str(payload["deterministic_decision"]),
        selected_candidate_id=(
            None
            if payload.get("selected_candidate_id") is None
            else str(payload["selected_candidate_id"])
        ),
        selected_url=(
            None if payload.get("selected_url") is None else str(payload["selected_url"])
        ),
        confidence_score=float(payload["confidence_score"]),
        confidence_band=str(payload["confidence_band"]),
        selection_margin=float(payload["selection_margin"]),
        manual_review_required=bool(payload["manual_review_required"]),
        adjudication_reasons=tuple(payload.get("adjudication_reasons") or ()),
        assessments=assessments,
    )


def _write(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bounded origin LLM escalation.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--primary-model", required=True)
    parser.add_argument("--escalation-model", required=True)
    parser.add_argument("--max-primary-requests", type=int, default=2)
    parser.add_argument("--max-escalation-requests", type=int, default=2)
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--max-output-tokens", type=int, default=600)
    parser.add_argument("--reserved-input-tokens", type=int, default=5000)
    parser.add_argument("--max-estimated-cost-usd", type=float, default=0.15)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--openai-api-key", default=os.getenv("OPENAI_API_KEY", ""))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not str(args.openai_api_key or "").strip():
        raise SystemExit("OPENAI_API_KEY is required for LLM escalation")
    if args.max_primary_requests < 0 or args.max_escalation_requests < 0:
        raise SystemExit("request ceilings must not be negative")
    reserved_cost = 0.0
    for model, count in (
        (args.primary_model, args.max_primary_requests),
        (args.escalation_model, args.max_escalation_requests),
    ):
        prices = MODEL_PRICES_USD_PER_MILLION.get(model)
        if prices is None:
            raise SystemExit(f"missing price reservation for model {model}")
        input_price, output_price = prices
        reserved_cost += count * (
            args.reserved_input_tokens * input_price / 1_000_000
            + args.max_output_tokens * output_price / 1_000_000
        )
    if reserved_cost > args.max_estimated_cost_usd:
        raise SystemExit(
            "pessimistic escalation reservation exceeds cost ceiling: "
            f"reserved={reserved_cost:.6f} ceiling={args.max_estimated_cost_usd:.6f}"
        )
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or not isinstance(payload.get("results"), list):
        raise SystemExit("invalid origin evidence report")

    runs = []
    primary_attempts = 0
    escalation_attempts = 0
    for raw in payload["results"]:
        if not isinstance(raw, Mapping) or not bool(raw.get("llm_eligible")):
            continue
        if primary_attempts >= args.max_primary_requests:
            break
        decision = _decision_from_json(raw)
        run = adjudicate_with_escalation(
            decision,
            api_key=args.openai_api_key,
            primary_model=args.primary_model,
            escalation_model=(
                args.escalation_model
                if escalation_attempts < args.max_escalation_requests
                else ""
            ),
            reasoning_effort=args.reasoning_effort,
            max_output_tokens=args.max_output_tokens,
            timeout_seconds=args.timeout_seconds,
        )
        primary_attempts += int(run.primary.result.request_attempted)
        if run.escalation is not None:
            escalation_attempts += int(run.escalation.result.request_attempted)
        runs.append(run.to_json())

    output = {
        "schema_version": SCHEMA_VERSION,
        "source_evidence_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "review_output_only_not_pipeline_input": True,
        "boundary": list(BOUNDARY),
        "config": {
            "primary_model": args.primary_model,
            "escalation_model": args.escalation_model,
            "max_primary_requests": args.max_primary_requests,
            "max_escalation_requests": args.max_escalation_requests,
            "reasoning_effort": args.reasoning_effort,
            "max_output_tokens": args.max_output_tokens,
            "reserved_input_tokens": args.reserved_input_tokens,
            "max_estimated_cost_usd": args.max_estimated_cost_usd,
            "pessimistic_reserved_cost_usd": round(reserved_cost, 8),
        },
        "summary": {
            "eligible_case_count": sum(
                isinstance(item, Mapping) and bool(item.get("llm_eligible"))
                for item in payload["results"]
            ),
            "processed_case_count": len(runs),
            "primary_request_attempts": primary_attempts,
            "escalation_request_attempts": escalation_attempts,
            "provider_disagreement_count": sum(
                item["outcome"] == "provider_disagreement_manual_review_required"
                for item in runs
            ),
        },
        "results": runs,
    }
    _write(args.output, output)
    print(
        "origin_llm_escalation_complete: "
        f"cases={len(runs)} primary={primary_attempts} "
        f"escalation={escalation_attempts} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
