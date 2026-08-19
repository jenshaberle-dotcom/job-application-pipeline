from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import psycopg

import scripts.run_detail_discovery_booster as detail_booster
import scripts.run_listing_discovery_booster as listing_booster
from scripts.run_employer_origin_detail_evidence_repair_agent import (
    DEFAULT_LOCATION_TERMS,
    DEFAULT_PROFILE_TERMS,
    DEFAULT_SEARCH_QUERY_LIMIT,
    DEFAULT_SEARCH_RESULT_LIMIT,
    DetailEvidence,
    GateStateRepository as DetailGateRepository,
    RepairOutcome,
    SourceCandidate as DetailSourceCandidate,
    build_repair_outcome,
    plausible_origin_url,
    unique_ordered,
)
from scripts.run_employer_origin_gate_agent import (
    GateOutcome,
    defensive_preview_gate,
    fetch_candidate_page,
    relevance_gate,
)
from scripts.run_employer_origin_preconnector_precondition_agent import Repository
from scripts.run_origin_source_discovery_agent import load_local_env_file
from src.config import get_database_config
from src.search_intelligence.preconnector_relevance_deferral import (
    evaluate_relevance_deferral,
)

EARLY_GATES = (
    "company_candidate",
    "source_discovery",
    "risk_gate",
    "technical_reachability_gate",
    "scope_gate",
    "defensive_preview_gate",
    "relevance_gate",
)
LISTING_GAP_REASON = "no same-domain job-like links found in bounded preview"

BOUNDARY = (
    "existing_candidate_only",
    "risk_gate_never_overridden",
    "deterministic_and_free_search_before_model",
    "provider_output_is_hypothesis_only",
    "fresh_canonical_validation_before_gate_pass",
    "unchanged_gap_fingerprint_suppresses_provider_replay",
    "tavily_disabled_without_runtime_non_payg_telemetry",
    "no_connector_build_or_registration",
    "no_final_approval_or_source_activation",
    "no_ingestion_ranking_application_or_product_mutation",
)


def gate_passed(gates: Mapping[str, Mapping[str, Any]], name: str) -> bool:
    row = gates.get(name)
    return bool(row and row.get("gate_status") == "passed")


def listing_gap_eligible(gates: Mapping[str, Mapping[str, Any]]) -> bool:
    required = (
        "company_candidate",
        "source_discovery",
        "risk_gate",
        "technical_reachability_gate",
        "scope_gate",
    )
    if any(not gate_passed(gates, name) for name in required):
        return False
    gate = gates.get("defensive_preview_gate") or {}
    return (
        gate.get("gate_status") == "manual_review_required"
        and gate.get("stop_reason") == LISTING_GAP_REASON
    )


def detail_gap_eligible(gates: Mapping[str, Mapping[str, Any]]) -> bool:
    if any(not gate_passed(gates, name) for name in EARLY_GATES):
        return False
    gate = gates.get("detail_evidence_gate") or {}
    return gate.get("gate_status") != "passed" and gate.get("gate_status") != "failed"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _profile_location_terms(args: argparse.Namespace) -> tuple[tuple[str, ...], tuple[str, ...]]:
    profile_terms = unique_ordered([*DEFAULT_PROFILE_TERMS, *(args.profile_term or [])])
    location_terms = unique_ordered([*DEFAULT_LOCATION_TERMS, *(args.location_term or [])])
    if args.target_location:
        location_terms = unique_ordered([args.target_location, *location_terms])
    return profile_terms, location_terms


def _detail_candidate(candidate: Any) -> DetailSourceCandidate:
    return DetailSourceCandidate(
        id=candidate.id,
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        candidate_url=candidate.candidate_url,
        source_name_candidate=candidate.source_name_candidate,
        source_family_candidate=candidate.source_family_candidate,
        source_target_candidate=candidate.source_target_candidate,
        source_type_candidate=candidate.source_type_candidate,
        status=candidate.status,
        risk_level=candidate.risk_level,
    )


def _gate_args(candidate: Any, args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        profile_terms=args.profile_term,
        target_location=args.target_location,
        source_target_candidate=candidate.source_target_candidate,
    )


def _stage_name(execution: Mapping[str, Any]) -> str | None:
    for item in execution.get("stages") or []:
        if isinstance(item, Mapping) and item.get("resolved_url"):
            return str(item.get("stage") or "") or None
    return None


def _persist_listing_attempt(
    repo: Repository,
    *,
    candidate_id: int,
    current_gate: Mapping[str, Any],
    execution: Mapping[str, Any],
    reviewed_by: str,
) -> None:
    evidence = dict(_mapping(current_gate.get("evidence")))
    evidence.update(
        {
            "listing_booster_evidence_fingerprint": execution.get("deterministic_evidence_fingerprint"),
            "listing_booster_provider_requests": int(execution.get("provider_requests") or 0),
            "listing_booster_llm_requests": int(execution.get("llm_requests") or 0),
            "listing_booster_unchanged_skip": bool(execution.get("unchanged_evidence_skip")),
            "listing_booster_resolved_url": execution.get("resolved_url"),
            "listing_booster_product_authority": False,
        }
    )
    repo.record_gate(
        candidate_id,
        GateOutcome(
            gate_name="defensive_preview_gate",
            gate_status=str(current_gate.get("gate_status") or "manual_review_required"),
            decision=str(current_gate.get("decision") or "manual_review_required"),
            stop_reason=str(current_gate.get("stop_reason") or LISTING_GAP_REASON),
            evidence=evidence,
        ),
        reviewed_by,
    )


def _write_listing_resolution(
    repo: Repository,
    *,
    candidate: Any,
    gates: dict[str, dict[str, Any]],
    payload: Mapping[str, Any],
    args: argparse.Namespace,
) -> tuple[bool, dict[str, Any]]:
    execution = _mapping(payload.get("execution"))
    current = gates.get("defensive_preview_gate") or {}
    resolved_url = str(execution.get("resolved_url") or "").strip()
    result: dict[str, Any] = {
        "resolved_url": resolved_url or None,
        "resolved_stage": _stage_name(execution),
        "provider_requests": int(execution.get("provider_requests") or 0),
        "llm_requests": int(execution.get("llm_requests") or 0),
        "evidence_fingerprint": execution.get("deterministic_evidence_fingerprint"),
        "unchanged_skip": bool(execution.get("unchanged_evidence_skip")),
        "gate_passed": False,
    }
    if not resolved_url:
        _persist_listing_attempt(
            repo,
            candidate_id=candidate.id,
            current_gate=current,
            execution=execution,
            reviewed_by=args.reviewed_by,
        )
        return False, result

    if not plausible_origin_url(resolved_url, _detail_candidate(candidate)):
        result["rejection"] = "resolved_listing_url_failed_employer_origin_identity_boundary"
        _persist_listing_attempt(
            repo,
            candidate_id=candidate.id,
            current_gate=current,
            execution=execution,
            reviewed_by=args.reviewed_by,
        )
        return False, result

    fetch = fetch_candidate_page(
        resolved_url,
        timeout_seconds=args.timeout_seconds,
        max_preview_links=args.max_preview_links,
        source_family_candidate=candidate.source_family_candidate,
    )
    preview = defensive_preview_gate(fetch)
    if preview.gate_status != "passed":
        result["rejection"] = preview.stop_reason or "canonical_defensive_preview_failed"
        _persist_listing_attempt(
            repo,
            candidate_id=candidate.id,
            current_gate=current,
            execution=execution,
            reviewed_by=args.reviewed_by,
        )
        return False, result

    preview = GateOutcome(
        gate_name=preview.gate_name,
        gate_status=preview.gate_status,
        decision=preview.decision,
        stop_reason=preview.stop_reason,
        evidence={
            **preview.evidence,
            "listing_booster_resolved_url": resolved_url,
            "listing_booster_resolved_stage": _stage_name(execution),
            "listing_booster_evidence_fingerprint": execution.get("deterministic_evidence_fingerprint"),
            "listing_booster_provider_requests": int(execution.get("provider_requests") or 0),
            "listing_booster_llm_requests": int(execution.get("llm_requests") or 0),
            "provider_output_authority": False,
            "canonical_preview_revalidation": True,
        },
    )
    repo.record_gate(candidate.id, preview, args.reviewed_by)

    relevance = relevance_gate(_gate_args(candidate, args), fetch)
    relevance = GateOutcome(
        gate_name=relevance.gate_name,
        gate_status=relevance.gate_status,
        decision=relevance.decision,
        stop_reason=relevance.stop_reason,
        evidence={
            **relevance.evidence,
            "evaluated_listing_url": resolved_url,
            "listing_booster_evidence_fingerprint": execution.get("deterministic_evidence_fingerprint"),
            "provider_output_authority": False,
        },
    )
    repo.record_gate(candidate.id, relevance, args.reviewed_by)
    result["gate_passed"] = True
    result["relevance_status"] = relevance.gate_status
    return True, result


def _apply_relevance_deferral_if_eligible(
    repo: Repository,
    *,
    candidate_id: int,
    reviewed_by: str,
) -> bool:
    gates = repo.load_gates(candidate_id)
    decision = evaluate_relevance_deferral(gates)
    if not decision.eligible:
        return False
    current = gates["relevance_gate"]
    repo.record_gate(
        candidate_id,
        GateOutcome(
            gate_name="relevance_gate",
            gate_status="passed",
            decision="passed",
            stop_reason=None,
            evidence={
                **decision.evidence,
                "agent": "lifecycle_booster_repair",
                "source_relevance_gate_stop_reason": current.get("stop_reason"),
            },
        ),
        reviewed_by,
    )
    return True


def _deterministic_detail_repair(
    detail_repo: DetailGateRepository,
    *,
    candidate: Any,
    gates: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> RepairOutcome:
    profile_terms, location_terms = _profile_location_terms(args)
    outcome = build_repair_outcome(
        candidate=_detail_candidate(candidate),
        gates=gates,
        profile_terms=profile_terms,
        location_terms=location_terms,
        max_seed_pages=args.max_seed_pages,
        max_detail_pages=args.max_detail_pages,
        enable_search_discovery=True,
        max_search_queries=args.max_search_queries,
        max_search_results=args.max_search_results,
        search_provider="duckduckgo_html",
    )
    detail_repo.record_detail_evidence_gate(
        candidate_id=candidate.id,
        outcome=outcome,
        reviewed_by=args.reviewed_by,
    )
    return outcome


def _detail_booster_args(
    candidate: Any,
    *,
    args: argparse.Namespace,
    previous_gap_fingerprint: str | None,
) -> argparse.Namespace:
    return argparse.Namespace(
        candidate_id=candidate.id,
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        candidate_url=candidate.candidate_url,
        source_name=candidate.source_name_candidate,
        source_family=candidate.source_family_candidate,
        source_target=candidate.source_target_candidate or args.target_location,
        source_type=candidate.source_type_candidate,
        candidate_status=candidate.status,
        risk_level=candidate.risk_level,
        target_location=args.target_location,
        profile_term=args.profile_term,
        location_term=args.location_term,
        max_d0_seed_pages=args.max_seed_pages,
        max_d0_detail_pages=args.max_detail_pages,
        tavily_remaining_credits=None,
        disable_tavily=True,
        tavily_provider_unavailable=False,
        disable_llm=not args.execute_provider_booster,
        search_depth="advanced",
        max_tavily_requests=0,
        search_max_results=5,
        search_timeout_seconds=20.0,
        model_timeout_seconds=args.model_timeout_seconds,
        reserved_input_tokens=3500,
        model_max_output_tokens=500,
        luna_max_output_tokens=1200,
        previous_gap_fingerprint=previous_gap_fingerprint,
        output=None,
    )


def _listing_booster_args(
    candidate: Any,
    *,
    args: argparse.Namespace,
    previous_evidence_fingerprint: str | None,
) -> argparse.Namespace:
    return argparse.Namespace(
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        origin_url=candidate.candidate_url,
        tavily_remaining_credits=None,
        disable_tavily=True,
        tavily_provider_unavailable=False,
        disable_llm=not args.execute_provider_booster,
        search_depth="advanced",
        max_tavily_requests=0,
        search_max_results=5,
        search_timeout_seconds=20.0,
        model_timeout_seconds=args.model_timeout_seconds,
        reserved_input_tokens=3500,
        model_max_output_tokens=500,
        luna_max_output_tokens=6000,
        previous_evidence_fingerprint=previous_evidence_fingerprint,
        output=None,
    )


def detail_outcome_from_booster(
    payload: Mapping[str, Any],
) -> RepairOutcome | None:
    execution = _mapping(payload.get("execution"))
    resolved_url = str(execution.get("resolved_url") or "").strip()
    validation = _mapping(execution.get("resolved_validation"))
    validation_evidence = _mapping(validation.get("evidence"))
    profile_terms = tuple(
        str(item) for item in (validation_evidence.get("profile_terms") or ()) if str(item)
    )
    location_terms = tuple(
        str(item) for item in (validation_evidence.get("location_terms") or ()) if str(item)
    )
    if not resolved_url or validation.get("accepted") is not True or not profile_terms or not location_terms:
        return None
    source_url = str(validation.get("candidate_url") or resolved_url)
    detail = DetailEvidence(
        url=source_url,
        final_url=resolved_url,
        status_code=int(validation_evidence.get("status_code") or 200),
        title=str(validation_evidence.get("title") or ""),
        profile_terms=profile_terms,
        location_terms=location_terms,
        html_bytes=0,
        reason="Booster hypothesis passed canonical concrete-detail deterministic validation.",
    )
    supported = {
        "url": detail.url,
        "final_url": detail.final_url,
        "status_code": detail.status_code,
        "title": detail.title,
        "profile_terms": list(detail.profile_terms),
        "location_terms": list(detail.location_terms),
        "html_bytes": detail.html_bytes,
        "reason": detail.reason,
    }
    return RepairOutcome(
        gate_status="passed",
        decision="passed",
        stop_reason=None,
        details=(detail,),
        rejected_urls=(),
        requested_urls=(resolved_url,),
        evidence={
            "supported_detail_evidence": [supported],
            "supported_details": [supported],
            "detail_discovery_booster_gap_fingerprint": execution.get("gap_fingerprint"),
            "detail_discovery_booster_resolved_stage": _stage_name(execution),
            "detail_discovery_booster_provider_requests": int(execution.get("provider_requests") or 0),
            "detail_discovery_booster_llm_requests": int(execution.get("llm_requests") or 0),
            "detail_discovery_booster_estimated_model_cost_usd": float(execution.get("estimated_model_cost_usd") or 0.0),
            "provider_output_authority": False,
            "canonical_detail_validation": True,
            "raw_html_persisted": False,
        },
    )


def _persist_unresolved_detail_attempt(
    repo: Repository,
    *,
    candidate_id: int,
    current_gate: Mapping[str, Any],
    execution: Mapping[str, Any],
    reviewed_by: str,
) -> None:
    evidence = dict(_mapping(current_gate.get("evidence")))
    evidence.update(
        {
            "detail_discovery_booster_gap_fingerprint": execution.get("gap_fingerprint"),
            "detail_discovery_booster_provider_requests": int(execution.get("provider_requests") or 0),
            "detail_discovery_booster_llm_requests": int(execution.get("llm_requests") or 0),
            "detail_discovery_booster_estimated_model_cost_usd": float(execution.get("estimated_model_cost_usd") or 0.0),
            "detail_discovery_booster_unchanged_skip": bool(execution.get("unchanged_gap_skip")),
            "provider_output_authority": False,
        }
    )
    repo.record_gate(
        candidate_id,
        GateOutcome(
            gate_name="detail_evidence_gate",
            gate_status=str(current_gate.get("gate_status") or "manual_review_required"),
            decision=str(current_gate.get("decision") or "manual_review_required"),
            stop_reason=(
                str(current_gate.get("stop_reason"))
                if current_gate.get("stop_reason")
                else "bounded deterministic and booster detail discovery remained unresolved"
            ),
            evidence=evidence,
        ),
        reviewed_by,
    )


def run_agent(args: argparse.Namespace) -> int:
    load_local_env_file()
    report: dict[str, Any] = {
        "candidate_id": args.candidate_id,
        "boundary": list(BOUNDARY),
        "execute_provider_booster": bool(args.execute_provider_booster),
        "listing": None,
        "relevance_deferred": False,
        "deterministic_detail": None,
        "detail": None,
        "provider_requests": 0,
        "llm_requests": 0,
        "estimated_model_cost_usd": 0.0,
    }

    with psycopg.connect(**get_database_config()) as conn:
        repo = Repository(conn)
        detail_repo = DetailGateRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        gates = repo.load_gates(candidate.id)
        report["company_key"] = candidate.company_key
        report["company_name"] = candidate.company_name

        if not gate_passed(gates, "risk_gate"):
            report["outcome"] = "risk_gate_not_passed"
            return _finish(report, args.output, exit_code=2)

        if listing_gap_eligible(gates):
            current = gates["defensive_preview_gate"]
            previous = _mapping(current.get("evidence")).get("listing_booster_evidence_fingerprint")
            payload = listing_booster.run(
                _listing_booster_args(
                    candidate,
                    args=args,
                    previous_evidence_fingerprint=str(previous) if previous else None,
                )
            )
            passed, listing_report = _write_listing_resolution(
                repo,
                candidate=candidate,
                gates=gates,
                payload=payload,
                args=args,
            )
            conn.commit()
            report["listing"] = listing_report
            report["provider_requests"] += int(listing_report.get("provider_requests") or 0)
            report["llm_requests"] += int(listing_report.get("llm_requests") or 0)
            gates = repo.load_gates(candidate.id)
            if not passed:
                report["outcome"] = "listing_discovery_unresolved"
                return _finish(report, args.output, exit_code=2)

        if _apply_relevance_deferral_if_eligible(
            repo,
            candidate_id=candidate.id,
            reviewed_by=args.reviewed_by,
        ):
            conn.commit()
            report["relevance_deferred"] = True
            gates = repo.load_gates(candidate.id)

        if any(not gate_passed(gates, name) for name in EARLY_GATES):
            report["outcome"] = "early_gate_unresolved"
            report["unpassed_early_gates"] = [
                name for name in EARLY_GATES if not gate_passed(gates, name)
            ]
            return _finish(report, args.output, exit_code=2)

        if not gate_passed(gates, "detail_evidence_gate"):
            deterministic = _deterministic_detail_repair(
                detail_repo,
                candidate=candidate,
                gates=gates,
                args=args,
            )
            conn.commit()
            report["deterministic_detail"] = {
                "gate_status": deterministic.gate_status,
                "decision": deterministic.decision,
                "detail_count": len(deterministic.details),
                "stop_reason": deterministic.stop_reason,
            }
            gates = repo.load_gates(candidate.id)

        if gate_passed(gates, "detail_evidence_gate"):
            report["outcome"] = "detail_evidence_passed_without_model"
            return _finish(report, args.output, exit_code=0)

        if not detail_gap_eligible(gates):
            report["outcome"] = "detail_booster_not_eligible"
            return _finish(report, args.output, exit_code=2)

        current_detail = gates["detail_evidence_gate"]
        previous_gap = _mapping(current_detail.get("evidence")).get(
            "detail_discovery_booster_gap_fingerprint"
        )
        payload = detail_booster.run(
            _detail_booster_args(
                candidate,
                args=args,
                previous_gap_fingerprint=str(previous_gap) if previous_gap else None,
            )
        )
        execution = _mapping(payload.get("execution"))
        report["detail"] = {
            "resolved_url": execution.get("resolved_url"),
            "resolved_stage": _stage_name(execution),
            "provider_requests": int(execution.get("provider_requests") or 0),
            "llm_requests": int(execution.get("llm_requests") or 0),
            "estimated_model_cost_usd": float(execution.get("estimated_model_cost_usd") or 0.0),
            "gap_fingerprint": execution.get("gap_fingerprint"),
            "unchanged_skip": bool(execution.get("unchanged_gap_skip")),
        }
        report["provider_requests"] += int(execution.get("provider_requests") or 0)
        report["llm_requests"] += int(execution.get("llm_requests") or 0)
        report["estimated_model_cost_usd"] += float(execution.get("estimated_model_cost_usd") or 0.0)

        resolved_outcome = detail_outcome_from_booster(payload)
        if resolved_outcome is not None:
            detail_repo.record_detail_evidence_gate(
                candidate_id=candidate.id,
                outcome=resolved_outcome,
                reviewed_by=args.reviewed_by,
            )
            conn.commit()
            report["outcome"] = "detail_evidence_passed_after_booster"
            return _finish(report, args.output, exit_code=0)

        _persist_unresolved_detail_attempt(
            repo,
            candidate_id=candidate.id,
            current_gate=current_detail,
            execution=execution,
            reviewed_by=args.reviewed_by,
        )
        conn.commit()
        report["outcome"] = (
            "unchanged_detail_gap_skipped"
            if execution.get("unchanged_gap_skip")
            else "detail_discovery_unresolved"
        )
        return _finish(report, args.output, exit_code=2)


def _finish(report: dict[str, Any], output: Path | None, *, exit_code: int) -> int:
    report["provider_requests"] = int(report.get("provider_requests") or 0)
    report["llm_requests"] = int(report.get("llm_requests") or 0)
    report["estimated_model_cost_usd"] = round(float(report.get("estimated_model_cost_usd") or 0.0), 8)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "lifecycle_booster_repair: "
        f"candidate_id={report.get('candidate_id')} outcome={report.get('outcome')} "
        f"provider_requests={report['provider_requests']} llm_requests={report['llm_requests']} "
        f"estimated_model_cost_usd={report['estimated_model_cost_usd']:.6f}"
    )
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Route exact unresolved employer-origin lifecycle gaps through existing Listing/Detail boosters "
            "without granting provider or product authority."
        )
    )
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")
    parser.add_argument("--execute-provider-booster", action="store_true")
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--profile-term", action="append")
    parser.add_argument("--location-term", action="append")
    parser.add_argument("--max-preview-links", type=int, default=25)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--max-seed-pages", type=int, default=8)
    parser.add_argument("--max-detail-pages", type=int, default=6)
    parser.add_argument("--max-search-queries", type=int, default=DEFAULT_SEARCH_QUERY_LIMIT)
    parser.add_argument("--max-search-results", type=int, default=DEFAULT_SEARCH_RESULT_LIMIT)
    parser.add_argument("--model-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--reviewed-by", default="lifecycle_booster_repair")
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
