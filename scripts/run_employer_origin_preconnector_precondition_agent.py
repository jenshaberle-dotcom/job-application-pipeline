"""Recover canonical employer-origin preconditions before connector candidacy.

This agent exists for candidates whose detail-evidence gate may already be
canonical while earlier lifecycle gates were never executed. It never infers a
pass from queue position. Instead it executes the existing bounded deterministic
A-G gates against the persisted candidate and, only after a passed detail gate,
computes incremental uniqueness from that gate's already-accepted detail
evidence.

It does not perform search-provider calls, LLM calls, URL discovery, connector
registration, source activation, ingestion, ranking, scoring, or application
mutation. A passed detail-evidence gate is preserved verbatim.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from types import SimpleNamespace
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row
import requests

from scripts.run_employer_origin_detail_uniqueness_agent import (
    DetailCandidate,
    fetch_existing_evidence,
    incremental_uniqueness_outcome,
)
from scripts.run_employer_origin_gate_agent import (
    DEFAULT_PROFILE_TERMS,
    GateOutcome,
    company_candidate_gate,
    defensive_preview_gate,
    fetch_candidate_page,
    postfetch_risk_gate,
    prefetch_risk_gate,
    relevance_gate,
    scope_gate,
    source_discovery_gate,
    technical_reachability_gate,
)
from scripts.run_origin_source_discovery_agent import load_local_env_file
from src.config import get_database_config

EARLY_PRECONDITION_GATES = (
    "company_candidate",
    "source_discovery",
    "risk_gate",
    "technical_reachability_gate",
    "scope_gate",
    "defensive_preview_gate",
    "relevance_gate",
)
DETAIL_EVIDENCE_GATE = "detail_evidence_gate"
INCREMENTAL_UNIQUENESS_GATE = "incremental_uniqueness_gate"

BOUNDARY = (
    "existing_candidate_only",
    "canonical_gate_writes_only",
    "preserve_passed_gate_rows",
    "preserve_passed_detail_evidence",
    "bounded_candidate_http_only",
    "no_search_provider",
    "no_llm",
    "no_connector_registration",
    "no_source_activation",
    "no_ingestion",
    "no_ranking_scoring_or_application_mutation",
)


@dataclass(frozen=True)
class Candidate:
    id: int
    company_key: str
    company_name: str
    candidate_url: str
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str
    status: str
    risk_level: str


class Repository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_candidate(self, *, candidate_id: int | None, company_key: str | None) -> Candidate:
        if candidate_id is None and not company_key:
            raise ValueError("Either candidate_id or company_key is required.")
        with self.conn.cursor(row_factory=dict_row) as cur:
            if candidate_id is not None:
                cur.execute("select * from employer_origin_source_candidates where id = %s", (candidate_id,))
            else:
                cur.execute(
                    "select * from employer_origin_source_candidates where company_key = %s order by id desc limit 1",
                    (company_key,),
                )
            row = cur.fetchone()
        if row is None:
            raise ValueError("No employer-origin source candidate found.")
        if not row.get("candidate_url"):
            raise ValueError("Candidate has no candidate_url; precondition recovery cannot proceed.")
        return Candidate(
            id=int(row["id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            candidate_url=str(row["candidate_url"]),
            source_name_candidate=str(row.get("source_name_candidate") or row["company_key"]),
            source_family_candidate=str(row.get("source_family_candidate") or row["company_key"]),
            source_target_candidate=row.get("source_target_candidate"),
            source_type_candidate=str(row.get("source_type_candidate") or "employer_origin_career_site"),
            status=str(row.get("status") or "discovery"),
            risk_level=str(row.get("risk_level") or "unknown"),
        )

    def load_gates(self, candidate_id: int) -> dict[str, dict[str, Any]]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select gate_name, gate_order, gate_status, decision, stop_reason,
                       evidence, reviewed_by, reviewed_at, updated_at
                from employer_origin_candidate_gate_reviews
                where candidate_id = %s
                order by gate_order, gate_name
                """,
                (candidate_id,),
            )
            rows = cur.fetchall()
        return {str(row["gate_name"]): dict(row) for row in rows}

    def record_gate(self, candidate_id: int, outcome: GateOutcome, reviewed_by: str) -> None:
        current = self.load_gates(candidate_id).get(outcome.gate_name)
        if current is None:
            raise ValueError(f"Missing canonical gate {outcome.gate_name} for candidate_id={candidate_id}")
        if current.get("gate_status") == "passed":
            return

        previous = {
            "gate_status": current.get("gate_status"),
            "decision": current.get("decision"),
            "stop_reason": current.get("stop_reason"),
            "evidence": current.get("evidence"),
            "reviewed_by": current.get("reviewed_by"),
            "reviewed_at": current.get("reviewed_at"),
        }
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                update employer_origin_candidate_gate_reviews
                set gate_status = %s,
                    decision = %s,
                    stop_reason = %s,
                    evidence = %s::jsonb,
                    reviewed_by = %s,
                    reviewed_at = now(),
                    updated_at = now()
                where candidate_id = %s and gate_name = %s
                returning id
                """,
                (
                    outcome.gate_status,
                    outcome.decision,
                    outcome.stop_reason,
                    json.dumps(outcome.evidence, ensure_ascii=False),
                    reviewed_by,
                    candidate_id,
                    outcome.gate_name,
                ),
            )
            gate_review_id = int(cur.fetchone()["id"])
            cur.execute(
                """
                insert into employer_origin_candidate_gate_events (
                    candidate_id, gate_review_id, event_type, previous_state,
                    new_state, event_reason, created_by
                )
                values (%s, %s, 'gate_updated', %s::jsonb, %s::jsonb, %s, %s)
                """,
                (
                    candidate_id,
                    gate_review_id,
                    json.dumps(previous, default=str, ensure_ascii=False),
                    json.dumps(
                        {
                            "gate_name": outcome.gate_name,
                            "gate_status": outcome.gate_status,
                            "decision": outcome.decision,
                            "stop_reason": outcome.stop_reason,
                            "evidence": outcome.evidence,
                        },
                        ensure_ascii=False,
                    ),
                    "bounded preconnector precondition recovery",
                    reviewed_by,
                ),
            )
        self.conn.commit()

    def update_candidate_stop(self, candidate_id: int, outcome: GateOutcome) -> None:
        if outcome.gate_status == "failed":
            status, risk = "abort_documented", "blocked"
        else:
            status, risk = "manual_review_required", None
        with self.conn.cursor() as cur:
            if risk is None:
                cur.execute(
                    "update employer_origin_source_candidates set status = %s, updated_at = now() where id = %s",
                    (status, candidate_id),
                )
            else:
                cur.execute(
                    "update employer_origin_source_candidates set status = %s, risk_level = %s, updated_at = now() where id = %s",
                    (status, risk, candidate_id),
                )
        self.conn.commit()


def gate_passed(gates: Mapping[str, Mapping[str, Any]], gate_name: str) -> bool:
    gate = gates.get(gate_name)
    return bool(gate and gate.get("gate_status") == "passed")


def _gate_args(candidate: Candidate, args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        candidate_url=candidate.candidate_url,
        source_name_candidate=candidate.source_name_candidate,
        source_family_candidate=candidate.source_family_candidate,
        source_target_candidate=candidate.source_target_candidate,
        source_type_candidate=candidate.source_type_candidate,
        target_location=args.target_location,
        profile_terms=args.profile_terms,
        max_listing_pages=1,
        max_preview_links=args.max_preview_links,
    )


def supported_detail_candidates_from_evidence(
    gate: Mapping[str, Any] | None,
) -> list[DetailCandidate]:
    if not gate or gate.get("gate_status") != "passed":
        return []
    evidence = gate.get("evidence")
    if not isinstance(evidence, Mapping):
        return []
    rows = (
        evidence.get("supported_detail_evidence")
        or evidence.get("supported_details")
        or evidence.get("details")
        or []
    )
    result: list[DetailCandidate] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        url = str(raw.get("final_url") or raw.get("url") or "").strip()
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        profile_hits = tuple(str(item) for item in (raw.get("profile_terms") or raw.get("profile_hits") or []) if str(item))
        location_hits = tuple(str(item) for item in (raw.get("location_terms") or raw.get("location_hits") or []) if str(item))
        if not profile_hits or not location_hits:
            continue
        seen.add(url)
        result.append(
            DetailCandidate(
                url=url,
                title=str(raw.get("title") or ""),
                status_code=int(raw.get("status_code") or 200),
                response_bytes=int(raw.get("html_bytes") or raw.get("response_bytes") or 0),
                profile_hits=profile_hits,
                location_hits=location_hits,
                remote_hits=(),
                text_sample="",
            )
        )
    return result


def _record_and_stop_if_needed(
    repo: Repository,
    *,
    candidate_id: int,
    outcome: GateOutcome,
    reviewed_by: str,
) -> bool:
    repo.record_gate(candidate_id, outcome, reviewed_by)
    print(f"{outcome.gate_name}: {outcome.gate_status} / {outcome.decision}")
    if outcome.gate_status == "passed":
        return False
    repo.update_candidate_stop(candidate_id, outcome)
    print(f"STOP: {outcome.stop_reason}")
    return True


def run_agent(args: argparse.Namespace) -> int:
    load_local_env_file()
    with psycopg.connect(**get_database_config()) as conn:
        repo = Repository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        print(f"candidate_id: {candidate.id}")
        print(f"candidate: {candidate.company_key} | {candidate.source_name_candidate}")
        print("boundary: " + ", ".join(BOUNDARY))
        gate_args = _gate_args(candidate, args)
        gates = repo.load_gates(candidate.id)

        for gate_name, builder in (
            ("company_candidate", lambda: company_candidate_gate(gate_args)),
            ("source_discovery", lambda: source_discovery_gate(gate_args)),
            ("risk_gate", lambda: prefetch_risk_gate(gate_args)),
        ):
            if gate_passed(gates, gate_name):
                continue
            outcome = builder()
            if _record_and_stop_if_needed(
                repo,
                candidate_id=candidate.id,
                outcome=outcome,
                reviewed_by=args.reviewed_by,
            ):
                return 2
            gates = repo.load_gates(candidate.id)

        needs_fetch = any(
            not gate_passed(gates, gate_name)
            for gate_name in ("technical_reachability_gate", "defensive_preview_gate", "relevance_gate")
        )
        fetch = None
        if needs_fetch:
            try:
                fetch = fetch_candidate_page(
                    candidate.candidate_url,
                    timeout_seconds=args.timeout_seconds,
                    max_preview_links=args.max_preview_links,
                    source_family_candidate=candidate.source_family_candidate,
                )
            except requests.RequestException as exc:
                outcome = GateOutcome(
                    gate_name="technical_reachability_gate",
                    gate_status="manual_review_required",
                    decision="manual_review_required",
                    stop_reason=f"bounded candidate fetch failed: {type(exc).__name__}",
                    evidence={"candidate_url": candidate.candidate_url, "error": str(exc)},
                )
                if _record_and_stop_if_needed(
                    repo,
                    candidate_id=candidate.id,
                    outcome=outcome,
                    reviewed_by=args.reviewed_by,
                ):
                    return 2

        if fetch is not None and not gate_passed(gates, "technical_reachability_gate"):
            outcome = technical_reachability_gate(fetch)
            if _record_and_stop_if_needed(
                repo,
                candidate_id=candidate.id,
                outcome=outcome,
                reviewed_by=args.reviewed_by,
            ):
                return 2
            gates = repo.load_gates(candidate.id)

        if fetch is not None and not gate_passed(gates, "risk_gate"):
            risk_after_fetch = postfetch_risk_gate(fetch)
            if risk_after_fetch is not None and _record_and_stop_if_needed(
                repo,
                candidate_id=candidate.id,
                outcome=risk_after_fetch,
                reviewed_by=args.reviewed_by,
            ):
                return 2
            gates = repo.load_gates(candidate.id)

        if not gate_passed(gates, "scope_gate"):
            outcome = scope_gate(gate_args)
            if _record_and_stop_if_needed(
                repo,
                candidate_id=candidate.id,
                outcome=outcome,
                reviewed_by=args.reviewed_by,
            ):
                return 2
            gates = repo.load_gates(candidate.id)

        if fetch is not None and not gate_passed(gates, "defensive_preview_gate"):
            outcome = defensive_preview_gate(fetch)
            if _record_and_stop_if_needed(
                repo,
                candidate_id=candidate.id,
                outcome=outcome,
                reviewed_by=args.reviewed_by,
            ):
                return 2
            gates = repo.load_gates(candidate.id)

        if fetch is not None and not gate_passed(gates, "relevance_gate"):
            outcome = relevance_gate(gate_args, fetch)
            if _record_and_stop_if_needed(
                repo,
                candidate_id=candidate.id,
                outcome=outcome,
                reviewed_by=args.reviewed_by,
            ):
                return 2
            gates = repo.load_gates(candidate.id)

        gates = repo.load_gates(candidate.id)
        remaining_early = [name for name in EARLY_PRECONDITION_GATES if not gate_passed(gates, name)]
        if remaining_early:
            print("STOP: early preconditions remain unpassed: " + ", ".join(remaining_early))
            return 2

        if not gate_passed(gates, DETAIL_EVIDENCE_GATE):
            print("NEXT: detail_evidence_gate is not passed; route to bounded detail-evidence repair.")
            return 0

        if gate_passed(gates, INCREMENTAL_UNIQUENESS_GATE):
            print("NEXT: all connector-candidate preconditions are passed.")
            return 0

        details = supported_detail_candidates_from_evidence(gates.get(DETAIL_EVIDENCE_GATE))
        if not details:
            outcome = GateOutcome(
                gate_name=INCREMENTAL_UNIQUENESS_GATE,
                gate_status="manual_review_required",
                decision="manual_review_required",
                stop_reason="passed detail_evidence_gate contains no authoritative supported detail rows",
                evidence={
                    "detail_gate_status": gates[DETAIL_EVIDENCE_GATE].get("gate_status"),
                    "detail_evidence_keys": sorted((gates[DETAIL_EVIDENCE_GATE].get("evidence") or {}).keys()),
                    "provider_requests": 0,
                },
            )
        else:
            existing = fetch_existing_evidence(
                conn,
                candidate_source_name=candidate.source_name_candidate,
                max_rows_per_table=args.max_evidence_rows,
            )
            outcome = incremental_uniqueness_outcome(details, existing)
            outcome = GateOutcome(
                gate_name=outcome.gate_name,
                gate_status=outcome.gate_status,
                decision=outcome.decision,
                stop_reason=outcome.stop_reason,
                evidence={
                    **outcome.evidence,
                    "evidence_source": "passed_detail_evidence_gate",
                    "detail_evidence_preserved": True,
                    "provider_requests": 0,
                },
            )

        if _record_and_stop_if_needed(
            repo,
            candidate_id=candidate.id,
            outcome=outcome,
            reviewed_by=args.reviewed_by,
        ):
            return 2

        print("NEXT: all connector-candidate preconditions are passed.")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recover canonical preconnector lifecycle gates without provider calls.")
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--profile-term", dest="profile_terms", action="append")
    parser.add_argument("--max-preview-links", type=int, default=25)
    parser.add_argument("--max-evidence-rows", type=int, default=1000)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--reviewed-by", default="preconnector_precondition_agent")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
