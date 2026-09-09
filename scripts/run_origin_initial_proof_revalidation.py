"""Read-only Employer-Origin initial-proof revalidation using Search Intelligence.

This audit deliberately does *not* full-scrape origin sources.  It validates every
persisted employer-origin candidate with a bounded state machine:

    source alive?
      -> any current job proof?
      -> targeted search using company vocabulary learned from market sensors
      -> if no interesting job: expand with more learned/reassessment vocabulary
      -> if still no interesting job: operator manual test required

Where a provider exposes a single official feed/API inventory (for example
Greenhouse/Personio), one provider request is allowed and filtering remains local.
That is not treated as crawling.  HTML career sites remain bounded to one listing
page plus a very small detail sample or the existing connector's own request bound.

The audit also reports pagination evidence/gaps, but never enumerates an entire
paginated site merely to count it.

Database state is read-only.  No Bronze/Silver/Gold, profile, source, scheduler,
application or connector-registration state is mutated.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime
import importlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row
import requests

from scripts.run_employer_origin_gate_agent import (
    DEFAULT_PROFILE_TERMS,
    DEFAULT_REMOTE_TERMS,
    DatabaseConfig,
    fetch_candidate_page,
)
from scripts.run_employer_origin_connector_candidate_agent import concrete_job_detail_url
from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.registry import SourceRole, build_default_connector_registry


DEFAULT_OUTPUT = Path("/tmp/jap-origin-initial-proof-revalidation.json")
INITIAL_TERM_LIMIT = 5
EXPANDED_TERM_LIMIT = 12
SOURCE_PAGE_LINK_LIMIT = 80
DETAIL_SAMPLE_LIMIT = 4
MAX_TARGETED_CONNECTOR_CALLS = 8

HANNOVER_TERMS = (
    "hannover",
    "hanover",
    "region hannover",
    "langenhagen",
    "garbsen",
    "laatzen",
    "isernhagen",
    "lehrte",
    "seelze",
    "hildesheim",
    "celle",
)
REMOTE_TERMS = tuple(
    dict.fromkeys(DEFAULT_REMOTE_TERMS + ("work from home", "remote work", "mobiles arbeiten"))
)
FALLBACK_PROFILE_TERMS = tuple(
    dict.fromkeys(
        DEFAULT_PROFILE_TERMS
        + (
            "data engineer",
            "data engineering",
            "data platform",
            "data warehouse",
            "machine learning",
            "ml",
            "cloud",
            "devops",
            "automation",
            "reliability",
        )
    )
)
PAGINATION_MARKERS = (
    "pagination",
    "page=2",
    "page%3d2",
    "offset=",
    "start=",
    "load more",
    "mehr laden",
    "weitere stellen",
    "weitere jobs",
    "next page",
    "nächste seite",
)
GATES_OF_INTEREST = (
    "defensive_preview_gate",
    "relevance_gate",
    "detail_evidence_gate",
    "connector_candidate_gate",
    "controlled_activation_gate",
    "bronze_validation",
    "silver_validation",
    "source_lifecycle_tracking",
)


def relation_exists(conn: psycopg.Connection[Any], name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{name}",))
        row = cur.fetchone()
    return bool(row and row[0])


def column_exists(conn: psycopg.Connection[Any], table: str, column: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s AND column_name=%s
            )
            """,
            (table, column),
        )
        row = cur.fetchone()
    return bool(row and row[0])


def ensure_read_only(conn: psycopg.Connection[Any]) -> None:
    conn.execute("SET TRANSACTION READ ONLY")
    with conn.cursor() as cur:
        cur.execute("SHOW transaction_read_only")
        value = str(cur.fetchone()[0]).lower()
    if value != "on":
        raise RuntimeError(f"AUDIT_REFUSED: transaction_read_only={value!r}")


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def term_in_text(text: str, raw_term: str) -> bool:
    normalized = normalize(text)
    term = normalize(raw_term)
    if not term:
        return False
    if len(term) <= 3 and re.fullmatch(r"[a-z0-9+#.]+", term):
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized) is not None
    return term in normalized


def matching_terms(text: str, terms: Sequence[str]) -> list[str]:
    return [term for term in terms if term_in_text(text, term)]


def recursive_text(value: object, *, limit: int = 200_000) -> str:
    parts: list[str] = []
    size = 0

    def visit(item: object) -> None:
        nonlocal size
        if size >= limit:
            return
        if isinstance(item, Mapping):
            for child in item.values():
                visit(child)
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                visit(child)
            return
        if item is None:
            return
        text = str(item).strip()
        if not text:
            return
        remaining = max(0, limit - size)
        chunk = text[:remaining]
        parts.append(chunk)
        size += len(chunk) + 1

    visit(value)
    return " ".join(parts)


def nested(value: Mapping[str, Any], *path: str) -> object | None:
    current: object = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def first_text(value: Mapping[str, Any], paths: Sequence[tuple[str, ...]]) -> str:
    for path in paths:
        current = nested(value, *path)
        if current is not None and str(current).strip():
            return str(current).strip()
    return ""


def record_text(record: RawJobRecord) -> str:
    raw = record.raw_data if isinstance(record.raw_data, Mapping) else {}
    return recursive_text(
        {
            "source_url": record.source_url,
            "job": raw.get("job"),
            "result_card": raw.get("result_card"),
            "listing_evidence": raw.get("listing_evidence"),
        }
    )


def record_summary(
    record: RawJobRecord,
    *,
    interest_terms: Sequence[str],
    query_term: str | None = None,
) -> dict[str, object]:
    raw = record.raw_data if isinstance(record.raw_data, Mapping) else {}
    title = first_text(
        raw,
        (
            ("result_card", "title"),
            ("job", "title"),
            ("job", "titel"),
            ("job", "name"),
        ),
    )
    company = first_text(
        raw,
        (
            ("result_card", "company_name"),
            ("job", "company_name"),
            ("job", "company"),
            ("job", "arbeitgeber"),
            ("job", "legal_entity"),
        ),
    )
    location = first_text(
        raw,
        (
            ("result_card", "location"),
            ("job", "location"),
            ("job", "city"),
            ("job", "ort"),
        ),
    )
    text = record_text(record)
    learned_hits = matching_terms(text, interest_terms)
    hannover_hits = matching_terms(text, HANNOVER_TERMS)
    remote_hits = matching_terms(text, REMOTE_TERMS)
    query_match = bool(query_term and term_in_text(text, query_term))
    return {
        "external_job_id": record.external_job_id,
        "title": title,
        "company_name": company,
        "location": location,
        "source_url": record.source_url,
        "query_term": query_term,
        "query_term_match": query_match,
        "learned_interest_hits": learned_hits,
        "hannover_hits": hannover_hits,
        "remote_hits": remote_hits,
        "interesting": bool(learned_hits or query_match),
        "interesting_hannover": bool((learned_hits or query_match) and hannover_hits),
        "interesting_remote": bool((learned_hits or query_match) and remote_hits),
    }


def unique_records(records: Iterable[tuple[RawJobRecord, str | None]]) -> list[tuple[RawJobRecord, str | None]]:
    result: list[tuple[RawJobRecord, str | None]] = []
    seen: set[tuple[str, str]] = set()
    for record, query_term in records:
        key = (record.source_name, str(record.external_job_id or record.source_url))
        if key in seen:
            continue
        seen.add(key)
        result.append((record, query_term))
    return result


def cap_metadata(connector: object) -> dict[str, int]:
    values: dict[str, int] = {}
    module = importlib.import_module(connector.__class__.__module__)
    for name in (
        "MAX_DETAIL_PAGES",
        "MAX_DETAIL_PAGES_HARD_LIMIT",
        "MAX_LISTING_PAGES",
        "MAX_PAGES",
    ):
        value = getattr(module, name, None)
        if isinstance(value, int) and value > 0:
            values[name] = value
    instance_detail = getattr(connector, "max_detail_pages", None)
    if isinstance(instance_detail, int) and instance_detail > 0:
        values["INSTANCE_MAX_DETAIL_PAGES"] = instance_detail
    return values


def load_db_snapshot() -> dict[str, object]:
    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        ensure_read_only(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (company_key)
                    id, company_key, company_name, candidate_url,
                    source_name_candidate, source_family_candidate,
                    source_target_candidate, source_type_candidate,
                    status, risk_level, updated_at
                FROM employer_origin_source_candidates
                ORDER BY company_key, updated_at DESC NULLS LAST, id DESC
                """
            )
            candidates = [dict(row) for row in cur.fetchall()]

            cur.execute("SELECT count(*)::bigint FROM employer_origin_source_candidates")
            candidate_rows_total = int(cur.fetchone()[0])

            cur.execute(
                """
                SELECT candidate_id, gate_name, gate_status, decision, stop_reason,
                       evidence, reviewed_at
                FROM employer_origin_candidate_gate_reviews
                WHERE gate_name = ANY(%s::text[])
                ORDER BY candidate_id, gate_order
                """,
                (list(GATES_OF_INTEREST),),
            )
            gate_rows = [dict(row) for row in cur.fetchall()]

            profiles: list[dict[str, object]] = []
            active_terms: list[dict[str, object]] = []
            if relation_exists(conn, "search_profiles"):
                recurring = column_exists(conn, "search_profiles", "recurring_ingestion_enabled")
                recurring_select = (
                    "recurring_ingestion_enabled"
                    if recurring
                    else "FALSE AS recurring_ingestion_enabled"
                )
                cur.execute(
                    f"""
                    SELECT id, profile_name, source_name, search_location,
                           search_radius_km, offer_type, page_size, is_active,
                           {recurring_select}
                    FROM search_profiles
                    ORDER BY source_name, profile_name, id
                    """  # noqa: S608 - column fragment is internal schema detection only
                )
                profiles = [dict(row) for row in cur.fetchall()]
                if relation_exists(conn, "search_terms"):
                    cur.execute(
                        """
                        SELECT sp.source_name, sp.profile_name, st.search_term
                        FROM search_profiles sp
                        JOIN search_terms st ON st.search_profile_id = sp.id
                        WHERE sp.is_active = TRUE AND st.is_active = TRUE
                        ORDER BY sp.source_name, sp.profile_name, st.search_term
                        """
                    )
                    active_terms = [dict(row) for row in cur.fetchall()]

            vocabulary: list[dict[str, object]] = []
            if relation_exists(conn, "company_vocabulary_observations"):
                cur.execute(
                    """
                    SELECT company_key, observed_term,
                           sum(observation_count)::bigint AS observation_count,
                           max(last_seen_at) AS last_seen_at,
                           array_agg(DISTINCT source_name ORDER BY source_name) AS sensor_sources
                    FROM company_vocabulary_observations
                    GROUP BY company_key, observed_term
                    ORDER BY company_key, observation_count DESC, last_seen_at DESC, observed_term
                    """
                )
                vocabulary = [dict(row) for row in cur.fetchall()]

            value_scores: list[dict[str, object]] = []
            if relation_exists(conn, "search_term_value_scores"):
                cur.execute(
                    """
                    SELECT observed_term,
                           max(overall_value_score) AS overall_value_score,
                           max(value_band) AS value_band,
                           max(updated_at) AS updated_at
                    FROM search_term_value_scores
                    GROUP BY observed_term
                    ORDER BY max(overall_value_score) DESC NULLS LAST, observed_term
                    """
                )
                value_scores = [dict(row) for row in cur.fetchall()]

            reassessment: list[dict[str, object]] = []
            if relation_exists(conn, "candidate_reassessment_queue"):
                cur.execute(
                    """
                    SELECT DISTINCT ON (candidate_id)
                           candidate_id, company_key, suggested_search_terms,
                           trigger_reason, status, updated_at
                    FROM candidate_reassessment_queue
                    ORDER BY candidate_id, updated_at DESC NULLS LAST, id DESC
                    """
                )
                reassessment = [dict(row) for row in cur.fetchall()]

            bronze: list[dict[str, object]] = []
            if relation_exists(conn, "raw_jobs"):
                cur.execute(
                    """
                    SELECT source_name, count(*)::bigint AS bronze_count,
                           max(created_at) AS latest_bronze_at
                    FROM raw_jobs
                    GROUP BY source_name
                    ORDER BY source_name
                    """
                )
                bronze = [dict(row) for row in cur.fetchall()]

    gates: dict[int, dict[str, dict[str, object]]] = defaultdict(dict)
    for row in gate_rows:
        gates[int(row["candidate_id"])][str(row["gate_name"])] = row
    return {
        "candidate_rows_total": candidate_rows_total,
        "candidates": candidates,
        "gates": dict(gates),
        "profiles": profiles,
        "active_terms": active_terms,
        "vocabulary": vocabulary,
        "value_scores": value_scores,
        "reassessment": reassessment,
        "bronze": bronze,
    }


def historical_relevance_terms(gates: Mapping[str, Mapping[str, object]]) -> list[str]:
    gate = gates.get("relevance_gate") or {}
    evidence = gate.get("evidence")
    if not isinstance(evidence, Mapping):
        return []
    values = evidence.get("profile_hits")
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def historic_detail_urls(gates: Mapping[str, Mapping[str, object]]) -> list[str]:
    gate = gates.get("detail_evidence_gate") or {}
    evidence = gate.get("evidence")
    if not isinstance(evidence, Mapping):
        return []
    details = evidence.get("details")
    if not isinstance(details, list):
        return []
    result: list[str] = []
    for detail in details:
        if not isinstance(detail, Mapping):
            continue
        url = str(detail.get("url") or "").strip()
        if url.startswith(("https://", "http://")) and url not in result:
            result.append(url)
    return result


def _unique_terms(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        key = normalize(value)
        if not value or not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def term_plan_for_candidate(
    candidate: Mapping[str, object],
    gates: Mapping[str, Mapping[str, object]],
    *,
    vocabulary_by_company: Mapping[str, Sequence[Mapping[str, object]]],
    value_by_term: Mapping[str, Mapping[str, object]],
    reassessment_by_candidate: Mapping[int, Mapping[str, object]],
    active_terms_by_source: Mapping[str, Sequence[str]],
    global_value_terms: Sequence[str],
) -> dict[str, object]:
    company_key = str(candidate.get("company_key") or "")
    candidate_id = int(candidate["id"])
    source_name = str(candidate.get("source_name_candidate") or "")
    vocab_rows = list(vocabulary_by_company.get(company_key, ()))

    enriched_vocab: list[dict[str, object]] = []
    for row in vocab_rows:
        term = str(row.get("observed_term") or "")
        value = value_by_term.get(normalize(term), {})
        enriched_vocab.append(
            {
                "term": term,
                "observation_count": int(row.get("observation_count") or 0),
                "last_seen_at": row.get("last_seen_at"),
                "sensor_sources": list(row.get("sensor_sources") or []),
                "overall_value_score": value.get("overall_value_score"),
                "value_band": value.get("value_band"),
            }
        )

    def vocab_sort_key(row: Mapping[str, object]) -> tuple[float, int, str]:
        score = row.get("overall_value_score")
        try:
            numeric = float(score) if score is not None else -1.0
        except (TypeError, ValueError):
            numeric = -1.0
        return (-numeric, -int(row.get("observation_count") or 0), str(row.get("term") or ""))

    enriched_vocab.sort(key=vocab_sort_key)
    learned_terms = [str(row["term"]) for row in enriched_vocab]
    historical = historical_relevance_terms(gates)
    current_terms = list(active_terms_by_source.get(source_name, ()))
    reassessment = reassessment_by_candidate.get(candidate_id) or {}
    suggested = [str(value) for value in (reassessment.get("suggested_search_terms") or [])]

    initial = _unique_terms(learned_terms[:INITIAL_TERM_LIMIT] + historical + current_terms)
    initial = initial[:INITIAL_TERM_LIMIT]
    expansion = _unique_terms(
        learned_terms[INITIAL_TERM_LIMIT:]
        + suggested
        + current_terms
        + list(global_value_terms)
        + list(FALLBACK_PROFILE_TERMS)
    )
    initial_keys = {normalize(term) for term in initial}
    expansion = [term for term in expansion if normalize(term) not in initial_keys][:EXPANDED_TERM_LIMIT]
    interest_terms = _unique_terms(initial + expansion)

    return {
        "company_vocabulary": enriched_vocab,
        "company_vocabulary_count": len(enriched_vocab),
        "historical_relevance_terms": historical,
        "current_active_source_terms": current_terms,
        "reassessment_suggested_terms": suggested,
        "initial_terms": initial,
        "expanded_terms": expansion,
        "interest_terms": interest_terms,
        "vocabulary_available": bool(enriched_vocab),
    }


def fetch_detail_sample(
    url: str,
    *,
    timeout_seconds: int,
    interest_terms: Sequence[str],
) -> dict[str, object]:
    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            headers={
                "User-Agent": "job-application-pipeline-origin-search-intelligence-audit/1.0 (+read-only)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        text = response.text or ""
        interest_hits = matching_terms(text, interest_terms)
        hannover_hits = matching_terms(text, HANNOVER_TERMS)
        remote_hits = matching_terms(text, REMOTE_TERMS)
        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
        title = re.sub(r"<[^>]+>", " ", title_match.group(1)).strip() if title_match else ""
        return {
            "url": url,
            "final_url": str(response.url),
            "status_code": int(response.status_code),
            "response_bytes": len(response.content or b""),
            "title": re.sub(r"\s+", " ", title),
            "interest_hits": interest_hits,
            "hannover_hits": hannover_hits,
            "remote_hits": remote_hits,
            "interesting": bool(interest_hits),
            "interesting_hannover": bool(interest_hits and hannover_hits),
            "interesting_remote": bool(interest_hits and remote_hits),
        }
    except Exception as exc:  # every source must remain independently diagnosable
        return {"url": url, "error": f"{type(exc).__name__}: {exc}"}


def source_page_probe(
    candidate: Mapping[str, object],
    *,
    timeout_seconds: int,
    interest_terms: Sequence[str],
) -> dict[str, object]:
    url = str(candidate.get("candidate_url") or "").strip()
    if not url:
        return {"status": "NO_CANDIDATE_URL", "job_proof": False}
    try:
        page = fetch_candidate_page(
            url,
            timeout_seconds=timeout_seconds,
            max_preview_links=SOURCE_PAGE_LINK_LIMIT,
            source_family_candidate=str(candidate.get("source_family_candidate") or "") or None,
        )
    except Exception as exc:
        return {
            "status": "FETCH_ERROR",
            "job_proof": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    job_links = list(page.same_domain_job_links)
    concrete = [link for link in job_links if concrete_job_detail_url(link)]
    sample_urls = (concrete or job_links)[:DETAIL_SAMPLE_LIMIT]
    detail_samples = [
        fetch_detail_sample(
            link,
            timeout_seconds=timeout_seconds,
            interest_terms=interest_terms,
        )
        for link in sample_urls
    ]
    lowered = normalize(page.text[:500_000])
    pagination_hints = [marker for marker in PAGINATION_MARKERS if marker in lowered]
    return {
        "status": "REACHABLE" if 200 <= page.status_code < 400 else "HTTP_ERROR",
        "http_status_code": page.status_code,
        "final_url": page.final_url,
        "response_bytes": page.response_bytes,
        "page_title": page.title,
        "static_job_link_count": len(job_links),
        "concrete_job_link_count": len(concrete),
        "job_link_sample": job_links[:10],
        "pagination_hints": pagination_hints,
        "detail_samples": detail_samples,
        "job_proof": bool(job_links),
        "interesting_sample_count": sum(bool(row.get("interesting")) for row in detail_samples),
        "interesting_hannover_sample_count": sum(bool(row.get("interesting_hannover")) for row in detail_samples),
        "interesting_remote_sample_count": sum(bool(row.get("interesting_remote")) for row in detail_samples),
    }


def profile_for_source(source_name: str, profile_rows: Sequence[Mapping[str, object]]) -> SearchProfile:
    selected = next(
        (
            row
            for row in profile_rows
            if str(row.get("source_name") or "") == source_name and row.get("is_active") is True
        ),
        None,
    ) or next(
        (row for row in profile_rows if str(row.get("source_name") or "") == source_name),
        None,
    )
    if selected:
        return SearchProfile(
            id=int(selected.get("id") or 0),
            profile_name=str(selected.get("profile_name") or f"audit_{source_name}"),
            source_name=source_name,
            search_location=str(selected.get("search_location") or "Hannover"),
            search_radius_km=int(selected.get("search_radius_km") or 50),
            offer_type=int(selected.get("offer_type") or 1),
            # This is only a connector request parameter, not permission to crawl pages.
            page_size=max(25, min(100, int(selected.get("page_size") or 25))),
        )
    return SearchProfile(
        id=0,
        profile_name=f"audit_{source_name.replace(':', '_')}",
        source_name=source_name,
        search_location="Hannover",
        search_radius_km=50,
        offer_type=1,
        page_size=25,
    )


def probe_connector_targeted(
    source_name: str,
    *,
    profile_rows: Sequence[Mapping[str, object]],
    initial_terms: Sequence[str],
    expanded_terms: Sequence[str],
    interest_terms: Sequence[str],
) -> dict[str, object]:
    registry = build_default_connector_registry()
    try:
        role = registry.role_for(source_name)
        connector = registry.create(source_name)
    except Exception as exc:
        return {
            "source_name": source_name,
            "implemented": False,
            "status": "NOT_REGISTERED",
            "error": f"{type(exc).__name__}: {exc}",
        }
    if role != SourceRole.EMPLOYER_ORIGIN:
        return {
            "source_name": source_name,
            "implemented": True,
            "role": role.value,
            "status": "NON_ORIGIN_SKIPPED",
        }

    profile = profile_for_source(source_name, profile_rows)
    capabilities = asdict(connector.capabilities)
    caps = cap_metadata(connector)
    provider_single_inventory = bool(
        connector.capabilities.supports_full_fetch
        and not connector.capabilities.supports_keyword
        and not caps
    )

    attempted: list[str] = []
    fetched: list[tuple[RawJobRecord, str | None]] = []
    request_evidence: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []

    def execute(term: str) -> None:
        attempted.append(term)
        try:
            records, requested_url = connector.fetch_jobs(profile, SearchTerm(search_term=term))
            fetched.extend((record, term) for record in records)
            request_evidence.append(
                {
                    "term": term,
                    "requested_url": requested_url,
                    "record_count": len(records),
                }
            )
        except Exception as exc:
            errors.append({"term": term, "error": f"{type(exc).__name__}: {exc}"})

    initial = list(initial_terms) or list(FALLBACK_PROFILE_TERMS[:1])
    expansion = [term for term in expanded_terms if normalize(term) not in {normalize(x) for x in initial}]

    # Official single-feed/API sources are fetched once; local filtering below applies the
    # learned vocabulary without repeatedly downloading the same feed.
    if provider_single_inventory:
        execute(initial[0])
    else:
        for term in initial:
            if len(attempted) >= MAX_TARGETED_CONNECTOR_CALLS:
                break
            execute(term)
            summaries = [
                record_summary(record, interest_terms=interest_terms, query_term=query)
                for record, query in unique_records(fetched)
            ]
            if any(row["interesting_hannover"] or row["interesting_remote"] for row in summaries):
                break

    unique = unique_records(fetched)
    summaries = [
        record_summary(record, interest_terms=interest_terms, query_term=query)
        for record, query in unique
    ]
    initial_interesting = [row for row in summaries if row["interesting"]]

    expansion_used = False
    if not initial_interesting and not provider_single_inventory:
        expansion_used = True
        for term in expansion:
            if len(attempted) >= MAX_TARGETED_CONNECTOR_CALLS:
                break
            execute(term)
            unique = unique_records(fetched)
            summaries = [
                record_summary(record, interest_terms=interest_terms, query_term=query)
                for record, query in unique
            ]
            if any(row["interesting"] for row in summaries):
                break

    unique = unique_records(fetched)
    summaries = [
        record_summary(record, interest_terms=interest_terms, query_term=query)
        for record, query in unique
    ]
    interesting = [row for row in summaries if row["interesting"]]
    hannover = [row for row in summaries if row["interesting_hannover"]]
    remote = [row for row in summaries if row["interesting_remote"]]

    if caps:
        pagination_contract = "BOUNDED_DETAIL_SELECTION"
    elif connector.capabilities.supports_pagination:
        pagination_contract = "PAGINATION_DECLARED"
    elif provider_single_inventory:
        pagination_contract = "SINGLE_PROVIDER_INVENTORY_ENDPOINT"
    else:
        pagination_contract = "NO_PAGINATION_CONTRACT"

    state = "OPERATOR_MANUAL_TEST_REQUIRED"
    if interesting:
        state = "INTERESTING_JOB_PROOF"
    elif summaries:
        state = "GENERIC_JOB_PROOF_ONLY"
    elif errors and not request_evidence:
        state = "CONNECTOR_ERROR"

    return {
        "source_name": source_name,
        "implemented": True,
        "role": role.value,
        "connector_class": connector.__class__.__name__,
        "connector_module": connector.__class__.__module__,
        "capabilities": capabilities,
        "hard_caps": caps,
        "provider_single_inventory": provider_single_inventory,
        "pagination_contract": pagination_contract,
        "status": "SUCCESS" if request_evidence else "FETCH_ERROR",
        "state": state,
        "initial_terms": list(initial_terms),
        "expanded_terms_available": list(expanded_terms),
        "expanded_search_used": expansion_used,
        "terms_attempted": attempted,
        "requests": request_evidence,
        "errors": errors,
        "bounded_unique_job_proof_count": len(summaries),
        "interesting_job_count": len(interesting),
        "interesting_hannover_count": len(hannover),
        "interesting_remote_count": len(remote),
        "job_samples": summaries[:12],
        "interesting_samples": interesting[:12],
    }


def json_safe(value: object) -> object:
    if isinstance(value, datetime):
        current = value if value.tzinfo else value.replace(tzinfo=UTC)
        return current.isoformat()
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout-seconds", type=int, default=15)
    parser.add_argument("--candidate-workers", type=int, default=8)
    args = parser.parse_args()

    db = load_db_snapshot()
    candidates = list(db["candidates"])
    gates_by_candidate = db["gates"]
    profiles = list(db["profiles"])

    vocabulary_by_company: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in db["vocabulary"]:
        vocabulary_by_company[str(row.get("company_key") or "")].append(row)
    value_by_term = {
        normalize(row.get("observed_term")): row
        for row in db["value_scores"]
        if normalize(row.get("observed_term"))
    }
    reassessment_by_candidate = {
        int(row["candidate_id"]): row for row in db["reassessment"]
    }
    active_terms_by_source: dict[str, list[str]] = defaultdict(list)
    for row in db["active_terms"]:
        active_terms_by_source[str(row.get("source_name") or "")].append(
            str(row.get("search_term") or "")
        )
    global_value_terms = [
        str(row.get("observed_term") or "")
        for row in db["value_scores"][:30]
        if str(row.get("observed_term") or "").strip()
    ]

    plans: dict[int, dict[str, object]] = {}
    for candidate in candidates:
        candidate_id = int(candidate["id"])
        plans[candidate_id] = term_plan_for_candidate(
            candidate,
            gates_by_candidate.get(candidate_id, {}),
            vocabulary_by_company=vocabulary_by_company,
            value_by_term=value_by_term,
            reassessment_by_candidate=reassessment_by_candidate,
            active_terms_by_source=active_terms_by_source,
            global_value_terms=global_value_terms,
        )

    source_pages: dict[int, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=args.candidate_workers) as pool:
        futures = {
            pool.submit(
                source_page_probe,
                candidate,
                timeout_seconds=args.timeout_seconds,
                interest_terms=plans[int(candidate["id"])]["interest_terms"],
            ): int(candidate["id"])
            for candidate in candidates
        }
        for future in as_completed(futures):
            source_pages[futures[future]] = future.result()

    bronze_by_source = {str(row["source_name"]): row for row in db["bronze"]}
    rows: list[dict[str, object]] = []
    connector_probe_cache: dict[tuple[str, tuple[str, ...], tuple[str, ...]], dict[str, object]] = {}

    for candidate in candidates:
        candidate_id = int(candidate["id"])
        source_name = str(candidate.get("source_name_candidate") or "")
        plan = plans[candidate_id]
        cache_key = (
            source_name,
            tuple(plan["initial_terms"]),
            tuple(plan["expanded_terms"]),
        )
        if source_name:
            if cache_key not in connector_probe_cache:
                connector_probe_cache[cache_key] = probe_connector_targeted(
                    source_name,
                    profile_rows=profiles,
                    initial_terms=plan["initial_terms"],
                    expanded_terms=plan["expanded_terms"],
                    interest_terms=plan["interest_terms"],
                )
            connector = connector_probe_cache[cache_key]
        else:
            connector = {
                "source_name": "",
                "implemented": False,
                "status": "NO_SOURCE_NAME",
                "state": "OPERATOR_MANUAL_TEST_REQUIRED",
            }

        page = source_pages[candidate_id]
        job_proof = bool(page.get("job_proof")) or int(connector.get("bounded_unique_job_proof_count") or 0) > 0
        interesting = (
            int(page.get("interesting_sample_count") or 0) > 0
            or int(connector.get("interesting_job_count") or 0) > 0
        )
        local_or_remote = (
            int(page.get("interesting_hannover_sample_count") or 0) > 0
            or int(page.get("interesting_remote_sample_count") or 0) > 0
            or int(connector.get("interesting_hannover_count") or 0) > 0
            or int(connector.get("interesting_remote_count") or 0) > 0
        )

        next_action = "NEXT_SOURCE"
        state = "SOURCE_UNRESOLVED"
        if page.get("status") == "REACHABLE":
            state = "SOURCE_ALIVE"
        if job_proof:
            state = "GENERIC_JOB_PROOF"
        if interesting:
            state = "INTERESTING_JOB_PROOF"
        if local_or_remote:
            state = "INTERESTING_HANNOVER_OR_REMOTE_PROOF"
        if not interesting:
            next_action = "OPERATOR_MANUAL_TEST"

        pagination_gap = bool(page.get("pagination_hints")) and connector.get("pagination_contract") in {
            "NO_PAGINATION_CONTRACT",
            "BOUNDED_DETAIL_SELECTION",
        }

        rows.append(
            {
                "candidate_id": candidate_id,
                "company_key": str(candidate.get("company_key") or ""),
                "company_name": str(candidate.get("company_name") or ""),
                "candidate_status": str(candidate.get("status") or ""),
                "candidate_url": str(candidate.get("candidate_url") or ""),
                "source_name_candidate": source_name,
                "source_family_candidate": str(candidate.get("source_family_candidate") or ""),
                "historical_relevance_passed": (
                    (gates_by_candidate.get(candidate_id, {}).get("relevance_gate") or {}).get("gate_status") == "passed"
                ),
                "historic_detail_urls": historic_detail_urls(gates_by_candidate.get(candidate_id, {})),
                "search_term_plan": plan,
                "source_page_probe": page,
                "connector_probe": connector,
                "historical_bronze": bronze_by_source.get(source_name),
                "job_proof": job_proof,
                "interesting_job_proof": interesting,
                "interesting_hannover_or_remote_proof": local_or_remote,
                "pagination_gap_suspected": pagination_gap,
                "state": state,
                "next_action": next_action,
            }
        )

    rows.sort(key=lambda row: (str(row["company_key"]), int(row["candidate_id"])))

    vocabulary_candidates = [row for row in rows if row["search_term_plan"]["vocabulary_available"]]
    source_alive = [row for row in rows if row["source_page_probe"].get("status") == "REACHABLE"]
    any_jobs = [row for row in rows if row["job_proof"]]
    interesting = [row for row in rows if row["interesting_job_proof"]]
    local_remote = [row for row in rows if row["interesting_hannover_or_remote_proof"]]
    manual = [row for row in rows if row["next_action"] == "OPERATOR_MANUAL_TEST"]
    pagination_gaps = [row for row in rows if row["pagination_gap_suspected"]]
    registered = [row for row in rows if row["connector_probe"].get("implemented") is True]
    registered_with_jobs = [row for row in registered if int(row["connector_probe"].get("bounded_unique_job_proof_count") or 0) > 0]
    registered_interesting = [row for row in registered if int(row["connector_probe"].get("interesting_job_count") or 0) > 0]

    summary = {
        "candidate_rows_total": db["candidate_rows_total"],
        "candidate_companies_latest": len(rows),
        "company_vocabulary_rows": len(db["vocabulary"]),
        "candidate_companies_with_learned_vocabulary": len(vocabulary_candidates),
        "search_term_value_rows": len(db["value_scores"]),
        "candidate_sources_alive_now": len(source_alive),
        "candidate_sources_with_any_job_proof": len(any_jobs),
        "candidate_sources_with_interesting_job_proof": len(interesting),
        "candidate_sources_with_interesting_hannover_or_remote_proof": len(local_remote),
        "registered_origin_targets_tested": len(registered),
        "registered_origin_targets_with_any_job_proof": len(registered_with_jobs),
        "registered_origin_targets_with_interesting_job_proof": len(registered_interesting),
        "operator_manual_tests_required": len(manual),
        "pagination_gaps_suspected": len(pagination_gaps),
        "database_writes": 0,
    }

    report = {
        "schema_version": "jap.origin_initial_proof_revalidation.v2",
        "generated_at": datetime.now(UTC).isoformat(),
        "contract": {
            "full_scrape_allowed": False,
            "source_listing_pages_per_candidate": 1,
            "detail_sample_limit": DETAIL_SAMPLE_LIMIT,
            "targeted_connector_call_limit": MAX_TARGETED_CONNECTOR_CALLS,
            "initial_company_vocabulary_term_limit": INITIAL_TERM_LIMIT,
            "expanded_term_limit": EXPANDED_TERM_LIMIT,
            "official_single_feed_or_api_inventory_request_allowed": True,
            "pagination_rule": "prove/flag pagination need; do not enumerate an entire site for audit counts",
            "state_machine": [
                "SOURCE_ALIVE",
                "GENERIC_JOB_PROOF",
                "INTERESTING_JOB_PROOF",
                "INTERESTING_HANNOVER_OR_REMOTE_PROOF",
                "OPERATOR_MANUAL_TEST",
                "NEXT_SOURCE",
            ],
            "read_only": True,
        },
        "summary": summary,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(json_safe(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("=" * 76)
    print("JAP ORIGIN SEARCH-INTELLIGENCE INITIAL-PROOF REVALIDATION")
    print("=" * 76)
    for key, value in summary.items():
        print(f"{key.upper()}={value}")
    print("--- SOURCE RESULTS ---")
    for row in rows:
        connector = row["connector_probe"]
        plan = row["search_term_plan"]
        print(
            "SOURCE="
            f"{row['company_key']}|origin={row['source_name_candidate']}|"
            f"alive={row['source_page_probe'].get('status')}|job_proof={row['job_proof']}|"
            f"interesting={row['interesting_job_proof']}|local_remote={row['interesting_hannover_or_remote_proof']}|"
            f"vocab={plan['company_vocabulary_count']}|initial={plan['initial_terms']}|"
            f"expanded_used={connector.get('expanded_search_used', False)}|"
            f"connector={connector.get('status')}|jobs={connector.get('bounded_unique_job_proof_count', 0)}|"
            f"interesting_jobs={connector.get('interesting_job_count', 0)}|"
            f"pagination_gap={row['pagination_gap_suspected']}|next={row['next_action']}"
        )
    print("DATABASE_WRITES=0")
    print(f"artifact={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
