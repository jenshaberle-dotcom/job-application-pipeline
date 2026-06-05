from __future__ import annotations

import argparse
import html
import json
import os
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import psycopg
import requests

from scripts.record_employer_origin_gate_review import DEFAULT_GATES
from src.search_intelligence.origin_url_policy import has_disallowed_source_url_shape


DEFAULT_PROFILE_TERMS = (
    "data",
    "daten",
    "analytics",
    "business intelligence",
    "business analyst",
    "bi",
    "sql",
    "python",
    "ki",
    "ai",
    "software",
    "entwickler",
    "product owner",
    "produktverantwort",
)

DEFAULT_REMOTE_TERMS = (
    "remote",
    "mobiles arbeiten",
    "mobile work",
    "homeoffice",
    "home office",
    "hybrid",
)

RISK_BLOCK_TERMS = (
    "captcha",
    "recaptcha",
    "hcaptcha",
    "cloudflare challenge",
    "access denied",
    "bot detection",
)

JOB_LINK_TERMS = (
    "job",
    "jobs",
    "stellen",
    "stellenangebote",
    "offene-stellen",
    "karriere",
    "career",
    "position",
)


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


class LinkAndTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self._inside_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._inside_title = True

        if tag.lower() != "a":
            return

        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(html.unescape(value.strip()))

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title and data.strip():
            self.title_parts.append(data.strip())

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()


@dataclass(frozen=True)
class FetchResult:
    requested_url: str
    final_url: str
    status_code: int
    response_bytes: int
    title: str
    text: str
    same_domain_job_links: tuple[str, ...]


@dataclass(frozen=True)
class GateOutcome:
    gate_name: str
    gate_status: str
    decision: str
    stop_reason: str | None
    evidence: dict[str, Any]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def has_disallowed_url_shape(url: str) -> str | None:
    return has_disallowed_source_url_shape(url)


def _host_tokens(hostname: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", hostname.lower())
        if len(token) >= 3
    }


def _source_tokens(source_family_candidate: str | None) -> set[str]:
    if not source_family_candidate:
        return set()
    generic = {"career", "careers", "source", "origin", "employer", "jobs", "job", "hannover"}
    return {
        token
        for token in re.split(r"[^a-z0-9]+", source_family_candidate.lower())
        if len(token) >= 3 and token not in generic
    }


def _is_allowed_preview_host(
    link_host: str,
    allowed_hosts: set[str],
    source_family_candidate: str | None,
) -> bool:
    normalized_host = link_host.lower()
    if normalized_host in allowed_hosts:
        return True

    tokens = _source_tokens(source_family_candidate)
    if not tokens:
        return False

    return bool(tokens & _host_tokens(normalized_host))


def parse_same_domain_job_links(
    requested_url: str,
    final_url: str,
    body: str,
    max_links: int,
    source_family_candidate: str | None = None,
) -> tuple[str, ...]:
    parser = LinkAndTitleParser()
    parser.feed(body)

    final_host = urlparse(final_url).netloc.lower()
    requested_host = urlparse(requested_url).netloc.lower()
    allowed_hosts = {host for host in (final_host, requested_host) if host}

    links: list[str] = []
    seen: set[str] = set()

    for href in parser.links:
        absolute = urljoin(final_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if not _is_allowed_preview_host(parsed.netloc, allowed_hosts, source_family_candidate):
            continue

        lowered = absolute.lower()
        if not any(term in lowered for term in JOB_LINK_TERMS):
            continue

        clean = absolute.split("#", 1)[0]
        if clean in seen:
            continue

        seen.add(clean)
        links.append(clean)
        if len(links) >= max_links:
            break

    return tuple(links)


def extract_title(body: str) -> str:
    parser = LinkAndTitleParser()
    parser.feed(body)
    return parser.title


def count_term_hits(text: str, terms: tuple[str, ...] | list[str]) -> list[str]:
    normalized = normalize_text(text)
    hits: list[str] = []
    for term in terms:
        normalized_term = normalize_text(term)
        if normalized_term and normalized_term in normalized and term not in hits:
            hits.append(term)
    return hits


def fetch_candidate_page(
    url: str,
    timeout_seconds: int,
    max_preview_links: int,
    source_family_candidate: str | None = None,
) -> FetchResult:
    response = requests.get(
        url,
        timeout=timeout_seconds,
        headers={
            "User-Agent": "job-application-pipeline-source-candidate-agent/0.1 (+bounded-read-only-preview)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    text = response.text or ""
    return FetchResult(
        requested_url=url,
        final_url=response.url,
        status_code=response.status_code,
        response_bytes=len(response.content or b""),
        title=extract_title(text),
        text=text,
        same_domain_job_links=parse_same_domain_job_links(
            requested_url=url,
            final_url=response.url,
            body=text,
            max_links=max_preview_links,
            source_family_candidate=source_family_candidate,
        ),
    )


class GateStateRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def upsert_candidate(
        self,
        *,
        company_key: str,
        company_name: str,
        candidate_url: str,
        source_name_candidate: str,
        source_family_candidate: str,
        source_target_candidate: str | None,
        source_type_candidate: str,
        reviewed_by: str,
    ) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                insert into employer_origin_source_candidates (
                    company_key,
                    company_name,
                    candidate_url,
                    source_name_candidate,
                    source_family_candidate,
                    source_target_candidate,
                    source_type_candidate,
                    status,
                    risk_level,
                    notes
                )
                values (%s, %s, %s, %s, %s, %s, %s, 'discovery', 'unknown', %s)
                on conflict (company_key, candidate_url)
                do update set
                    company_name = excluded.company_name,
                    source_name_candidate = excluded.source_name_candidate,
                    source_family_candidate = excluded.source_family_candidate,
                    source_target_candidate = excluded.source_target_candidate,
                    source_type_candidate = excluded.source_type_candidate,
                    updated_at = now()
                returning id
                """,
                (
                    company_key,
                    company_name,
                    candidate_url,
                    source_name_candidate,
                    source_family_candidate,
                    source_target_candidate,
                    source_type_candidate,
                    "Created or updated by bounded employer-origin gate agent MVP.",
                ),
            )
            candidate_id = int(cur.fetchone()[0])

            for gate_order, gate_name, is_hard_gate in DEFAULT_GATES:
                cur.execute(
                    """
                    insert into employer_origin_candidate_gate_reviews (
                        candidate_id,
                        gate_name,
                        gate_order,
                        is_hard_gate
                    )
                    values (%s, %s, %s, %s)
                    on conflict (candidate_id, gate_name)
                    do nothing
                    """,
                    (candidate_id, gate_name, gate_order, is_hard_gate),
                )

            cur.execute(
                """
                insert into employer_origin_candidate_gate_events (
                    candidate_id,
                    event_type,
                    new_state,
                    event_reason,
                    created_by
                )
                values (%s, 'candidate_created', %s::jsonb, %s, %s)
                """,
                (
                    candidate_id,
                    json.dumps(
                        {
                            "company_key": company_key,
                            "candidate_url": candidate_url,
                            "source_name_candidate": source_name_candidate,
                            "agent_mode": "bounded_gate_agent_mvp",
                        },
                        ensure_ascii=False,
                    ),
                    "upsert candidate for bounded gate-agent run",
                    reviewed_by,
                ),
            )

        self.conn.commit()
        return candidate_id

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
                "id": previous[0],
                "gate_status": previous[1],
                "decision": previous[2],
                "stop_reason": previous[3],
                "evidence": previous[4],
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
            gate_review_id = int(cur.fetchone()[0])

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
                    "bounded gate-agent run",
                    reviewed_by,
                ),
            )

        self.conn.commit()

    def update_candidate_status(self, candidate_id: int, status: str, risk_level: str | None = None) -> None:
        with self.conn.cursor() as cur:
            if risk_level is None:
                cur.execute(
                    """
                    update employer_origin_source_candidates
                    set status = %s,
                        updated_at = now()
                    where id = %s
                    """,
                    (status, candidate_id),
                )
            else:
                cur.execute(
                    """
                    update employer_origin_source_candidates
                    set status = %s,
                        risk_level = %s,
                        updated_at = now()
                    where id = %s
                    """,
                    (status, risk_level, candidate_id),
                )

        self.conn.commit()


def company_candidate_gate(args: argparse.Namespace) -> GateOutcome:
    return GateOutcome(
        gate_name="company_candidate",
        gate_status="passed",
        decision="passed",
        stop_reason=None,
        evidence={
            "company_key": args.company_key,
            "company_name": args.company_name,
            "source_name_candidate": args.source_name_candidate,
        },
    )


def source_discovery_gate(args: argparse.Namespace) -> GateOutcome:
    url_problem = has_disallowed_url_shape(args.candidate_url)
    if url_problem:
        return GateOutcome(
            gate_name="source_discovery",
            gate_status="failed",
            decision="abort_documented",
            stop_reason=url_problem,
            evidence={"candidate_url": args.candidate_url},
        )

    return GateOutcome(
        gate_name="source_discovery",
        gate_status="passed",
        decision="passed",
        stop_reason=None,
        evidence={"candidate_url": args.candidate_url, "finding": "candidate source URL provided and has allowed URL shape"},
    )


def prefetch_risk_gate(args: argparse.Namespace) -> GateOutcome:
    return GateOutcome(
        gate_name="risk_gate",
        gate_status="passed",
        decision="passed",
        stop_reason=None,
        evidence={
            "finding": "pre-fetch risk check passed",
            "rules": ["http/https URL", "no login/auth/sso URL marker"],
        },
    )


def technical_reachability_gate(fetch: FetchResult) -> GateOutcome:
    if fetch.status_code < 200 or fetch.status_code >= 400:
        return GateOutcome(
            gate_name="technical_reachability_gate",
            gate_status="failed",
            decision="abort_documented",
            stop_reason=f"source returned HTTP {fetch.status_code}",
            evidence={
                "requested_url": fetch.requested_url,
                "final_url": fetch.final_url,
                "status_code": fetch.status_code,
                "response_bytes": fetch.response_bytes,
            },
        )

    return GateOutcome(
        gate_name="technical_reachability_gate",
        gate_status="passed",
        decision="passed",
        stop_reason=None,
        evidence={
            "requested_url": fetch.requested_url,
            "final_url": fetch.final_url,
            "status_code": fetch.status_code,
            "response_bytes": fetch.response_bytes,
            "title": fetch.title,
        },
    )


def postfetch_risk_gate(fetch: FetchResult) -> GateOutcome | None:
    normalized = normalize_text(fetch.text[:200_000])
    hits = [term for term in RISK_BLOCK_TERMS if term in normalized]

    if not hits:
        return None

    return GateOutcome(
        gate_name="risk_gate",
        gate_status="failed",
        decision="abort_documented",
        stop_reason="source response contains bot-defense or access-risk markers",
        evidence={"risk_markers": hits, "final_url": fetch.final_url, "status_code": fetch.status_code},
    )


def scope_gate(args: argparse.Namespace) -> GateOutcome:
    if args.max_listing_pages != 1:
        return GateOutcome(
            gate_name="scope_gate",
            gate_status="failed",
            decision="abort_documented",
            stop_reason="agent MVP only supports one listing page per run",
            evidence={"max_listing_pages": args.max_listing_pages},
        )

    return GateOutcome(
        gate_name="scope_gate",
        gate_status="passed",
        decision="passed",
        stop_reason=None,
        evidence={
            "source_name_candidate": args.source_name_candidate,
            "source_family_candidate": args.source_family_candidate,
            "source_target_candidate": args.source_target_candidate,
            "source_type_candidate": args.source_type_candidate,
            "max_listing_pages": args.max_listing_pages,
            "max_preview_links": args.max_preview_links,
        },
    )


def defensive_preview_gate(fetch: FetchResult) -> GateOutcome:
    if not fetch.same_domain_job_links:
        return GateOutcome(
            gate_name="defensive_preview_gate",
            gate_status="manual_review_required",
            decision="manual_review_required",
            stop_reason="no same-domain job-like links found in bounded preview",
            evidence={
                "title": fetch.title,
                "final_url": fetch.final_url,
                "same_domain_job_link_count": 0,
                "response_bytes": fetch.response_bytes,
            },
        )

    return GateOutcome(
        gate_name="defensive_preview_gate",
        gate_status="passed",
        decision="passed",
        stop_reason=None,
        evidence={
            "title": fetch.title,
            "final_url": fetch.final_url,
            "same_domain_job_link_count": len(fetch.same_domain_job_links),
            "sample_links": list(fetch.same_domain_job_links[:5]),
        },
    )


def relevance_gate(args: argparse.Namespace, fetch: FetchResult) -> GateOutcome:
    profile_terms = tuple(args.profile_terms or DEFAULT_PROFILE_TERMS)
    location_terms = tuple(term for term in (args.target_location, args.source_target_candidate) if term)
    profile_hits = count_term_hits(fetch.text, profile_terms)
    location_hits = count_term_hits(fetch.text, location_terms)
    remote_hits = count_term_hits(fetch.text, DEFAULT_REMOTE_TERMS)

    if not profile_hits:
        return GateOutcome(
            gate_name="relevance_gate",
            gate_status="manual_review_required",
            decision="manual_review_required",
            stop_reason="bounded preview did not expose profile-term evidence",
            evidence={
                "profile_hits": profile_hits,
                "location_hits": location_hits,
                "remote_hits": remote_hits,
                "profile_terms_checked": list(profile_terms),
            },
        )

    if not location_hits and not remote_hits:
        return GateOutcome(
            gate_name="relevance_gate",
            gate_status="manual_review_required",
            decision="manual_review_required",
            stop_reason="bounded preview did not expose target-location or remote evidence",
            evidence={
                "profile_hits": profile_hits,
                "location_hits": location_hits,
                "remote_hits": remote_hits,
            },
        )

    return GateOutcome(
        gate_name="relevance_gate",
        gate_status="passed",
        decision="passed",
        stop_reason=None,
        evidence={
            "profile_hits": profile_hits,
            "location_hits": location_hits,
            "remote_hits": remote_hits,
        },
    )


def stop_status(outcome: GateOutcome) -> tuple[str, str | None]:
    if outcome.gate_status == "failed":
        return "abort_documented", "blocked"
    if outcome.gate_status in {"deferred", "manual_review_required"}:
        return "manual_review_required", None
    return "discovery", None


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = GateStateRepository(conn)
        candidate_id = repo.upsert_candidate(
            company_key=args.company_key,
            company_name=args.company_name,
            candidate_url=args.candidate_url,
            source_name_candidate=args.source_name_candidate,
            source_family_candidate=args.source_family_candidate,
            source_target_candidate=args.source_target_candidate,
            source_type_candidate=args.source_type_candidate,
            reviewed_by=args.reviewed_by,
        )

        print(f"candidate_id: {candidate_id}")

        for outcome in (company_candidate_gate(args), source_discovery_gate(args), prefetch_risk_gate(args)):
            repo.record_gate(candidate_id, outcome, args.reviewed_by)
            print(f"{outcome.gate_name}: {outcome.gate_status} / {outcome.decision}")
            if outcome.gate_status != "passed":
                status, risk_level = stop_status(outcome)
                repo.update_candidate_status(candidate_id, status, risk_level)
                print(f"STOP: {outcome.stop_reason}")
                return 0

        try:
            fetch = fetch_candidate_page(
                args.candidate_url,
                timeout_seconds=args.timeout_seconds,
                max_preview_links=args.max_preview_links,
                source_family_candidate=args.source_family_candidate,
            )
        except requests.RequestException as exc:
            outcome = GateOutcome(
                gate_name="technical_reachability_gate",
                gate_status="failed",
                decision="abort_documented",
                stop_reason=f"request failed: {exc.__class__.__name__}",
                evidence={"error": str(exc), "candidate_url": args.candidate_url},
            )
            repo.record_gate(candidate_id, outcome, args.reviewed_by)
            repo.update_candidate_status(candidate_id, "abort_documented", "blocked")
            print(f"{outcome.gate_name}: {outcome.gate_status} / {outcome.decision}")
            print(f"STOP: {outcome.stop_reason}")
            return 0

        for outcome in (technical_reachability_gate(fetch),):
            repo.record_gate(candidate_id, outcome, args.reviewed_by)
            print(f"{outcome.gate_name}: {outcome.gate_status} / {outcome.decision}")
            if outcome.gate_status != "passed":
                status, risk_level = stop_status(outcome)
                repo.update_candidate_status(candidate_id, status, risk_level)
                print(f"STOP: {outcome.stop_reason}")
                return 0

        risk_after_fetch = postfetch_risk_gate(fetch)
        if risk_after_fetch is not None:
            repo.record_gate(candidate_id, risk_after_fetch, args.reviewed_by)
            repo.update_candidate_status(candidate_id, "abort_documented", "blocked")
            print(f"{risk_after_fetch.gate_name}: {risk_after_fetch.gate_status} / {risk_after_fetch.decision}")
            print(f"STOP: {risk_after_fetch.stop_reason}")
            return 0

        for outcome in (
            scope_gate(args),
            defensive_preview_gate(fetch),
            relevance_gate(args, fetch),
        ):
            repo.record_gate(candidate_id, outcome, args.reviewed_by)
            print(f"{outcome.gate_name}: {outcome.gate_status} / {outcome.decision}")
            if outcome.gate_status != "passed":
                status, risk_level = stop_status(outcome)
                repo.update_candidate_status(candidate_id, status, risk_level)
                print(f"STOP: {outcome.stop_reason}")
                return 0

        repo.update_candidate_status(candidate_id, "manual_review_required", "low")
        print("NEXT: candidate passed MVP gates through relevance_gate; detail evidence remains manual/next-step.")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a bounded DB-backed employer-origin candidate gate agent MVP."
    )
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--candidate-url", required=True)
    parser.add_argument("--source-name-candidate", required=True)
    parser.add_argument("--source-family-candidate", required=True)
    parser.add_argument("--source-target-candidate", required=True)
    parser.add_argument(
        "--source-type-candidate",
        default="employer_origin_career_site",
        choices=[
            "employer_origin_career_site",
            "employer_origin_ats_backed_career_site",
        ],
    )
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--profile-term", dest="profile_terms", action="append")
    parser.add_argument("--max-listing-pages", type=int, default=1)
    parser.add_argument("--max-preview-links", type=int, default=25)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--reviewed-by", default="agent_mvp")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
