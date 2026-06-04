"""Run a bounded relevance-evidence probe for a blocked employer-origin candidate.

Boundary: this agent may fetch the persisted candidate source URL and a small
number of same-/related-host job/search pages. It may update only the
``relevance_gate`` review for the candidate. It does not build/register
connectors, activate sources, write Bronze records, use CSV/export inputs or
change scheduler configuration.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row
import requests

from src.config import get_database_config
from src.search_intelligence.employer_origin_gate_registry import gate_order
from src.search_intelligence.relevance_evidence_probe import (
    RelevanceProbeResult,
    build_probe_url_queue,
    extract_candidate_links,
    extract_json_ld_job_urls,
    job_detail_url_pattern,
    learned_signals_from_result,
    probe_result_from_http_response,
    relevance_confidence,
    relevance_decision,
)

BOUNDARY = {
    "no_connector_artifact_generation": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_bronze_write": True,
    "no_scheduler_change": True,
    "no_csv_or_export_input": True,
    "bounded_relevance_probe": True,
    "autonomous_job_detail_discovery": True,
    "signal_learning_from_accepted_evidence_only": True,
    "uses_promoted_observation_patterns_only": True,
}


@dataclass(frozen=True)
class Candidate:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_url: str
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str


@dataclass(frozen=True)
class PromotedObservationPatterns:
    profile_terms: tuple[str, ...] = ()
    location_terms: tuple[str, ...] = ()
    remote_terms: tuple[str, ...] = ()
    url_path_patterns: tuple[str, ...] = ()

    @property
    def evidence(self) -> dict[str, object]:
        return {
            "profile_terms": list(self.profile_terms),
            "location_terms": list(self.location_terms),
            "remote_terms": list(self.remote_terms),
            "url_path_patterns": list(self.url_path_patterns),
        }


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def load_candidate(conn: psycopg.Connection[Any], company_key: str) -> Candidate:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                company_key,
                company_name,
                candidate_url,
                source_name_candidate,
                source_family_candidate,
                source_target_candidate,
                source_type_candidate
            FROM employer_origin_source_candidates
            WHERE company_key = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (company_key,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"No employer-origin source candidate found for company_key={company_key!r}.")
    return Candidate(
        candidate_id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        candidate_url=str(row["candidate_url"]),
        source_name_candidate=str(row["source_name_candidate"]),
        source_family_candidate=str(row["source_family_candidate"]),
        source_target_candidate=row["source_target_candidate"],
        source_type_candidate=str(row["source_type_candidate"]),
    )


def load_promoted_observation_patterns(conn: psycopg.Connection[Any]) -> PromotedObservationPatterns:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pattern_type, pattern_value, pattern_category, usage_scope
            FROM origin_observed_pattern_candidates
            WHERE promotion_status = 'promoted'
              AND usage_scope IN (
                  'detail_url_discovery',
                  'listing_url_discovery',
                  'relevance_profile',
                  'relevance_location',
                  'relevance_remote'
              )
            ORDER BY usage_scope, pattern_type, pattern_value
            """
        )
        rows = cur.fetchall()

    grouped: dict[str, list[str]] = {
        "profile_terms": [],
        "location_terms": [],
        "remote_terms": [],
        "url_path_patterns": [],
    }
    for row in rows:
        usage_scope = str(row["usage_scope"] or "")
        value = str(row["pattern_value"] or "").strip()
        if not value:
            continue
        if usage_scope == "relevance_profile" and value not in grouped["profile_terms"]:
            grouped["profile_terms"].append(value)
        elif usage_scope == "relevance_location" and value not in grouped["location_terms"]:
            grouped["location_terms"].append(value)
        elif usage_scope == "relevance_remote" and value not in grouped["remote_terms"]:
            grouped["remote_terms"].append(value)
        elif usage_scope in {"detail_url_discovery", "listing_url_discovery"} and value not in grouped["url_path_patterns"]:
            grouped["url_path_patterns"].append(value)

    return PromotedObservationPatterns(
        profile_terms=tuple(grouped["profile_terms"]),
        location_terms=tuple(grouped["location_terms"]),
        remote_terms=tuple(grouped["remote_terms"]),
        url_path_patterns=tuple(grouped["url_path_patterns"]),
    )


def fetch_text(url: str, *, timeout_seconds: float) -> str:
    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            headers={
                "User-Agent": "job-application-pipeline-relevance-evidence-probe/0.1 (+bounded personal portfolio project)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            allow_redirects=True,
        )
    except requests.RequestException:
        return ""
    return response.text or ""


def fetch_response(url: str, *, timeout_seconds: float) -> requests.Response | None:
    try:
        return requests.get(
            url,
            timeout=timeout_seconds,
            headers={
                "User-Agent": "job-application-pipeline-autonomous-relevance-discovery/0.1 (+bounded personal portfolio project)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            allow_redirects=True,
        )
    except requests.RequestException:
        return None


def http_probe(
    url: str,
    *,
    timeout_seconds: float,
    target_location: str,
    source_target: str | None,
    promoted_patterns: PromotedObservationPatterns,
) -> RelevanceProbeResult:
    response = fetch_response(url, timeout_seconds=timeout_seconds)
    if response is None:
        return RelevanceProbeResult(
            url=url,
            final_url=None,
            status_code=None,
            accepted=False,
            reason="request failed",
            signals=probe_result_from_http_response(
                url,
                type("EmptyResponse", (), {"status_code": 0, "url": url, "text": "", "content": b""})(),
                target_location=target_location,
                source_target=source_target,
                promoted_profile_terms=promoted_patterns.profile_terms,
                promoted_location_terms=promoted_patterns.location_terms,
                promoted_remote_terms=promoted_patterns.remote_terms,
            ).signals,
        )
    return probe_result_from_http_response(
        url,
        response,
        target_location=target_location,
        source_target=source_target,
        promoted_profile_terms=promoted_patterns.profile_terms,
        promoted_location_terms=promoted_patterns.location_terms,
        promoted_remote_terms=promoted_patterns.remote_terms,
    )


def autonomous_probe(
    initial_urls: tuple[str, ...],
    *,
    candidate: Candidate,
    timeout_seconds: float,
    target_location: str,
    max_probe_urls: int,
    promoted_patterns: PromotedObservationPatterns,
) -> tuple[RelevanceProbeResult | None, tuple[RelevanceProbeResult, ...]]:
    """Probe URLs and expand bounded job-detail links from fetched pages.

    This is intentionally breadth-limited: the agent may learn from heterogenous
    job/search pages, but it must not become an uncontrolled crawler.
    """

    queue = list(initial_urls)
    seen = set(queue)
    results: list[RelevanceProbeResult] = []
    index = 0

    while index < len(queue) and len(results) < max_probe_urls:
        url = queue[index]
        index += 1

        response = fetch_response(url, timeout_seconds=timeout_seconds)
        if response is None:
            result = http_probe(
                url,
                timeout_seconds=timeout_seconds,
                target_location=target_location,
                source_target=candidate.source_target_candidate,
                promoted_patterns=promoted_patterns,
            )
            results.append(result)
            continue

        result = probe_result_from_http_response(
            url,
            response,
            target_location=target_location,
            source_target=candidate.source_target_candidate,
            promoted_profile_terms=promoted_patterns.profile_terms,
            promoted_location_terms=promoted_patterns.location_terms,
            promoted_remote_terms=promoted_patterns.remote_terms,
        )
        results.append(result)
        if result.accepted:
            return result, tuple(results)

        body = response.text or ""
        discovered = (
            extract_json_ld_job_urls(base_url=result.final_url or url, body=body, max_links=max_probe_urls)
            + extract_candidate_links(
                base_url=result.final_url or url,
                body=body,
                source_family_candidate=candidate.source_family_candidate,
                company_key=candidate.company_key,
                max_links=max_probe_urls,
            )
        )
        for discovered_url in discovered:
            if len(seen) >= max_probe_urls * 3:
                break
            if discovered_url not in seen:
                seen.add(discovered_url)
                from src.search_intelligence.relevance_evidence_probe import is_probable_job_detail_url

                if is_probable_job_detail_url(discovered_url):
                    queue.insert(index, discovered_url)
                else:
                    queue.append(discovered_url)

    return None, tuple(results)


def _serialized_results(results: tuple[RelevanceProbeResult, ...]) -> list[dict[str, object]]:
    serialized: list[dict[str, object]] = []
    for result in results:
        payload = asdict(result)
        serialized.append(payload)
    return serialized


def _json_array(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), sort_keys=True)


def persist_autonomous_job_detail_evidence(
    cur: psycopg.Cursor[Any],
    *,
    candidate: Candidate,
    result: RelevanceProbeResult,
    reviewed_by: str,
) -> None:
    pattern = job_detail_url_pattern(result.final_url or result.url)
    evidence = {
        "agent": "run_employer_origin_relevance_evidence_probe_agent",
        "boundary": BOUNDARY,
        "source_url": result.url,
        "final_url": result.final_url,
        "reason": result.reason,
        "signals": asdict(result.signals),
    }
    cur.execute(
        """
        INSERT INTO employer_origin_job_detail_evidence (
            candidate_id,
            company_key,
            source_url,
            final_url,
            evidence_host,
            path_pattern,
            status_code,
            page_title,
            profile_hits,
            location_hits,
            remote_hits,
            flexibility_hits,
            relevance_decision,
            confidence,
            reason,
            evidence,
            discovered_by,
            reviewed_by,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
            %s, %s, %s, %s::jsonb, %s, %s, now()
        )
        ON CONFLICT (candidate_id, source_url)
        DO UPDATE SET
            final_url = EXCLUDED.final_url,
            evidence_host = EXCLUDED.evidence_host,
            path_pattern = EXCLUDED.path_pattern,
            status_code = EXCLUDED.status_code,
            page_title = EXCLUDED.page_title,
            profile_hits = EXCLUDED.profile_hits,
            location_hits = EXCLUDED.location_hits,
            remote_hits = EXCLUDED.remote_hits,
            flexibility_hits = EXCLUDED.flexibility_hits,
            relevance_decision = EXCLUDED.relevance_decision,
            confidence = EXCLUDED.confidence,
            reason = EXCLUDED.reason,
            evidence = EXCLUDED.evidence,
            discovered_by = EXCLUDED.discovered_by,
            reviewed_by = EXCLUDED.reviewed_by,
            updated_at = now()
        """,
        (
            candidate.candidate_id,
            candidate.company_key,
            result.url,
            result.final_url,
            pattern.get("host"),
            pattern.get("path_pattern"),
            result.status_code,
            result.title,
            _json_array(result.signals.profile_hits),
            _json_array(result.signals.location_hits),
            _json_array(result.signals.remote_hits),
            _json_array(result.signals.flexibility_hits),
            relevance_decision(result.signals),
            relevance_confidence(result.signals),
            result.reason,
            json.dumps(evidence, sort_keys=True),
            "autonomous_relevance_discovery",
            reviewed_by,
        ),
    )


def persist_learned_relevance_signals(
    cur: psycopg.Cursor[Any],
    *,
    candidate: Candidate,
    result: RelevanceProbeResult,
    reviewed_by: str,
) -> None:
    pattern = job_detail_url_pattern(result.final_url or result.url)
    for signal in learned_signals_from_result(result):
        evidence = {
            "agent": "run_employer_origin_relevance_evidence_probe_agent",
            "reviewed_by": reviewed_by,
            "source_url": result.url,
            "final_url": result.final_url,
            "reason": signal.reason,
            "boundary": BOUNDARY,
        }
        cur.execute(
            """
            INSERT INTO employer_origin_learned_relevance_signals (
                signal_type,
                signal_value,
                signal_strength,
                confidence,
                company_key,
                source_family,
                evidence_host,
                path_pattern,
                first_seen_candidate_id,
                last_seen_candidate_id,
                evidence_count,
                evidence,
                learned_by,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s::jsonb, %s, now())
            ON CONFLICT (
                signal_type,
                signal_value,
                company_key,
                evidence_host,
                path_pattern
            )
            DO UPDATE SET
                signal_strength = EXCLUDED.signal_strength,
                confidence = GREATEST(employer_origin_learned_relevance_signals.confidence, EXCLUDED.confidence),
                last_seen_candidate_id = EXCLUDED.last_seen_candidate_id,
                evidence_count = employer_origin_learned_relevance_signals.evidence_count + 1,
                evidence = EXCLUDED.evidence,
                learned_by = EXCLUDED.learned_by,
                updated_at = now()
            """,
            (
                signal.signal_type,
                signal.signal_value,
                signal.signal_strength,
                signal.confidence,
                candidate.company_key or "",
                candidate.source_family_candidate or "",
                pattern.get("host") or "",
                pattern.get("path_pattern") or "",
                candidate.candidate_id,
                candidate.candidate_id,
                json.dumps(evidence, sort_keys=True),
                "autonomous_relevance_discovery",
            ),
        )


def record_relevance_result(
    conn: psycopg.Connection[Any],
    *,
    candidate: Candidate,
    selected: RelevanceProbeResult | None,
    probe_results: tuple[RelevanceProbeResult, ...],
    target_location: str,
    reviewed_by: str,
) -> None:
    if selected is not None:
        gate_status = "passed"
        decision = "passed"
        stop_reason = None
        evidence = {
            "probe_agent": "run_employer_origin_relevance_evidence_probe_agent",
            "decision": "relevance_evidence_found",
            "candidate_url": candidate.candidate_url,
            "selected_evidence_url": selected.final_url or selected.url,
            "selected_signals": asdict(selected.signals),
            "target_location": target_location,
            "boundary": BOUNDARY,
            "probe_results": _serialized_results(probe_results),
        }
        candidate_status = "discovery"
        note = "Relevance evidence passed by bounded A1f relevance probe."
    else:
        gate_status = "manual_review_required"
        decision = "manual_review_required"
        stop_reason = "bounded relevance evidence probe found no target-location or remote/Germany-wide detail evidence"
        evidence = {
            "probe_agent": "run_employer_origin_relevance_evidence_probe_agent",
            "decision": "no_relevance_evidence_found",
            "candidate_url": candidate.candidate_url,
            "target_location": target_location,
            "boundary": BOUNDARY,
            "probe_results": _serialized_results(probe_results),
        }
        candidate_status = "manual_review_required"
        note = "Relevance evidence probe requires manual review."

    with conn.cursor() as cur:
        for result in probe_results:
            persist_autonomous_job_detail_evidence(cur, candidate=candidate, result=result, reviewed_by=reviewed_by)
        if selected is not None:
            persist_learned_relevance_signals(cur, candidate=candidate, result=selected, reviewed_by=reviewed_by)

        cur.execute(
            """
            INSERT INTO employer_origin_candidate_gate_reviews (
                candidate_id,
                gate_name,
                gate_order,
                gate_status,
                decision,
                is_hard_gate,
                stop_reason,
                evidence,
                reviewed_at,
                reviewed_by,
                updated_at
            )
            VALUES (
                %s,
                'relevance_gate',
                %s,
                %s,
                %s,
                true,
                %s,
                %s::jsonb,
                now(),
                %s,
                now()
            )
            ON CONFLICT (candidate_id, gate_name)
            DO UPDATE SET
                gate_status = EXCLUDED.gate_status,
                decision = EXCLUDED.decision,
                stop_reason = EXCLUDED.stop_reason,
                evidence = EXCLUDED.evidence,
                reviewed_at = EXCLUDED.reviewed_at,
                reviewed_by = EXCLUDED.reviewed_by,
                updated_at = now()
            """,
            (
                candidate.candidate_id,
                gate_order("relevance_gate"),
                gate_status,
                decision,
                stop_reason,
                json.dumps(evidence, sort_keys=True),
                reviewed_by,
            ),
        )
        cur.execute(
            """
            UPDATE employer_origin_source_candidates
            SET status = %s,
                notes = concat_ws(' ', nullif(notes, ''), %s::text),
                updated_at = now()
            WHERE id = %s
            """,
            (candidate_status, f"{note} reviewed_by={reviewed_by}.", candidate.candidate_id),
        )
    conn.commit()


def run(args: argparse.Namespace) -> int:
    with connect() as conn:
        candidate = load_candidate(conn, args.company_key)
        promoted_patterns = load_promoted_observation_patterns(conn)

    initial_body = fetch_text(candidate.candidate_url, timeout_seconds=args.timeout_seconds)
    probe_urls = build_probe_url_queue(
        candidate_url=candidate.candidate_url,
        initial_body=initial_body,
        source_family_candidate=candidate.source_family_candidate,
        company_key=candidate.company_key,
        max_links=args.max_probe_urls,
        promoted_url_path_patterns=promoted_patterns.url_path_patterns,
    )
    selected, probe_results = autonomous_probe(
        probe_urls,
        candidate=candidate,
        timeout_seconds=args.timeout_seconds,
        target_location=args.target_location,
        max_probe_urls=args.max_probe_urls,
        promoted_patterns=promoted_patterns,
    )

    print(f"candidate_id: {candidate.candidate_id}")
    print(f"company_key: {candidate.company_key}")
    print(f"candidate_url: {candidate.candidate_url}")
    print(f"autonomous_relevance_discovery_url_count: {len(probe_urls)}")
    for result in probe_results:
        signals = result.signals
        print(
            "probe: "
            f"{result.url} | accepted={result.accepted} | reason={result.reason} | "
            f"profile={list(signals.profile_hits)} | location={list(signals.location_hits)} | remote={list(signals.remote_hits)}"
        )

    with connect() as conn:
        record_relevance_result(
            conn,
            candidate=candidate,
            selected=selected,
            probe_results=probe_results,
            target_location=args.target_location,
            reviewed_by=args.reviewed_by,
        )

    if selected is not None:
        print(f"selected_relevance_evidence_url: {selected.final_url or selected.url}")
        print("autonomous_relevance_discovery_result: passed")
    else:
        print("autonomous_relevance_discovery_result: manual_review_required")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bounded relevance-evidence probing for a blocked employer-origin candidate.")
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--max-probe-urls", type=int, default=8)
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
