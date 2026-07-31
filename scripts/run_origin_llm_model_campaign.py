"""Run a fixed multi-model origin-adjudication benchmark or bounded escalation path."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

from src.search_intelligence.origin_llm_model_campaign import (
    DEFAULT_BENCHMARK_MODELS,
    MODEL_PRICES_USD_PER_MILLION,
    ModelCallObservation,
    adjudicate_model,
    match_expectation,
    parse_expectations,
    recommend_route,
    score_observation,
    simulate_escalation,
    summarize_models,
)
from src.search_intelligence.origin_source_evidence import (
    OriginEvidenceAssessment,
    OriginEvidenceDecision,
)

REPORT_SCHEMA_VERSION = "origin_llm_model_campaign.v1"
CHECKPOINT_SCHEMA_VERSION = "origin_llm_model_campaign_checkpoint.v1"
BOUNDARY = (
    "immutable_origin_evidence_input_only",
    "same_packet_per_model",
    "strict_structured_output",
    "provider_candidate_ids_only",
    "provider_review_signal_only",
    "no_candidate_url_write",
    "no_connector_registration",
    "no_source_activation",
    "no_bronze_silver_write",
    "no_scheduler_change",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


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


def _observation_from_json(payload: Mapping[str, object]) -> ModelCallObservation:
    from src.search_intelligence.origin_llm_adjudication import (
        LLMAdjudication,
        LLMAdjudicationResult,
    )

    provider = payload["provider_result"]
    if not isinstance(provider, Mapping):
        raise ValueError("checkpoint provider_result must be an object")
    adjudication_raw = provider.get("adjudication")
    adjudication = None
    if isinstance(adjudication_raw, Mapping):
        adjudication = LLMAdjudication(
            decision=str(adjudication_raw["decision"]),
            recommended_candidate_id=(
                None
                if adjudication_raw.get("recommended_candidate_id") is None
                else str(adjudication_raw["recommended_candidate_id"])
            ),
            entity_relationship=str(adjudication_raw["entity_relationship"]),
            origin_assessment=str(adjudication_raw["origin_assessment"]),
            manual_review_required=bool(adjudication_raw["manual_review_required"]),
            evidence_references=tuple(adjudication_raw.get("evidence_references") or ()),
            remaining_uncertainty=tuple(
                adjudication_raw.get("remaining_uncertainty") or ()
            ),
            rationale=str(adjudication_raw["rationale"]),
        )
    result = LLMAdjudicationResult(
        status=str(provider["status"]),
        provider=str(provider["provider"]),
        model=None if provider.get("model") is None else str(provider["model"]),
        request_attempted=bool(provider["request_attempted"]),
        response_id=(
            None if provider.get("response_id") is None else str(provider["response_id"])
        ),
        usage=(provider.get("usage") if isinstance(provider.get("usage"), Mapping) else None),
        adjudication=adjudication,
        failure_class=(
            None
            if provider.get("failure_class") is None
            else str(provider["failure_class"])
        ),
    )
    return ModelCallObservation(
        company_key=str(payload["company_key"]),
        company_name=str(payload["company_name"]),
        model_requested=str(payload["model_requested"]),
        model_returned=(
            None
            if payload.get("model_returned") is None
            else str(payload["model_returned"])
        ),
        packet_sha256=str(payload["packet_sha256"]),
        request_contract_sha256=str(payload["request_contract_sha256"]),
        latency_ms=int(payload["latency_ms"]),
        estimated_cost_usd=float(payload["estimated_cost_usd"]),
        result=result,
    )


def _load_checkpoint(
    path: Path | None,
    *,
    input_sha256: str,
    contract_sha256: str,
    config: Mapping[str, object],
) -> list[ModelCallObservation]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise SystemExit("invalid model campaign checkpoint root")
    if payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise SystemExit("unsupported model campaign checkpoint schema")
    if payload.get("input_sha256") != input_sha256:
        raise SystemExit("model campaign checkpoint input mismatch")
    if payload.get("contract_sha256") != contract_sha256:
        raise SystemExit("model campaign checkpoint contract mismatch")
    if payload.get("config") != dict(config):
        raise SystemExit("model campaign checkpoint configuration mismatch")
    rows = payload.get("observations")
    if not isinstance(rows, list) or not all(isinstance(item, Mapping) for item in rows):
        raise SystemExit("model campaign checkpoint observations must be objects")
    return [_observation_from_json(item) for item in rows]


def _write_checkpoint(
    path: Path | None,
    *,
    input_sha256: str,
    contract_sha256: str,
    config: Mapping[str, object],
    observations: Sequence[ModelCallObservation],
    complete: bool,
) -> None:
    if path is None:
        return
    _write_json_atomic(
        path,
        {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "input_sha256": input_sha256,
            "contract_sha256": contract_sha256,
            "config": dict(config),
            "complete": complete,
            "observations": [item.to_json() for item in observations],
            "boundary": list(BOUNDARY),
        },
    )


def _models(raw: str) -> tuple[str, ...]:
    models = tuple(dict.fromkeys(item.strip() for item in raw.split(",") if item.strip()))
    if not models:
        raise SystemExit("at least one model is required")
    return models


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark origin-adjudication models and validate escalation value."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument(
        "--models",
        default=",".join(DEFAULT_BENCHMARK_MODELS),
    )
    parser.add_argument("--max-cases", type=int, default=6)
    parser.add_argument("--max-requests", type=int, default=18)
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--max-output-tokens", type=int, default=600)
    parser.add_argument("--reserved-input-tokens", type=int, default=5000)
    parser.add_argument("--max-estimated-cost-usd", type=float, default=0.50)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--openai-api-key", default=os.getenv("OPENAI_API_KEY", ""))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_cases < 1:
        raise SystemExit("max-cases must be at least 1")
    if args.max_requests < 1:
        raise SystemExit("max-requests must be at least 1")
    if args.max_output_tokens < 1 or args.reserved_input_tokens < 1:
        raise SystemExit("token reservations must be at least 1")
    if args.max_estimated_cost_usd <= 0:
        raise SystemExit("max-estimated-cost-usd must be positive")
    if not str(args.openai_api_key or "").strip():
        raise SystemExit("OPENAI_API_KEY is required for the model campaign")

    model_order = _models(args.models)
    if args.max_requests < len(model_order):
        raise SystemExit("max-requests is lower than the model count")

    evidence = json.loads(args.input.read_text(encoding="utf-8"))
    contract_payload = json.loads(args.contract.read_text(encoding="utf-8"))
    if not isinstance(evidence, Mapping) or not isinstance(contract_payload, Mapping):
        raise SystemExit("campaign input and contract roots must be objects")
    raw_results = evidence.get("results")
    if not isinstance(raw_results, list):
        raise SystemExit("origin evidence report results must be an array")
    expectations = parse_expectations(contract_payload)
    decisions = [_decision_from_json(item) for item in raw_results if isinstance(item, Mapping)]
    selected: list[OriginEvidenceDecision] = []
    for decision in decisions:
        if match_expectation(decision, expectations) is not None:
            selected.append(decision)
        if len(selected) >= args.max_cases:
            break
    if not selected:
        raise SystemExit("no evidence decisions matched the benchmark contract")

    reserved_cost = 0.0
    for model in model_order:
        prices = MODEL_PRICES_USD_PER_MILLION.get(model)
        if prices is None:
            raise SystemExit(f"missing price reservation for model {model}")
        input_price, output_price = prices
        reserved_cost += len(selected) * (
            args.reserved_input_tokens * input_price / 1_000_000
            + args.max_output_tokens * output_price / 1_000_000
        )
    if reserved_cost > args.max_estimated_cost_usd:
        raise SystemExit(
            "pessimistic model campaign reservation exceeds cost ceiling: "
            f"reserved={reserved_cost:.6f} ceiling={args.max_estimated_cost_usd:.6f}"
        )

    config = {
        "models": list(model_order),
        "company_keys": [item.company_key for item in selected],
        "max_requests": args.max_requests,
        "reasoning_effort": args.reasoning_effort,
        "max_output_tokens": args.max_output_tokens,
        "reserved_input_tokens": args.reserved_input_tokens,
        "max_estimated_cost_usd": args.max_estimated_cost_usd,
        "pessimistic_reserved_cost_usd": round(reserved_cost, 8),
        "timeout_seconds": args.timeout_seconds,
    }
    input_sha = _sha256(args.input)
    contract_sha = _sha256(args.contract)
    observations = _load_checkpoint(
        args.checkpoint,
        input_sha256=input_sha,
        contract_sha256=contract_sha,
        config=config,
    )
    completed_keys = {(item.company_key, item.model_requested) for item in observations}
    request_attempts = sum(item.result.request_attempted for item in observations)

    for decision in selected:
        for model in model_order:
            key = (decision.company_key, model)
            if key in completed_keys:
                continue
            if request_attempts >= args.max_requests:
                raise SystemExit("model campaign request budget exhausted")
            observation = adjudicate_model(
                decision,
                api_key=args.openai_api_key,
                model=model,
                reasoning_effort=args.reasoning_effort,
                max_output_tokens=args.max_output_tokens,
                timeout_seconds=args.timeout_seconds,
            )
            observations.append(observation)
            request_attempts += int(observation.result.request_attempted)
            _write_checkpoint(
                args.checkpoint,
                input_sha256=input_sha,
                contract_sha256=contract_sha,
                config=config,
                observations=observations,
                complete=False,
            )

    by_key = {(item.company_key, item.model_requested): item for item in observations}
    scores = []
    for decision in selected:
        expectation = match_expectation(decision, expectations)
        if expectation is None:
            continue
        packet_hashes = {
            by_key[(decision.company_key, model)].packet_sha256 for model in model_order
        }
        contract_hashes = {
            by_key[(decision.company_key, model)].request_contract_sha256
            for model in model_order
        }
        if len(packet_hashes) != 1 or len(contract_hashes) != 1:
            raise SystemExit("models did not receive an identical benchmark task")
        for model in model_order:
            scores.append(
                score_observation(
                    decision,
                    by_key[(decision.company_key, model)],
                    expectation,
                )
            )

    score_by_key = {(item.company_key, item.model): item for item in scores}
    simulations_by_pair: dict[str, list] = {}
    for primary in model_order:
        for escalation in model_order:
            if primary == escalation:
                continue
            pair = f"{primary}->{escalation}"
            simulations = []
            for decision in selected:
                simulations.append(
                    simulate_escalation(
                        decision=decision,
                        primary_observation=by_key[(decision.company_key, primary)],
                        escalation_observation=by_key[(decision.company_key, escalation)],
                        primary_score=score_by_key[(decision.company_key, primary)],
                        escalation_score=score_by_key[(decision.company_key, escalation)],
                    )
                )
            simulations_by_pair[pair] = simulations

    summaries = summarize_models(
        observations,
        scores,
        model_order=model_order,
    )
    recommendation = recommend_route(summaries, simulations_by_pair)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "source_evidence_sha256": input_sha,
        "benchmark_contract_sha256": contract_sha,
        "review_output_only_not_pipeline_input": True,
        "boundary": list(BOUNDARY),
        "config": config,
        "summary": {
            "case_count": len(selected),
            "model_count": len(model_order),
            "request_attempts": request_attempts,
            "pessimistic_reserved_cost_usd": round(reserved_cost, 8),
            "estimated_total_cost_usd": round(
                sum(item.estimated_cost_usd for item in observations), 8
            ),
        },
        "model_summaries": summaries,
        "recommendation": recommendation,
        "case_scores": [item.to_json() for item in scores],
        "escalation_simulations": {
            pair: [item.to_json() for item in simulations]
            for pair, simulations in simulations_by_pair.items()
        },
        "observations": [item.to_json() for item in observations],
    }
    _write_json_atomic(args.output, report)
    _write_checkpoint(
        args.checkpoint,
        input_sha256=input_sha,
        contract_sha256=contract_sha,
        config=config,
        observations=observations,
        complete=True,
    )
    print(
        "origin_llm_model_campaign_complete: "
        f"cases={len(selected)} models={len(model_order)} "
        f"requests={request_attempts} "
        f"primary={recommendation.get('primary_model')} "
        f"escalation={recommendation.get('escalation_model')} "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
