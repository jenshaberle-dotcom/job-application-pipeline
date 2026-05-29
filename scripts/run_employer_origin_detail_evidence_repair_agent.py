from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import psycopg
import requests
from psycopg.rows import dict_row


DETAIL_EVIDENCE_GATE = "detail_evidence_gate"
CONNECTOR_CANDIDATE_GATE = "connector_candidate_gate"

NON_JOB_DETAIL_URL_FRAGMENTS = (
    "/privacy",
    "/datenschutz",
    "/impressum",
    "/imprint",
    "/cookie",
    "/kontakt",
    "/contact",
    "/faq",
    "/your_career_opportunities",
)

GENERIC_DETAIL_LAST_SEGMENTS = (
    "career",
    "careers",
    "karriere",
    "job",
    "jobs",
    "job_board",
    "stellen",
    "stellenangebote",
    "offene-stellen",
    "stellen-finden",
)

JOB_DETAIL_PATH_MARKERS = (
    "/jobs/",
    "/job/",
    "/stellenangebote/",
    "/offene-stellen/",
    "/stellen-finden/",
    "/karriere/offene-stellen/",
    "/karriere/jobs/",
)

DEFAULT_PROFILE_TERMS = (
    "data",
    "daten",
    "analytics",
    "analyst",
    "business analyst",
    "business intelligence",
    "bi",
    "sql",
    "python",
    "ki",
    "ai",
    "software",
    "entwickler",
    "javascript",
    "ui",
    "product owner",
    "produktverantwort",
)

DEFAULT_LOCATION_TERMS = (
    "hannover",
    "remote",
    "deutschland",
    "bundesweit",
    "hybrid",
)

REQUEST_TIMEOUT_SECONDS = 20


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
    status: str
    risk_level: str


@dataclass(frozen=True)
class LinkCandidate:
    url: str
    source_url: str
    text: str
    profile_terms: tuple[str, ...]
    location_terms: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class DetailEvidence:
    url: str
    final_url: str
    status_code: int
    title: str
    profile_terms: tuple[str, ...]
    location_terms: tuple[str, ...]
    html_bytes: int
    reason: str


@dataclass(frozen=True)
class RepairOutcome:
    gate_status: str
    decision: str
    stop_reason: str | None
    details: tuple[DetailEvidence, ...]
    rejected_urls: tuple[str, ...]
    requested_urls: tuple[str, ...]
    evidence: dict[str, Any]


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        self._href = urljoin(self.base_url, href)
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((self._href.split("#", 1)[0], normalize_whitespace(" ".join(self._text))))
            self._href = None
            self._text = []


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        self.text_parts.append(data)

    @property
    def title(self) -> str:
        return normalize_whitespace(" ".join(self.title_parts))

    @property
    def text(self) -> str:
        return normalize_whitespace(" ".join(self.text_parts))


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_text(value: str | None) -> str:
    value = normalize_whitespace(value).casefold()
    return value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def unique_ordered(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return tuple(result)


def find_terms(value: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    haystack = normalize_text(value)
    matches: list[str] = []
    for term in terms:
        if normalize_text(term) in haystack and term not in matches:
            matches.append(term)
    return tuple(matches)


def concrete_job_detail_url(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False

    parsed = urlparse(url)
    path = re.sub(r"/+", "/", parsed.path.casefold()).rstrip("/")
    if not path:
        return False

    if any(fragment in path for fragment in NON_JOB_DETAIL_URL_FRAGMENTS):
        return False

    last_segment = path.rsplit("/", 1)[-1]
    if last_segment in GENERIC_DETAIL_LAST_SEGMENTS:
        return False

    if not any(marker in f"{path}/" for marker in JOB_DETAIL_PATH_MARKERS):
        return False

    if len(last_segment) < 6:
        return False

    return "-" in last_segment or "_" in last_segment or any(ch.isdigit() for ch in last_segment)


def same_host(url: str, allowed_hosts: tuple[str, ...]) -> bool:
    return urlparse(url).netloc.casefold() in allowed_hosts


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    parser = LinkExtractor(base_url)
    parser.feed(html)
    return parser.links


def candidate_hosts(candidate: SourceCandidate) -> tuple[str, ...]:
    return unique_ordered([urlparse(candidate.candidate_url).netloc.casefold()])


def requested_seed_urls(candidate: SourceCandidate, gates: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    urls = [candidate.candidate_url]

    detail_gate = gates.get(DETAIL_EVIDENCE_GATE) or {}
    evidence = detail_gate.get("evidence") or {}
    details = evidence.get("details") or []
    rejected = evidence.get("rejected_detail_urls") or evidence.get("rejected_urls") or []

    for item in details:
        if isinstance(item, dict):
            urls.append(str(item.get("url") or ""))
    for item in rejected:
        urls.append(str(item or ""))

    return unique_ordered([url for url in urls if url.startswith(("http://", "https://"))])


def fetch_url(url: str) -> tuple[str, str, int]:
    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "job-application-pipeline-employer-origin-detail-repair-agent/0.1 "
                "(bounded; no browser automation; no raw html persistence)"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text, response.url, response.status_code


def discover_link_candidates(
    *,
    candidate: SourceCandidate,
    gates: dict[str, dict[str, Any]],
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
    max_seed_pages: int,
    fetcher=fetch_url,
) -> tuple[tuple[LinkCandidate, ...], tuple[str, ...], tuple[str, ...]]:
    allowed_hosts = candidate_hosts(candidate)
    seed_urls = requested_seed_urls(candidate, gates)[:max_seed_pages]
    requested_urls: list[str] = []
    rejected_urls: list[str] = []
    link_candidates: list[LinkCandidate] = []
    seen: set[str] = set()

    for seed_url in seed_urls:
        if not same_host(seed_url, allowed_hosts):
            rejected_urls.append(seed_url)
            continue

        try:
            html, final_url, status_code = fetcher(seed_url)
        except Exception as exc:  # noqa: BLE001 - bounded repair must continue across individual URL failures.
            rejected_urls.append(f"{seed_url} :: fetch_error={type(exc).__name__}")
            continue

        requested_urls.append(final_url)
        if status_code >= 400:
            rejected_urls.append(final_url)
            continue

        for url, text in extract_links(html, final_url):
            if url in seen:
                continue
            seen.add(url)

            if not same_host(url, allowed_hosts):
                rejected_urls.append(url)
                continue

            if not concrete_job_detail_url(url):
                rejected_urls.append(url)
                continue

            evidence_blob = " ".join([url, text])
            matched_profile = find_terms(evidence_blob, profile_terms)
            matched_location = find_terms(evidence_blob, location_terms)

            if not matched_profile and not matched_location:
                rejected_urls.append(url)
                continue

            link_candidates.append(
                LinkCandidate(
                    url=url,
                    source_url=final_url,
                    text=text,
                    profile_terms=matched_profile,
                    location_terms=matched_location,
                    reason="Concrete job-detail URL found during bounded repair.",
                )
            )

    return tuple(link_candidates), unique_ordered(rejected_urls), unique_ordered(requested_urls)


def parse_detail_page(html: str) -> tuple[str, str]:
    parser = TextExtractor()
    parser.feed(html)
    return parser.title, parser.text


def validate_detail_candidates(
    *,
    link_candidates: tuple[LinkCandidate, ...],
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
    max_detail_pages: int,
    fetcher=fetch_url,
) -> tuple[tuple[DetailEvidence, ...], tuple[str, ...], tuple[str, ...]]:
    requested_urls: list[str] = []
    rejected_urls: list[str] = []
    details: list[DetailEvidence] = []

    for link in link_candidates[:max_detail_pages]:
        try:
            html, final_url, status_code = fetcher(link.url)
        except Exception as exc:  # noqa: BLE001
            rejected_urls.append(f"{link.url} :: fetch_error={type(exc).__name__}")
            continue

        requested_urls.append(final_url)
        if status_code >= 400:
            rejected_urls.append(final_url)
            continue

        title, text = parse_detail_page(html)
        evidence_blob = " ".join([link.url, link.text, title, text])
        matched_profile = find_terms(evidence_blob, profile_terms)
        matched_location = find_terms(evidence_blob, location_terms)

        if not matched_profile or not matched_location:
            rejected_urls.append(final_url)
            continue

        details.append(
            DetailEvidence(
                url=link.url,
                final_url=final_url,
                status_code=status_code,
                title=title,
                profile_terms=matched_profile,
                location_terms=matched_location,
                html_bytes=len(html.encode("utf-8")),
                reason="Detail page contains concrete job URL plus profile and target/remote signals.",
            )
        )

    return tuple(details), unique_ordered(rejected_urls), unique_ordered(requested_urls)


def build_repair_outcome(
    *,
    candidate: SourceCandidate,
    gates: dict[str, dict[str, Any]],
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
    max_seed_pages: int,
    max_detail_pages: int,
    fetcher=fetch_url,
) -> RepairOutcome:
    link_candidates, link_rejections, listing_requests = discover_link_candidates(
        candidate=candidate,
        gates=gates,
        profile_terms=profile_terms,
        location_terms=location_terms,
        max_seed_pages=max_seed_pages,
        fetcher=fetcher,
    )
    details, detail_rejections, detail_requests = validate_detail_candidates(
        link_candidates=link_candidates,
        profile_terms=profile_terms,
        location_terms=location_terms,
        max_detail_pages=max_detail_pages,
        fetcher=fetcher,
    )

    requested_urls = unique_ordered([*listing_requests, *detail_requests])
    rejected_urls = unique_ordered([*link_rejections, *detail_rejections])

    evidence: dict[str, Any] = {
        "repair_attempted": True,
        "repair_agent": "s2w_employer_origin_detail_evidence_repair_agent",
        "repair_boundary": {
            "database_writes": True,
            "bronze_persistence": False,
            "connector_activation": False,
            "browser_automation_used": False,
            "raw_html_persisted": False,
            "max_seed_pages": max_seed_pages,
            "max_detail_pages": max_detail_pages,
        },
        "requested_urls": list(requested_urls),
        "rejected_urls": list(rejected_urls),
        "candidate_links": [
            {
                "url": link.url,
                "source_url": link.source_url,
                "text": link.text,
                "profile_terms": list(link.profile_terms),
                "location_terms": list(link.location_terms),
                "reason": link.reason,
            }
            for link in link_candidates
        ],
        "details": [
            {
                "url": detail.url,
                "final_url": detail.final_url,
                "status_code": detail.status_code,
                "title": detail.title,
                "profile_terms": list(detail.profile_terms),
                "location_terms": list(detail.location_terms),
                "html_bytes": detail.html_bytes,
                "raw_html_persisted": False,
                "reason": detail.reason,
            }
            for detail in details
        ],
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }

    if details:
        return RepairOutcome(
            gate_status="passed",
            decision="continue",
            stop_reason=None,
            details=details,
            rejected_urls=rejected_urls,
            requested_urls=requested_urls,
            evidence=evidence,
        )

    return RepairOutcome(
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="bounded repair found no concrete detail pages with profile and target/remote signals",
        details=details,
        rejected_urls=rejected_urls,
        requested_urls=requested_urls,
        evidence=evidence,
    )


def repair_report_lines(candidate: SourceCandidate, outcome: RepairOutcome) -> list[str]:
    lines = [
        f"candidate_id: {candidate.id}",
        f"candidate: {candidate.company_key} | {candidate.source_name_candidate}",
        f"{DETAIL_EVIDENCE_GATE}: {outcome.gate_status} / {outcome.decision}",
    ]

    if outcome.stop_reason:
        lines.append(f"STOP: {outcome.stop_reason}")
    else:
        lines.append(f"repaired_detail_count: {len(outcome.details)}")
        lines.append("NEXT: rerun connector_candidate_agent to recompute connector_candidate_gate from repaired DB evidence.")

    return lines


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
            status=str(row["status"]),
            risk_level=str(row["risk_level"]),
        )

    def load_gates(self, candidate_id: int) -> dict[str, dict[str, Any]]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select *
                from employer_origin_candidate_gate_reviews
                where candidate_id = %s
                """,
                (candidate_id,),
            )
            rows = cur.fetchall()

        return {str(row["gate_name"]): dict(row) for row in rows}

    def record_detail_evidence_gate(
        self,
        *,
        candidate_id: int,
        outcome: RepairOutcome,
        reviewed_by: str,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                insert into employer_origin_candidate_gate_reviews (
                    candidate_id,
                    gate_order,
                    gate_name,
                    gate_status,
                    decision,
                    stop_reason,
                    evidence,
                    reviewed_by
                )
                values (%s, 8, %s, %s, %s, %s, %s, %s)
                on conflict (candidate_id, gate_name)
                do update set
                    gate_status = excluded.gate_status,
                    decision = excluded.decision,
                    stop_reason = excluded.stop_reason,
                    evidence = excluded.evidence,
                    reviewed_by = excluded.reviewed_by
                """,
                (
                    candidate_id,
                    DETAIL_EVIDENCE_GATE,
                    outcome.gate_status,
                    outcome.decision,
                    outcome.stop_reason,
                    json.dumps(outcome.evidence),
                    reviewed_by,
                ),
            )


def build_terms(args: argparse.Namespace) -> tuple[tuple[str, ...], tuple[str, ...]]:
    profile_terms = unique_ordered([*DEFAULT_PROFILE_TERMS, *(args.profile_term or [])])
    location_terms = unique_ordered([*DEFAULT_LOCATION_TERMS, *(args.location_term or [])])
    if args.target_location:
        location_terms = unique_ordered([args.target_location, *location_terms])
    return profile_terms, location_terms


def run_agent(args: argparse.Namespace) -> int:
    profile_terms, location_terms = build_terms(args)

    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = GateStateRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        gates = repo.load_gates(candidate.id)

        outcome = build_repair_outcome(
            candidate=candidate,
            gates=gates,
            profile_terms=profile_terms,
            location_terms=location_terms,
            max_seed_pages=args.max_seed_pages,
            max_detail_pages=args.max_detail_pages,
        )

        if not args.dry_run:
            repo.record_detail_evidence_gate(
                candidate_id=candidate.id,
                outcome=outcome,
                reviewed_by=args.reviewed_by,
            )
            conn.commit()

    for line in repair_report_lines(candidate, outcome):
        print(line)

    if args.dry_run:
        print("DRY RUN: no DB gate state was changed.")

    return 0 if outcome.details else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bounded DB-backed repair agent for weak employer-origin detail evidence."
    )

    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")

    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--profile-term", action="append")
    parser.add_argument("--location-term", action="append")
    parser.add_argument("--max-seed-pages", type=int, default=3)
    parser.add_argument("--max-detail-pages", type=int, default=3)
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
