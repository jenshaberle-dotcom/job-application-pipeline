from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row
import requests

from scripts.run_employer_origin_gate_agent import (
    DEFAULT_PROFILE_TERMS,
    DEFAULT_REMOTE_TERMS,
    FetchResult,
    GateOutcome,
    count_term_hits,
    fetch_candidate_page,
    parse_same_domain_job_links,
)


def row_value(row, key: str, index: int):
    """Read a psycopg row safely regardless of tuple or dict row shape."""
    try:
        return row[key]
    except (KeyError, TypeError):
        return row[index]


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: str
    dbname: str
    user: str
    password: str

    @classmethod
    def from_environment(cls) -> "DatabaseConfig":
        return cls(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        )

    def dsn(self) -> str:
        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.dbname} "
            f"user={self.user} "
            f"password={self.password}"
        )


@dataclass(frozen=True)
class SourceCandidate:
    id: int
    company_key: str
    company_name: str
    candidate_url: str
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str


@dataclass(frozen=True)
class DetailCandidate:
    url: str
    title: str
    status_code: int
    response_bytes: int
    profile_hits: tuple[str, ...]
    location_hits: tuple[str, ...]
    remote_hits: tuple[str, ...]
    text_sample: str


@dataclass(frozen=True)
class ExistingEvidence:
    table_name: str
    record_id: int | None
    source_name: str
    title: str
    company_name: str
    location: str
    source_url: str
    evidence_text: str


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.casefold()).strip()


def url_slug_title(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if not path:
        return ""
    slug = path.split("/")[-1]
    return re.sub(r"[-_]+", " ", slug).strip()


def title_similarity(left: str, right: str) -> float:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm or not right_norm:
        return 0.0
    return round(SequenceMatcher(None, left_norm, right_norm).ratio(), 3)


def token_set(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-ZäöüÄÖÜß0-9]{3,}", normalize_text(value))
        if token
    }


def evidence_similarity(left: str, right: str) -> float:
    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return round(len(left_tokens & right_tokens) / len(left_tokens | right_tokens), 3)


def extract_detail_candidates(
    fetches: list[FetchResult],
    *,
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
) -> list[DetailCandidate]:
    candidates: list[DetailCandidate] = []

    for fetch in fetches:
        title = fetch.title or url_slug_title(fetch.final_url)
        profile_hits = tuple(count_term_hits(fetch.text, profile_terms))
        location_hits = tuple(count_term_hits(fetch.text, location_terms))
        remote_hits = tuple(count_term_hits(fetch.text, DEFAULT_REMOTE_TERMS))

        text_sample = re.sub(r"\s+", " ", fetch.text[:2000]).strip()

        candidates.append(
            DetailCandidate(
                url=fetch.final_url,
                title=title,
                status_code=fetch.status_code,
                response_bytes=fetch.response_bytes,
                profile_hits=profile_hits,
                location_hits=location_hits,
                remote_hits=remote_hits,
                text_sample=text_sample,
            )
        )

    return candidates


def detail_evidence_outcome(details: list[DetailCandidate]) -> GateOutcome:
    supported = [
        detail
        for detail in details
        if detail.status_code >= 200
        and detail.status_code < 400
        and detail.profile_hits
        and (detail.location_hits or detail.remote_hits)
    ]

    evidence = {
        "detail_pages_requested": len(details),
        "supported_detail_candidates": len(supported),
        "details": [
            {
                "url": detail.url,
                "title": detail.title,
                "status_code": detail.status_code,
                "response_bytes": detail.response_bytes,
                "profile_hits": list(detail.profile_hits),
                "location_hits": list(detail.location_hits),
                "remote_hits": list(detail.remote_hits),
            }
            for detail in details
        ],
    }

    if not supported:
        return GateOutcome(
            gate_name="detail_evidence_gate",
            gate_status="manual_review_required",
            decision="manual_review_required",
            stop_reason="bounded detail fetch did not confirm profile plus target-location/remote evidence",
            evidence=evidence,
        )

    return GateOutcome(
        gate_name="detail_evidence_gate",
        gate_status="passed",
        decision="passed",
        stop_reason=None,
        evidence=evidence,
    )


def value_from_raw_data(raw_data: Any, *keys: str) -> str:
    if not isinstance(raw_data, dict):
        return ""
    for key in keys:
        value = raw_data.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def evidence_from_raw_job(row: dict[str, Any]) -> ExistingEvidence:
    raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
    title = value_from_raw_data(raw_data, "title", "job_title", "name")
    company = value_from_raw_data(raw_data, "company_name", "company", "employer")
    location = value_from_raw_data(raw_data, "location", "city", "workplace")
    url = value_from_raw_data(raw_data, "url", "source_url", "detail_url", "external_url", "application_url")

    evidence_text = " ".join(
        str(value)
        for value in [
            title,
            company,
            location,
            url,
            row.get("source_name") or "",
            json.dumps(raw_data, ensure_ascii=False, default=str)[:3000],
        ]
        if value
    )

    return ExistingEvidence(
        table_name="raw_jobs",
        record_id=row.get("id"),
        source_name=str(row.get("source_name") or ""),
        title=title,
        company_name=company,
        location=location,
        source_url=url,
        evidence_text=evidence_text,
    )


def evidence_from_silver_job(row: dict[str, Any]) -> ExistingEvidence:
    title = str(row.get("title") or row.get("job_title") or row.get("name") or "")
    company = str(row.get("company_name") or row.get("company") or "")
    location = str(row.get("location") or row.get("city") or "")
    source_url = str(row.get("source_url") or row.get("url") or row.get("detail_url") or "")
    source_name = str(row.get("source_name") or "")

    compact = {
        key: value
        for key, value in row.items()
        if key in {
            "title",
            "job_title",
            "company_name",
            "company",
            "location",
            "city",
            "source_url",
            "url",
            "detail_url",
            "source_name",
            "canonical_source_type",
        }
    }

    return ExistingEvidence(
        table_name="silver_jobs",
        record_id=row.get("id"),
        source_name=source_name,
        title=title,
        company_name=company,
        location=location,
        source_url=source_url,
        evidence_text=json.dumps(compact, ensure_ascii=False, default=str),
    )


def table_exists(conn: psycopg.Connection[Any], table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            select exists (
                select 1
                from information_schema.tables
                where table_schema = 'public'
                  and table_name = %s
            )
            """,
            (table_name,),
        )
        row = cur.fetchone()
        return bool(row_value(row, "exists", 0))


def fetch_existing_evidence(
    conn: psycopg.Connection[Any],
    *,
    candidate_source_name: str,
    max_rows_per_table: int,
) -> list[ExistingEvidence]:
    evidence: list[ExistingEvidence] = []

    if table_exists(conn, "raw_jobs"):
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select *
                from raw_jobs
                where source_name <> %s
                order by id desc
                limit %s
                """,
                (candidate_source_name, max_rows_per_table),
            )
            evidence.extend(evidence_from_raw_job(dict(row)) for row in cur.fetchall())

    if table_exists(conn, "silver_jobs"):
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select *
                from silver_jobs
                where source_name <> %s
                order by id desc
                limit %s
                """,
                (candidate_source_name, max_rows_per_table),
            )
            evidence.extend(evidence_from_silver_job(dict(row)) for row in cur.fetchall())

    return evidence


def classify_detail_candidate(detail: DetailCandidate, existing: list[ExistingEvidence]) -> dict[str, Any]:
    best: dict[str, Any] | None = None

    candidate_text = " ".join(
        [
            detail.title,
            detail.url,
            " ".join(detail.profile_hits),
            " ".join(detail.location_hits),
            " ".join(detail.remote_hits),
            detail.text_sample,
        ]
    )

    for row in existing:
        url_match = bool(detail.url and row.source_url and detail.url == row.source_url)
        title_score = title_similarity(detail.title, row.title)
        evidence_score = evidence_similarity(candidate_text, row.evidence_text)

        score = max(title_score, evidence_score, 1.0 if url_match else 0.0)
        if best is None or score > best["score"]:
            best = {
                "score": score,
                "table_name": row.table_name,
                "record_id": row.record_id,
                "source_name": row.source_name,
                "title": row.title,
                "company_name": row.company_name,
                "location": row.location,
                "source_url": row.source_url,
                "exact_url_match": url_match,
                "title_similarity": title_score,
                "evidence_similarity": evidence_score,
            }

    if best is None:
        return {
            "candidate_url": detail.url,
            "candidate_title": detail.title,
            "uniqueness_decision": "incrementally_unique_candidate",
            "reason": "No existing raw/Silver evidence was available for comparison.",
            "best_match": None,
        }

    same_company_hint = "finanz" in normalize_text(best["company_name"]) or "hdi" in normalize_text(best["company_name"])
    if best["exact_url_match"] or (best["title_similarity"] >= 0.88 and same_company_hint):
        decision = "known_duplicate_or_low_incremental_value"
        reason = "Candidate strongly overlaps with existing evidence."
    elif best["title_similarity"] >= 0.6 or best["evidence_similarity"] >= 0.12:
        decision = "possible_known_elsewhere_review"
        reason = "Candidate has partial overlap with existing evidence and needs manual review."
    else:
        decision = "incrementally_unique_candidate"
        reason = "No sufficiently similar existing evidence was found."

    return {
        "candidate_url": detail.url,
        "candidate_title": detail.title,
        "uniqueness_decision": decision,
        "reason": reason,
        "best_match": best,
    }


def incremental_uniqueness_outcome(
    details: list[DetailCandidate],
    existing: list[ExistingEvidence],
) -> GateOutcome:
    supported_details = [
        detail
        for detail in details
        if detail.profile_hits and (detail.location_hits or detail.remote_hits)
    ]

    results = [
        classify_detail_candidate(detail, existing)
        for detail in supported_details
    ]
    counts = Counter(result["uniqueness_decision"] for result in results)

    evidence = {
        "detail_candidates_considered": len(supported_details),
        "existing_evidence_rows_considered": len(existing),
        "uniqueness_counts": dict(sorted(counts.items())),
        "results": results,
    }

    if not supported_details:
        return GateOutcome(
            gate_name="incremental_uniqueness_gate",
            gate_status="manual_review_required",
            decision="manual_review_required",
            stop_reason="no supported detail candidates available for uniqueness comparison",
            evidence=evidence,
        )

    if counts.get("incrementally_unique_candidate", 0) > 0:
        return GateOutcome(
            gate_name="incremental_uniqueness_gate",
            gate_status="passed",
            decision="passed",
            stop_reason=None,
            evidence=evidence,
        )

    return GateOutcome(
        gate_name="incremental_uniqueness_gate",
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="candidate details need manual overlap review before connector-candidate gate",
        evidence=evidence,
    )


class GateStateRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_candidate(self, *, candidate_id: int | None, company_key: str | None) -> SourceCandidate:
        if candidate_id is None and not company_key:
            raise ValueError("Either candidate_id or company_key is required.")

        with self.conn.cursor(row_factory=dict_row) as cur:
            if candidate_id is not None:
                cur.execute(
                    """
                    select *
                    from employer_origin_source_candidates
                    where id = %s
                    """,
                    (candidate_id,),
                )
            else:
                cur.execute(
                    """
                    select *
                    from employer_origin_source_candidates
                    where company_key = %s
                    order by id desc
                    limit 1
                    """,
                    (company_key,),
                )
            row = cur.fetchone()

        if row is None:
            raise ValueError("No employer-origin source candidate found.")

        return SourceCandidate(
            id=int(row["id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            candidate_url=str(row["candidate_url"]),
            source_name_candidate=str(row["source_name_candidate"]),
            source_family_candidate=str(row["source_family_candidate"]),
            source_target_candidate=row.get("source_target_candidate"),
            source_type_candidate=str(row["source_type_candidate"]),
        )

    def load_preview_links_from_gate_evidence(self, candidate_id: int) -> list[str]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select evidence
                from employer_origin_candidate_gate_reviews
                where candidate_id = %s
                  and gate_name = 'defensive_preview_gate'
                """,
                (candidate_id,),
            )
            row = cur.fetchone()

        evidence = dict(row["evidence"] or {}) if row else {}
        links = evidence.get("sample_links") or []
        return [str(link) for link in links if str(link).startswith(("http://", "https://"))]

    def record_gate(self, candidate_id: int, outcome: GateOutcome, reviewed_by: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                select id, gate_status, decision, stop_reason, evidence
                from employer_origin_candidate_gate_reviews
                where candidate_id = %s
                  and gate_name = %s
                """,
                (candidate_id, outcome.gate_name),
            )
            previous = cur.fetchone()
            if previous is None:
                raise ValueError(f"Missing gate {outcome.gate_name} for candidate_id={candidate_id}")

            previous_state = {
                "id": row_value(previous, "id", 0),
                "gate_status": row_value(previous, "gate_status", 1),
                "decision": row_value(previous, "decision", 2),
                "stop_reason": row_value(previous, "stop_reason", 3),
                "evidence": row_value(previous, "evidence", 4),
            }

            cur.execute(
                """
                update employer_origin_candidate_gate_reviews
                set
                    gate_status = %s,
                    decision = %s,
                    stop_reason = %s,
                    evidence = %s::jsonb,
                    reviewed_at = now(),
                    reviewed_by = %s,
                    updated_at = now()
                where candidate_id = %s
                  and gate_name = %s
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
            gate_review_row = cur.fetchone()
            gate_review_id = int(row_value(gate_review_row, "id", 0))

            cur.execute(
                """
                insert into employer_origin_candidate_gate_events (
                    candidate_id,
                    gate_review_id,
                    event_type,
                    previous_state,
                    new_state,
                    event_reason,
                    created_by
                )
                values (%s, %s, 'gate_updated', %s::jsonb, %s::jsonb, %s, %s)
                """,
                (
                    candidate_id,
                    gate_review_id,
                    json.dumps(previous_state, default=str, ensure_ascii=False),
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
                    "detail-evidence and incremental-uniqueness gate-agent run",
                    reviewed_by,
                ),
            )

        self.conn.commit()

    def update_candidate_status(self, candidate_id: int, status: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                update employer_origin_source_candidates
                set status = %s,
                    updated_at = now()
                where id = %s
                """,
                (status, candidate_id),
            )
        self.conn.commit()


def build_detail_urls(
    candidate: SourceCandidate,
    preview_links: list[str],
    explicit_urls: list[str] | None,
    max_detail_pages: int,
) -> list[str]:
    urls = list(explicit_urls or [])
    if not urls:
        urls = preview_links

    if not urls:
        urls = parse_same_domain_job_links(
            requested_url=candidate.candidate_url,
            final_url=candidate.candidate_url,
            body=requests.get(candidate.candidate_url, timeout=20).text,
            max_links=max_detail_pages,
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        clean = str(url).split("#", 1)[0]
        if clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
        if len(deduped) >= max_detail_pages:
            break

    return deduped


def fetch_detail_pages(urls: list[str], timeout_seconds: int) -> list[FetchResult]:
    fetches: list[FetchResult] = []
    for url in urls:
        fetches.append(fetch_candidate_page(url, timeout_seconds=timeout_seconds, max_preview_links=10))
    return fetches


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = GateStateRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        print(f"candidate_id: {candidate.id}")
        print(f"candidate: {candidate.company_key} | {candidate.source_name_candidate}")

        preview_links = repo.load_preview_links_from_gate_evidence(candidate.id)
        detail_urls = build_detail_urls(
            candidate,
            preview_links=preview_links,
            explicit_urls=args.detail_url,
            max_detail_pages=args.max_detail_pages,
        )

        if not detail_urls:
            outcome = GateOutcome(
                gate_name="detail_evidence_gate",
                gate_status="manual_review_required",
                decision="manual_review_required",
                stop_reason="no detail URLs available from preview gate or explicit arguments",
                evidence={"detail_urls": []},
            )
            repo.record_gate(candidate.id, outcome, args.reviewed_by)
            repo.update_candidate_status(candidate.id, "manual_review_required")
            print(f"{outcome.gate_name}: {outcome.gate_status} / {outcome.decision}")
            print(f"STOP: {outcome.stop_reason}")
            return 0

        try:
            fetches = fetch_detail_pages(detail_urls, timeout_seconds=args.timeout_seconds)
        except requests.RequestException as exc:
            outcome = GateOutcome(
                gate_name="detail_evidence_gate",
                gate_status="manual_review_required",
                decision="manual_review_required",
                stop_reason=f"detail request failed: {exc.__class__.__name__}",
                evidence={"detail_urls": detail_urls, "error": str(exc)},
            )
            repo.record_gate(candidate.id, outcome, args.reviewed_by)
            repo.update_candidate_status(candidate.id, "manual_review_required")
            print(f"{outcome.gate_name}: {outcome.gate_status} / {outcome.decision}")
            print(f"STOP: {outcome.stop_reason}")
            return 0

        profile_terms = tuple(args.profile_terms or DEFAULT_PROFILE_TERMS)
        location_terms = tuple(
            term for term in (args.target_location, candidate.source_target_candidate) if term
        )
        details = extract_detail_candidates(
            fetches,
            profile_terms=profile_terms,
            location_terms=location_terms,
        )

        detail_outcome = detail_evidence_outcome(details)
        repo.record_gate(candidate.id, detail_outcome, args.reviewed_by)
        print(f"{detail_outcome.gate_name}: {detail_outcome.gate_status} / {detail_outcome.decision}")

        if detail_outcome.gate_status != "passed":
            repo.update_candidate_status(candidate.id, "manual_review_required")
            print(f"STOP: {detail_outcome.stop_reason}")
            return 0

        existing = fetch_existing_evidence(
            conn,
            candidate_source_name=candidate.source_name_candidate,
            max_rows_per_table=args.max_evidence_rows,
        )

        uniqueness_outcome = incremental_uniqueness_outcome(details, existing)
        repo.record_gate(candidate.id, uniqueness_outcome, args.reviewed_by)
        print(f"{uniqueness_outcome.gate_name}: {uniqueness_outcome.gate_status} / {uniqueness_outcome.decision}")

        if uniqueness_outcome.gate_status == "passed":
            repo.update_candidate_status(candidate.id, "connector_candidate")
            print("NEXT: connector_candidate_gate is now eligible for manual or agent-assisted review.")
        else:
            repo.update_candidate_status(candidate.id, "manual_review_required")
            print(f"STOP: {uniqueness_outcome.stop_reason}")

        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run detail-evidence and incremental-uniqueness gates for employer-origin candidates."
    )
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")

    parser.add_argument("--detail-url", action="append")
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--profile-term", dest="profile_terms", action="append")
    parser.add_argument("--max-detail-pages", type=int, default=3)
    parser.add_argument("--max-evidence-rows", type=int, default=1000)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--reviewed-by", default="agent_mvp")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
