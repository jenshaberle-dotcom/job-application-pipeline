"""Read-only live revalidation of the complete Employer-Origin candidate pool.

The audit answers the question that predates Product/CC delivery:

1. Does each persisted candidate source still expose any current vacancies?
2. If a JAP connector exists for the source, does it still return vacancies?
3. Does the returned inventory contain job-level profile evidence and Hannover/remote evidence?
4. Is the connector capable of complete inventory acquisition, including pagination when required?

Historical candidate-gate state is read only as provenance. The historical gate MVP used one
listing page and listing-page text for relevance; this audit therefore does not treat a passed
historical relevance gate as current job-level proof.

No database row is written and no source/profile/scheduler state is changed.
"""
from __future__ import annotations

import argparse
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
PROFILE_TERMS = tuple(
    dict.fromkeys(
        DEFAULT_PROFILE_TERMS
        + (
            "machine learning",
            "ml engineer",
            "data engineer",
            "data engineering",
            "data scientist",
            "data science",
            "data platform",
            "data warehouse",
            "etl",
            "cloud",
            "devops",
            "platform engineer",
            "reliability",
            "site reliability",
            "automation",
        )
    )
)
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
)
REMOTE_TERMS = tuple(dict.fromkeys(DEFAULT_REMOTE_TERMS + ("work from home", "remote work")))
PAGINATION_MARKERS = (
    "pagination",
    "page=2",
    "page%3d2",
    "offset=",
    "start=",
    "load more",
    "mehr laden",
    "weitere stellen",
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


def ensure_read_only(conn: psycopg.Connection[Any]) -> None:
    conn.execute("SET TRANSACTION READ ONLY")
    with conn.cursor() as cur:
        cur.execute("SHOW transaction_read_only")
        value = str(cur.fetchone()[0]).lower()
    if value != "on":
        raise RuntimeError(f"AUDIT_REFUSED: transaction_read_only={value!r}")


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def match_terms(text: str, terms: Sequence[str]) -> list[str]:
    normalized = normalize(text)
    hits: list[str] = []
    for raw in terms:
        term = normalize(raw)
        if not term:
            continue
        if len(term) <= 3 and re.fullmatch(r"[a-z0-9]+", term):
            matched = re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized) is not None
        else:
            matched = term in normalized
        if matched and raw not in hits:
            hits.append(raw)
    return hits


def recursive_text(value: object, *, limit: int = 250_000) -> str:
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


def record_summary(record: RawJobRecord) -> dict[str, object]:
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
    job_text = recursive_text(
        {
            "title": title,
            "location": location,
            "job": raw.get("job"),
            "result_card": raw.get("result_card"),
        }
    )
    profile_hits = match_terms(job_text, PROFILE_TERMS)
    hannover_hits = match_terms(job_text, HANNOVER_TERMS)
    remote_hits = match_terms(job_text, REMOTE_TERMS)
    return {
        "external_job_id": record.external_job_id,
        "title": title,
        "company_name": company,
        "location": location,
        "source_url": record.source_url,
        "profile_hits": profile_hits,
        "hannover_hits": hannover_hits,
        "remote_hits": remote_hits,
        "profile_interesting": bool(profile_hits),
        "profile_hannover": bool(profile_hits and hannover_hits),
        "profile_remote": bool(profile_hits and remote_hits),
    }


def unique_records(records: Iterable[RawJobRecord]) -> list[RawJobRecord]:
    result: list[RawJobRecord] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record.source_name, str(record.external_job_id or record.source_url))
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
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
        value = getattr(connector, name.lower(), None)
        if not isinstance(value, int):
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
            if relation_exists(conn, "search_profiles"):
                cur.execute(
                    """
                    SELECT id, profile_name, source_name, search_location,
                           search_radius_km, offer_type, page_size, is_active,
                           CASE WHEN EXISTS (
                               SELECT 1 FROM information_schema.columns
                               WHERE table_schema='public' AND table_name='search_profiles'
                                 AND column_name='recurring_ingestion_enabled'
                           ) THEN recurring_ingestion_enabled ELSE FALSE END AS recurring_ingestion_enabled
                    FROM search_profiles
                    ORDER BY source_name, profile_name, id
                    """
                )
                profiles = [dict(row) for row in cur.fetchall()]

            bronze: list[dict[str, object]] = []
            if relation_exists(conn, "raw_jobs"):
                cur.execute(
                    """
                    SELECT source_name, count(*)::bigint AS bronze_count,
                           max(fetched_at) AS latest_bronze_at
                    FROM raw_jobs
                    GROUP BY source_name
                    ORDER BY source_name
                    """
                )
                bronze = [dict(row) for row in cur.fetchall()]

            observations: list[dict[str, object]] = []
            if relation_exists(conn, "job_observations"):
                cur.execute(
                    """
                    SELECT source_name, count(*)::bigint AS observation_count,
                           max(observed_at) AS latest_observed_at
                    FROM job_observations
                    GROUP BY source_name
                    ORDER BY source_name
                    """
                )
                observations = [dict(row) for row in cur.fetchall()]

    gates: dict[int, dict[str, dict[str, object]]] = {}
    for row in gate_rows:
        gates.setdefault(int(row["candidate_id"]), {})[str(row["gate_name"])] = row
    return {
        "candidate_rows_total": candidate_rows_total,
        "candidates": candidates,
        "gates": gates,
        "profiles": profiles,
        "bronze": bronze,
        "observations": observations,
    }


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


def fetch_detail_sample(url: str, *, timeout_seconds: int) -> dict[str, object]:
    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            headers={
                "User-Agent": "job-application-pipeline-origin-initial-proof-audit/1.0 (+read-only)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        text = response.text or ""
        profile_hits = match_terms(text, PROFILE_TERMS)
        hannover_hits = match_terms(text, HANNOVER_TERMS)
        remote_hits = match_terms(text, REMOTE_TERMS)
        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
        title = re.sub(r"<[^>]+>", " ", title_match.group(1)).strip() if title_match else ""
        return {
            "url": url,
            "final_url": str(response.url),
            "status_code": int(response.status_code),
            "response_bytes": len(response.content or b""),
            "title": re.sub(r"\s+", " ", title),
            "profile_hits": profile_hits,
            "hannover_hits": hannover_hits,
            "remote_hits": remote_hits,
            "profile_interesting": bool(profile_hits),
            "profile_hannover": bool(profile_hits and hannover_hits),
            "profile_remote": bool(profile_hits and remote_hits),
        }
    except Exception as exc:  # diagnostic surface must continue across independent sources
        return {"url": url, "error": f"{type(exc).__name__}: {exc}"}


def revalidate_candidate(
    candidate: Mapping[str, object],
    gates: Mapping[str, Mapping[str, object]],
    *,
    timeout_seconds: int,
    max_preview_links: int,
    max_detail_samples: int,
) -> dict[str, object]:
    candidate_id = int(candidate["id"])
    url = str(candidate.get("candidate_url") or "").strip()
    row: dict[str, object] = {
        "candidate_id": candidate_id,
        "company_key": str(candidate.get("company_key") or ""),
        "company_name": str(candidate.get("company_name") or ""),
        "candidate_url": url,
        "source_name_candidate": str(candidate.get("source_name_candidate") or ""),
        "source_family_candidate": str(candidate.get("source_family_candidate") or ""),
        "source_target_candidate": candidate.get("source_target_candidate"),
        "source_type_candidate": str(candidate.get("source_type_candidate") or ""),
        "candidate_status": str(candidate.get("status") or ""),
        "risk_level": str(candidate.get("risk_level") or ""),
        "historical_gates": {
            name: {
                "gate_status": gate.get("gate_status"),
                "decision": gate.get("decision"),
                "stop_reason": gate.get("stop_reason"),
                "reviewed_at": gate.get("reviewed_at"),
                "evidence": gate.get("evidence"),
            }
            for name, gate in gates.items()
        },
    }
    relevance = gates.get("relevance_gate") or {}
    row["historical_relevance_passed"] = relevance.get("gate_status") == "passed"
    row["historical_detail_urls"] = historic_detail_urls(gates)

    if not url:
        row.update({"live_status": "NO_CANDIDATE_URL", "diagnosis": ["candidate_url_missing"]})
        return row

    try:
        page = fetch_candidate_page(
            url,
            timeout_seconds=timeout_seconds,
            max_preview_links=max_preview_links,
            source_family_candidate=str(candidate.get("source_family_candidate") or "") or None,
        )
    except Exception as exc:
        row.update(
            {
                "live_status": "FETCH_ERROR",
                "error": f"{type(exc).__name__}: {exc}",
                "diagnosis": ["candidate_source_fetch_failed"],
            }
        )
        return row

    page_profile = match_terms(page.text, PROFILE_TERMS)
    page_hannover = match_terms(page.text, HANNOVER_TERMS)
    page_remote = match_terms(page.text, REMOTE_TERMS)
    lowered = normalize(page.text[:500_000])
    pagination_hints = [marker for marker in PAGINATION_MARKERS if marker in lowered]
    job_links = list(page.same_domain_job_links)
    concrete = [link for link in job_links if concrete_job_detail_url(link)]
    current_sample_pool = concrete or job_links
    historical = [link for link in historic_detail_urls(gates) if link not in current_sample_pool]
    sample_urls = (current_sample_pool + historical)[:max_detail_samples]
    detail_samples = [
        fetch_detail_sample(link, timeout_seconds=timeout_seconds)
        for link in sample_urls
    ]
    detail_interest = sum(bool(item.get("profile_interesting")) for item in detail_samples)
    detail_hannover = sum(bool(item.get("profile_hannover")) for item in detail_samples)
    detail_remote = sum(bool(item.get("profile_remote")) for item in detail_samples)

    diagnosis: list[str] = []
    if 200 <= page.status_code < 400:
        diagnosis.append("candidate_source_reachable")
    else:
        diagnosis.append("candidate_source_http_error")
    if job_links:
        diagnosis.append("current_static_job_links_present")
    else:
        diagnosis.append("no_current_static_job_links")
    if detail_interest:
        diagnosis.append("current_job_level_profile_interest_in_sample")
    if detail_hannover:
        diagnosis.append("current_job_level_profile_hannover_in_sample")
    if detail_remote:
        diagnosis.append("current_job_level_profile_remote_in_sample")
    if pagination_hints:
        diagnosis.append("source_page_exposes_pagination_hint")
    if row["historical_relevance_passed"] and not detail_interest:
        diagnosis.append("historical_listing_relevance_not_revalidated_at_job_level")

    row.update(
        {
            "live_status": "REACHABLE" if 200 <= page.status_code < 400 else "HTTP_ERROR",
            "http_status_code": page.status_code,
            "final_url": page.final_url,
            "response_bytes": page.response_bytes,
            "page_title": page.title,
            "static_job_link_count": len(job_links),
            "concrete_job_link_count": len(concrete),
            "job_link_sample": job_links[:10],
            "listing_page_profile_hits": page_profile,
            "listing_page_hannover_hits": page_hannover,
            "listing_page_remote_hits": page_remote,
            "pagination_hints": pagination_hints,
            "detail_samples": detail_samples,
            "detail_sample_count": len(detail_samples),
            "detail_profile_interesting_count": detail_interest,
            "detail_profile_hannover_count": detail_hannover,
            "detail_profile_remote_count": detail_remote,
            "diagnosis": diagnosis,
        }
    )
    return row


def profile_for_source(source_name: str, profile_rows: Sequence[Mapping[str, object]]) -> SearchProfile:
    selected = next(
        (row for row in profile_rows if str(row.get("source_name") or "") == source_name and row.get("is_active") is True),
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
            page_size=max(1000, int(selected.get("page_size") or 0)),
        )
    return SearchProfile(
        id=0,
        profile_name=f"audit_{source_name.replace(':', '_')}",
        source_name=source_name,
        search_location="Hannover",
        search_radius_km=50,
        offer_type=1,
        page_size=1000,
    )


def probe_connector(
    source_name: str,
    *,
    profile_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    registry = build_default_connector_registry()
    try:
        role = registry.role_for(source_name)
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
    try:
        connector = registry.create(source_name)
    except Exception as exc:
        return {
            "source_name": source_name,
            "implemented": True,
            "role": role.value,
            "status": "INSTANTIATION_ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }

    profile = profile_for_source(source_name, profile_rows)
    capabilities = asdict(connector.capabilities)
    caps = cap_metadata(connector)
    terms = ["*"]
    inventory_scope = "full_fetch"
    if not connector.capabilities.supports_full_fetch:
        inventory_scope = "search_scoped_union"
        terms = [
            "data",
            "analytics",
            "software",
            "python",
            "sql",
            "machine learning",
            "ai",
        ]

    all_records: list[RawJobRecord] = []
    requests: list[dict[str, object]] = []
    try:
        for term in terms:
            records, requested_url = connector.fetch_jobs(profile, SearchTerm(search_term=term))
            all_records.extend(records)
            requests.append(
                {
                    "term": term,
                    "requested_url": requested_url,
                    "record_count": len(records),
                }
            )
    except Exception as exc:
        return {
            "source_name": source_name,
            "implemented": True,
            "role": role.value,
            "connector_class": connector.__class__.__name__,
            "connector_module": connector.__class__.__module__,
            "capabilities": capabilities,
            "hard_caps": caps,
            "inventory_scope": inventory_scope,
            "status": "FETCH_ERROR",
            "error": f"{type(exc).__name__}: {exc}",
            "requests": requests,
        }

    records = unique_records(all_records)
    summaries = [record_summary(record) for record in records]
    profile_interesting = [row for row in summaries if row["profile_interesting"]]
    profile_hannover = [row for row in summaries if row["profile_hannover"]]
    profile_remote = [row for row in summaries if row["profile_remote"]]

    diagnosis: list[str] = []
    if records:
        diagnosis.append("connector_returns_current_jobs")
    else:
        diagnosis.append("connector_returns_zero_current_jobs")
    if profile_interesting:
        diagnosis.append("connector_inventory_contains_profile_interest")
    if profile_hannover:
        diagnosis.append("connector_inventory_contains_profile_hannover")
    if profile_remote:
        diagnosis.append("connector_inventory_contains_profile_remote")

    full_fetch_with_cap = bool(connector.capabilities.supports_full_fetch and caps)
    if full_fetch_with_cap:
        diagnosis.append("declared_full_fetch_has_hard_acquisition_cap")
    if connector.capabilities.supports_full_fetch and not caps:
        coverage_contract = "COMPLETE_FEED_OR_UNCAPPED_FULL_FETCH"
    elif connector.capabilities.supports_pagination:
        coverage_contract = "PAGINATION_DECLARED"
    elif full_fetch_with_cap:
        coverage_contract = "FULL_FETCH_CLAIM_BUT_CAPPED"
    else:
        coverage_contract = "SEARCH_SCOPED_WITHOUT_PAGINATION"

    return {
        "source_name": source_name,
        "implemented": True,
        "role": role.value,
        "connector_class": connector.__class__.__name__,
        "connector_module": connector.__class__.__module__,
        "capabilities": capabilities,
        "hard_caps": caps,
        "inventory_scope": inventory_scope,
        "coverage_contract": coverage_contract,
        "status": "SUCCESS",
        "requests": requests,
        "record_count": len(records),
        "profile_interesting_count": len(profile_interesting),
        "profile_hannover_count": len(profile_hannover),
        "profile_remote_count": len(profile_remote),
        "sample_jobs": summaries[:10],
        "sample_interesting_jobs": profile_interesting[:10],
        "sample_hannover_jobs": profile_hannover[:10],
        "sample_remote_jobs": profile_remote[:10],
        "diagnosis": diagnosis,
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
    parser.add_argument("--max-preview-links", type=int, default=250)
    parser.add_argument("--max-detail-samples", type=int, default=6)
    args = parser.parse_args()

    db = load_db_snapshot()
    candidates = list(db["candidates"])
    gates_by_candidate = db["gates"]
    profile_rows = list(db["profiles"])

    candidate_rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=args.candidate_workers) as pool:
        futures = {
            pool.submit(
                revalidate_candidate,
                candidate,
                gates_by_candidate.get(int(candidate["id"]), {}),
                timeout_seconds=args.timeout_seconds,
                max_preview_links=args.max_preview_links,
                max_detail_samples=args.max_detail_samples,
            ): int(candidate["id"])
            for candidate in candidates
        }
        for future in as_completed(futures):
            candidate_rows.append(future.result())
    candidate_rows.sort(key=lambda row: (str(row["company_key"]), int(row["candidate_id"])))

    registry = build_default_connector_registry()
    concrete_sources: set[str] = {
        str(row.get("source_name_candidate") or "").strip()
        for row in candidates
        if str(row.get("source_name_candidate") or "").strip()
    }
    concrete_sources.update(
        str(row.get("source_name") or "").strip()
        for row in profile_rows
        if str(row.get("source_name") or "").strip()
    )
    concrete_sources.update(registry.exact_factories)

    connector_rows = [
        probe_connector(source_name, profile_rows=profile_rows)
        for source_name in sorted(concrete_sources)
    ]
    connector_by_source = {str(row["source_name"]): row for row in connector_rows}

    bronze_by_source = {str(row["source_name"]): row for row in db["bronze"]}
    observations_by_source = {str(row["source_name"]): row for row in db["observations"]}

    for row in candidate_rows:
        source_name = str(row.get("source_name_candidate") or "")
        connector = connector_by_source.get(source_name)
        row["connector_probe"] = connector
        row["historical_bronze"] = bronze_by_source.get(source_name)
        row["historical_observations"] = observations_by_source.get(source_name)
        diagnosis = list(row.get("diagnosis") or [])
        if connector and connector.get("status") == "SUCCESS":
            connector_count = int(connector.get("record_count") or 0)
            static_count = int(row.get("static_job_link_count") or 0)
            if connector_count == 0 and static_count > 0:
                diagnosis.append("connector_zero_while_source_page_exposes_job_links")
            if connector_count > 0:
                diagnosis.append("implemented_connector_initial_proof_live")
            if int(connector.get("profile_interesting_count") or 0) > 0:
                diagnosis.append("implemented_connector_profile_interest_live")
            if static_count > connector_count and connector.get("coverage_contract") == "FULL_FETCH_CLAIM_BUT_CAPPED":
                diagnosis.append("connector_bounded_below_static_source_lower_bound")
        else:
            if int(row.get("static_job_link_count") or 0) > 0:
                diagnosis.append("source_has_job_links_without_working_registered_connector")
            if int(row.get("detail_profile_interesting_count") or 0) > 0:
                diagnosis.append("interesting_job_sample_without_working_registered_connector")
        row["diagnosis"] = list(dict.fromkeys(diagnosis))

    origin_connectors = [
        row for row in connector_rows
        if row.get("role") == SourceRole.EMPLOYER_ORIGIN.value
    ]
    successful_origin = [row for row in origin_connectors if row.get("status") == "SUCCESS"]
    sources_with_jobs = [row for row in successful_origin if int(row.get("record_count") or 0) > 0]
    sources_with_interest = [
        row for row in successful_origin
        if int(row.get("profile_interesting_count") or 0) > 0
    ]
    sources_with_hannover = [
        row for row in successful_origin
        if int(row.get("profile_hannover_count") or 0) > 0
    ]
    sources_with_remote = [
        row for row in successful_origin
        if int(row.get("profile_remote_count") or 0) > 0
    ]
    capped_full_fetch = [
        row for row in successful_origin
        if row.get("coverage_contract") == "FULL_FETCH_CLAIM_BUT_CAPPED"
    ]
    reachable_candidates = [row for row in candidate_rows if row.get("live_status") == "REACHABLE"]
    candidate_job_links = [row for row in candidate_rows if int(row.get("static_job_link_count") or 0) > 0]
    candidate_interest = [row for row in candidate_rows if int(row.get("detail_profile_interesting_count") or 0) > 0]
    candidate_hannover = [row for row in candidate_rows if int(row.get("detail_profile_hannover_count") or 0) > 0]
    candidate_remote = [row for row in candidate_rows if int(row.get("detail_profile_remote_count") or 0) > 0]

    summary = {
        "candidate_rows_total": db["candidate_rows_total"],
        "candidate_companies_latest": len(candidate_rows),
        "historical_relevance_passed": sum(bool(row.get("historical_relevance_passed")) for row in candidate_rows),
        "candidate_sources_reachable_now": len(reachable_candidates),
        "candidate_sources_with_static_job_links_now": len(candidate_job_links),
        "candidate_static_job_links_lower_bound": sum(int(row.get("static_job_link_count") or 0) for row in candidate_rows),
        "candidate_sources_with_profile_interest_in_detail_sample": len(candidate_interest),
        "candidate_sources_with_profile_hannover_in_detail_sample": len(candidate_hannover),
        "candidate_sources_with_profile_remote_in_detail_sample": len(candidate_remote),
        "origin_connector_targets_tested": len(origin_connectors),
        "origin_connector_targets_success": len(successful_origin),
        "origin_connector_targets_with_jobs": len(sources_with_jobs),
        "origin_connector_total_records": sum(int(row.get("record_count") or 0) for row in successful_origin),
        "origin_connector_targets_with_profile_interest": len(sources_with_interest),
        "origin_connector_profile_interesting_records": sum(int(row.get("profile_interesting_count") or 0) for row in successful_origin),
        "origin_connector_targets_with_profile_hannover": len(sources_with_hannover),
        "origin_connector_profile_hannover_records": sum(int(row.get("profile_hannover_count") or 0) for row in successful_origin),
        "origin_connector_targets_with_profile_remote": len(sources_with_remote),
        "origin_connector_profile_remote_records": sum(int(row.get("profile_remote_count") or 0) for row in successful_origin),
        "full_fetch_claims_with_hard_caps": len(capped_full_fetch),
        "database_writes": 0,
    }

    report = {
        "schema_version": "jap.origin_initial_proof_revalidation.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": {
            "candidate_pool": "latest row per company_key across employer_origin_source_candidates",
            "implemented_targets": "all concrete candidate/profile/exact-registry source names resolvable by canonical registry",
            "historic_relevance_semantics": "one listing page; listing-page text only",
            "job_level_interest_terms": list(PROFILE_TERMS),
            "hannover_terms": list(HANNOVER_TERMS),
            "remote_terms": list(REMOTE_TERMS),
            "candidate_detail_sampling": args.max_detail_samples,
            "candidate_preview_link_limit": args.max_preview_links,
            "read_only": True,
        },
        "summary": summary,
        "candidates": candidate_rows,
        "connectors": connector_rows,
        "profiles": profile_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(json_safe(report), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    print("=" * 72)
    print("JAP ORIGIN INITIAL-PROOF REVALIDATION")
    print("=" * 72)
    for key, value in summary.items():
        print(f"{key.upper()}={value}")
    print("--- IMPLEMENTED EMPLOYER-ORIGIN TARGETS ---")
    for row in origin_connectors:
        print(
            "CONNECTOR="
            f"{row['source_name']}|status={row.get('status')}|"
            f"jobs={row.get('record_count', '-')}|interest={row.get('profile_interesting_count', '-')}|"
            f"hannover={row.get('profile_hannover_count', '-')}|remote={row.get('profile_remote_count', '-')}|"
            f"coverage={row.get('coverage_contract', '-')}|caps={row.get('hard_caps', {})}"
        )
    print("--- CANDIDATE SOURCES ---")
    for row in candidate_rows:
        print(
            "CANDIDATE="
            f"{row['company_key']}|source={row.get('source_name_candidate')}|"
            f"live={row.get('live_status')}|links={row.get('static_job_link_count', 0)}|"
            f"sample_interest={row.get('detail_profile_interesting_count', 0)}|"
            f"sample_hannover={row.get('detail_profile_hannover_count', 0)}|"
            f"sample_remote={row.get('detail_profile_remote_count', 0)}|"
            f"implemented={(row.get('connector_probe') or {}).get('status', 'NOT_REGISTERED')}"
        )
    print("DATABASE_WRITES=0")
    print(f"artifact={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
