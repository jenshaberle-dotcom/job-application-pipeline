from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

import scripts.run_detail_discovery_booster as detail_booster
from scripts.run_product_v1_origin_vacancy_bridge import run_bridge_for_contender
from src.config import get_database_config
from src.job_lifecycle_health import fetch_exact_detail
from src.search_intelligence.market_opportunity_bridge import (
    MarketOpportunity,
    bridge_outcome_from_exact_status,
    opportunity_to_contender,
    product_authority_boundary,
    risk_gate_blocks,
)
from src.search_intelligence.product_v1_origin_vacancy_bridge import (
    ExactDetailAttempt,
    OriginCandidateSnapshot,
    evaluate_exact_detail_attempts,
    origin_candidate_from_row,
    resolve_origin_candidate,
)

MAX_OPPORTUNITIES = 20
WRITE_APPROVAL_TOKEN = "approve_market_opportunity_verification"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _load_state(
    opportunity_ids: list[int],
) -> tuple[list[dict[str, Any]], list[OriginCandidateSnapshot], dict[int, dict[str, Any]], dict[int, str | None]]:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                """
                SELECT id, normalized_company_key, company_name, title, evidence_url,
                       source_name, observed_at, evidence
                FROM market_evidence
                WHERE id = ANY(%s)
                  AND (
                    evidence_kind = 'manual_market_observation'
                    OR evidence_source = 'manual_market_observation'
                    OR evidence ->> 'observation_origin' = 'external_market_observation'
                  )
                ORDER BY id
                """,
                (opportunity_ids,),
            )
            opportunities = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT id, company_key, company_name, candidate_url,
                       source_name_candidate, source_family_candidate,
                       source_target_candidate, source_type_candidate, status, risk_level
                FROM employer_origin_source_candidates
                ORDER BY id
                """
            )
            candidates = [origin_candidate_from_row(dict(row)) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT candidate_id, gate_status, decision, stop_reason, evidence
                FROM employer_origin_candidate_gate_reviews
                WHERE gate_name = 'risk_gate'
                """
            )
            risk_gates = {int(row["candidate_id"]): dict(row) for row in cur.fetchall()}
            cur.execute(
                """
                SELECT DISTINCT ON (market_evidence_id)
                       market_evidence_id, evidence
                FROM market_opportunity_verification_observations
                WHERE market_evidence_id = ANY(%s)
                ORDER BY market_evidence_id, observed_at DESC, id DESC
                """,
                (opportunity_ids,),
            )
            previous_fingerprints: dict[int, str | None] = {}
            for row in cur.fetchall():
                evidence = _mapping(row.get("evidence"))
                fingerprint = str(evidence.get("detail_gap_fingerprint") or "").strip() or None
                previous_fingerprints[int(row["market_evidence_id"])] = fingerprint
        conn.rollback()
    return opportunities, candidates, risk_gates, previous_fingerprints


def _opportunity(row: Mapping[str, Any]) -> MarketOpportunity:
    evidence = _mapping(row.get("evidence"))
    return MarketOpportunity(
        opportunity_id=int(row["id"]),
        company_name=str(row.get("company_name") or ""),
        title=str(row.get("title") or ""),
        observation_channel=str(row.get("source_name") or evidence.get("observation_channel") or "unknown"),
        evidence_url=str(row.get("evidence_url") or "").strip() or None,
        observed_at=str(row.get("observed_at") or "").strip() or None,
        location=str(evidence.get("location") or "").strip() or None,
        remote_signal=str(evidence.get("remote_signal") or "unknown"),
    )


def _contender_row(opportunity: MarketOpportunity) -> dict[str, Any]:
    contender = opportunity_to_contender(opportunity)
    return {
        "inspection_priority": contender.inspection_priority,
        "silver_job_id": contender.silver_job_id,
        "title": contender.title,
        "company_name": contender.company_name,
        "city": contender.city,
        "country": contender.country,
        "publication_date": None,
        "source_name": contender.source_name,
        "source_url": contender.source_url,
        "canonical_source_type": contender.canonical_source_type,
        "origin_validation_status": "observational_only",
        "work_model": opportunity.remote_signal,
        "commute_minutes": None,
        "lifecycle_status": contender.lifecycle_status,
        "geography_bucket": contender.geography_bucket,
    }


def _provider_args(
    opportunity: MarketOpportunity,
    candidate: OriginCandidateSnapshot,
    *,
    previous_gap_fingerprint: str | None,
) -> argparse.Namespace:
    city, country, _bucket = (
        opportunity_to_contender(opportunity).city,
        opportunity_to_contender(opportunity).country,
        opportunity_to_contender(opportunity).geography_bucket,
    )
    location_terms = [value for value in (opportunity.location, city, country, "remote") if value]
    return argparse.Namespace(
        candidate_id=candidate.candidate_id,
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        candidate_url=candidate.candidate_url,
        source_name=candidate.source_name_candidate,
        source_family=candidate.source_family_candidate,
        source_target=candidate.source_target_candidate or city or country or "Hannover",
        source_type=candidate.source_type_candidate,
        candidate_status=candidate.status,
        risk_level=candidate.risk_level,
        target_location=city or country or "Hannover",
        profile_term=[opportunity.title],
        location_term=location_terms,
        max_d0_seed_pages=8,
        max_d0_detail_pages=6,
        tavily_remaining_credits=None,
        disable_tavily=True,
        tavily_provider_unavailable=False,
        disable_llm=False,
        search_depth="advanced",
        max_tavily_requests=0,
        search_max_results=5,
        search_timeout_seconds=20.0,
        model_timeout_seconds=60.0,
        reserved_input_tokens=3500,
        model_max_output_tokens=500,
        luna_max_output_tokens=1200,
        previous_gap_fingerprint=previous_gap_fingerprint,
        output=None,
    )


def _persist(
    *,
    opportunity_id: int,
    candidate_id: int | None,
    outcome: str,
    resolved_url: str | None,
    reason: str,
    evidence: Mapping[str, Any],
    observed_by: str,
) -> int:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO market_opportunity_verification_observations (
                    market_evidence_id, candidate_id, outcome, resolved_url,
                    evidence_reason, evidence, observed_by
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                RETURNING id
                """,
                (
                    opportunity_id,
                    candidate_id,
                    outcome,
                    resolved_url,
                    reason,
                    json.dumps(dict(evidence), sort_keys=True),
                    observed_by,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        raise RuntimeError("verification observation write returned no id")
    return int(row["id"])


def run_one(
    row: Mapping[str, Any],
    *,
    candidates: list[OriginCandidateSnapshot],
    risk_gates: Mapping[int, Mapping[str, Any]],
    previous_gap_fingerprint: str | None,
    execute_provider_booster: bool,
) -> dict[str, Any]:
    opportunity = _opportunity(row)
    contender = opportunity_to_contender(opportunity)
    resolution = resolve_origin_candidate(contender, candidates)
    result: dict[str, Any] = {
        "opportunity_id": opportunity.opportunity_id,
        "company_name": opportunity.company_name,
        "title": opportunity.title,
        "location": opportunity.location,
        "remote_signal": opportunity.remote_signal,
        "candidate_resolution": resolution.status,
        "candidate_id": resolution.candidate.candidate_id if resolution.candidate else None,
        "provider_booster_attempted": False,
        "provider_requests": 0,
        "llm_requests": 0,
        "tavily_requests": 0,
        "exact_vacancy": None,
        "outcome": None,
        "resolved_url": None,
        "reason": resolution.reason,
        "evidence": {"candidate_resolution": resolution.status},
    }

    if resolution.status == "origin_candidate_required":
        result.update(outcome="employer_candidate_missing")
        return result
    if resolution.status == "origin_source_url_required":
        result.update(outcome="origin_source_required")
        return result
    if resolution.status != "ready_for_bounded_detail_discovery" or resolution.candidate is None:
        result.update(outcome="unverifiable")
        return result

    candidate = resolution.candidate
    risk_gate = risk_gates.get(candidate.candidate_id)
    if risk_gate_blocks(candidate_risk_level=candidate.risk_level, risk_gate=risk_gate):
        result.update(
            outcome="risk_gate_blocked",
            reason=str((risk_gate or {}).get("stop_reason") or "Candidate is blocked by current risk authority."),
            evidence={"candidate_resolution": resolution.status, "risk_gate": dict(risk_gate or {})},
        )
        return result

    deterministic = run_bridge_for_contender(
        _contender_row(opportunity),
        candidates=candidates,
        max_origin_candidates=12,
        origin_timeout_seconds=5.0,
        max_seed_pages=3,
        max_detail_pages=8,
    )
    exact = _mapping(deterministic.get("exact_vacancy"))
    exact_status = str(exact.get("status") or "") or None
    outcome, reason = bridge_outcome_from_exact_status(exact_status)
    result["exact_vacancy"] = dict(exact)
    result["outcome"] = outcome
    result["resolved_url"] = exact.get("resolved_url")
    result["reason"] = str(exact.get("reason") or reason)
    result["evidence"] = {
        "candidate_resolution": resolution.status,
        "deterministic_bridge": deterministic,
        "provider_output_authority": False,
    }
    if outcome in {"verified_active", "verified_closed"} or not execute_provider_booster:
        return result

    provider_payload = detail_booster.run(
        _provider_args(
            opportunity,
            candidate,
            previous_gap_fingerprint=previous_gap_fingerprint,
        )
    )
    execution = _mapping(provider_payload.get("execution"))
    result["provider_booster_attempted"] = True
    result["provider_requests"] = int(execution.get("provider_requests") or 0)
    result["llm_requests"] = int(execution.get("llm_requests") or 0)
    result["tavily_requests"] = int(execution.get("tavily_requests") or 0)
    resolved_url = str(execution.get("resolved_url") or "").strip()
    gap_fingerprint = str(execution.get("deterministic_evidence_fingerprint") or "").strip() or None
    result["evidence"] = {
        **dict(result["evidence"]),
        "detail_booster": provider_payload,
        "detail_gap_fingerprint": gap_fingerprint,
        "provider_output_authority": False,
    }
    if not resolved_url:
        result["reason"] = "Canonical Detail Discovery cascade did not resolve an exact-vacancy candidate URL."
        return result

    provider_exact = evaluate_exact_detail_attempts(
        contender,
        [
            ExactDetailAttempt(
                url=resolved_url,
                link_text="",
                probe=fetch_exact_detail(resolved_url),
            )
        ],
    )
    provider_status = str(provider_exact.get("status") or "") or None
    outcome, fallback_reason = bridge_outcome_from_exact_status(provider_status)
    result["exact_vacancy"] = provider_exact
    result["outcome"] = outcome
    result["resolved_url"] = provider_exact.get("resolved_url")
    result["reason"] = str(provider_exact.get("reason") or fallback_reason)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify observed market opportunities against exact employer-origin vacancies.")
    parser.add_argument("--opportunity-id", action="append", type=int, required=True)
    parser.add_argument("--execute-provider-booster", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--observed-by", default="agent")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ids = list(dict.fromkeys(args.opportunity_id))
    if not ids or len(ids) > MAX_OPPORTUNITIES or any(value < 1 for value in ids):
        raise SystemExit(f"Provide between 1 and {MAX_OPPORTUNITIES} positive opportunity ids.")
    if args.write and args.approval_token != WRITE_APPROVAL_TOKEN:
        raise SystemExit("--write requires the exact opportunity-verification approval token")

    rows, candidates, risk_gates, previous = _load_state(ids)
    found_ids = {int(row["id"]) for row in rows}
    missing = [value for value in ids if value not in found_ids]
    if missing:
        raise SystemExit(f"Requested manual market opportunities not found: {missing}")

    results: list[dict[str, Any]] = []
    for row in rows:
        opportunity_id = int(row["id"])
        item = run_one(
            row,
            candidates=candidates,
            risk_gates=risk_gates,
            previous_gap_fingerprint=previous.get(opportunity_id),
            execute_provider_booster=args.execute_provider_booster,
        )
        if args.write:
            item["verification_observation_id"] = _persist(
                opportunity_id=opportunity_id,
                candidate_id=item.get("candidate_id"),
                outcome=str(item["outcome"]),
                resolved_url=str(item.get("resolved_url") or "").strip() or None,
                reason=str(item.get("reason") or ""),
                evidence=_mapping(item.get("evidence")),
                observed_by=args.observed_by,
            )
        results.append(item)

    payload = {
        "schema_version": "pipeline.market_opportunity_vacancy_bridge.v1",
        "requested_opportunity_ids": ids,
        "write_enabled": bool(args.write),
        "provider_booster_enabled": bool(args.execute_provider_booster),
        "results": results,
        "summary": {
            "opportunity_count": len(results),
            "verified_active": sum(item.get("outcome") == "verified_active" for item in results),
            "verified_closed": sum(item.get("outcome") == "verified_closed" for item in results),
            "risk_gate_blocked": sum(item.get("outcome") == "risk_gate_blocked" for item in results),
            "unresolved": sum(item.get("outcome") not in {"verified_active", "verified_closed", "risk_gate_blocked"} for item in results),
            "provider_requests": sum(int(item.get("provider_requests") or 0) for item in results),
            "llm_requests": sum(int(item.get("llm_requests") or 0) for item in results),
            "tavily_requests": sum(int(item.get("tavily_requests") or 0) for item in results),
        },
        "boundary": product_authority_boundary(),
    }
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
