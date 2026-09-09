"""Bounded read-only Search-Intelligence probe for all Employer-Origin candidates.

Per source:
  1. source alive?
  2. any current job proof?
  3. targeted search with company vocabulary learned from market sensors
  4. if no interesting result, one bounded vocabulary expansion
  5. if still no interesting result, require an operator manual test and move on

No full-site crawl is performed. HTML sources get one listing-page request and at
most three detail samples. Existing connectors keep their own request bounds.
Official single-feed/API sources may be requested once and filtered locally.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
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

from scripts.run_employer_origin_connector_candidate_agent import concrete_job_detail_url
from scripts.run_employer_origin_gate_agent import (
    DEFAULT_PROFILE_TERMS,
    DEFAULT_REMOTE_TERMS,
    DatabaseConfig,
    fetch_candidate_page,
)
from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.registry import SourceRole, build_default_connector_registry


DEFAULT_OUTPUT = Path("/tmp/jap-origin-search-intelligence-probe.json")
INITIAL_TERM_LIMIT = 5
EXPANSION_TERM_LIMIT = 10
MAX_CONNECTOR_CALLS = 8
MAX_STATIC_LINKS = 80
MAX_DETAIL_SAMPLES = 3

HANNOVER_TERMS = (
    "hannover", "hanover", "region hannover", "langenhagen", "garbsen",
    "laatzen", "isernhagen", "lehrte", "seelze", "hildesheim", "celle",
)
REMOTE_TERMS = tuple(dict.fromkeys(DEFAULT_REMOTE_TERMS + ("work from home", "remote work")))
FALLBACK_TERMS = tuple(
    dict.fromkeys(
        DEFAULT_PROFILE_TERMS
        + (
            "data engineer", "data engineering", "data platform", "data warehouse",
            "machine learning", "ml", "cloud", "devops", "automation", "reliability",
        )
    )
)
PAGINATION_MARKERS = (
    "page=2", "offset=", "start=", "load more", "mehr laden", "weitere stellen",
    "weitere jobs", "next page", "nächste seite", "pagination",
)


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def term_in_text(text: str, term: str) -> bool:
    haystack = norm(text)
    needle = norm(term)
    if not needle:
        return False
    if len(needle) <= 3 and re.fullmatch(r"[a-z0-9+#.]+", needle):
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None
    return needle in haystack


def hits(text: str, terms: Sequence[str]) -> list[str]:
    return [term for term in terms if term_in_text(text, term)]


def unique_terms(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        key = norm(value)
        if value and key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def recursive_text(value: object, limit: int = 180_000) -> str:
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
        if text:
            chunk = text[: max(0, limit - size)]
            parts.append(chunk)
            size += len(chunk) + 1

    visit(value)
    return " ".join(parts)


def relation_exists(conn: psycopg.Connection[Any], name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{name}",))
        row = cur.fetchone()
    return bool(row and row["relation"] is not None)


def ensure_read_only(conn: psycopg.Connection[Any]) -> None:
    conn.execute("SET TRANSACTION READ ONLY")
    with conn.cursor() as cur:
        cur.execute("SHOW transaction_read_only")
        row = cur.fetchone()
    value = str(row["transaction_read_only"] if row else "")
    if value != "on":
        raise RuntimeError(f"AUDIT_REFUSED transaction_read_only={value!r}")


def load_db() -> dict[str, object]:
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
                    SELECT observed_term, max(overall_value_score) AS overall_value_score,
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

            profiles: list[dict[str, object]] = []
            active_terms: list[dict[str, object]] = []
            if relation_exists(conn, "search_profiles"):
                cur.execute(
                    """
                    SELECT id, profile_name, source_name, search_location,
                           search_radius_km, offer_type, page_size, is_active
                    FROM search_profiles
                    ORDER BY source_name, profile_name, id
                    """
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

    return {
        "candidates": candidates,
        "vocabulary": vocabulary,
        "value_scores": value_scores,
        "reassessment": reassessment,
        "profiles": profiles,
        "active_terms": active_terms,
    }


def build_term_plan(
    candidate: Mapping[str, object],
    *,
    vocabulary_by_company: Mapping[str, Sequence[Mapping[str, object]]],
    value_by_term: Mapping[str, float],
    reassessment_by_candidate: Mapping[int, Mapping[str, object]],
    active_terms_by_source: Mapping[str, Sequence[str]],
    global_value_terms: Sequence[str],
) -> dict[str, object]:
    company_key = str(candidate.get("company_key") or "")
    source_name = str(candidate.get("source_name_candidate") or "")
    candidate_id = int(candidate["id"])
    rows = list(vocabulary_by_company.get(company_key, ()))
    enriched: list[dict[str, object]] = []
    for row in rows:
        term = str(row.get("observed_term") or "")
        enriched.append(
            {
                "term": term,
                "observation_count": int(row.get("observation_count") or 0),
                "last_seen_at": row.get("last_seen_at"),
                "sensor_sources": list(row.get("sensor_sources") or []),
                "value_score": value_by_term.get(norm(term)),
            }
        )
    enriched.sort(
        key=lambda row: (
            -(float(row["value_score"]) if row["value_score"] is not None else -1.0),
            -int(row["observation_count"]),
            str(row["term"]),
        )
    )
    learned = [str(row["term"]) for row in enriched]
    current = list(active_terms_by_source.get(source_name, ()))
    reassessment = reassessment_by_candidate.get(candidate_id) or {}
    suggested = [str(term) for term in (reassessment.get("suggested_search_terms") or [])]

    initial = unique_terms(learned[:INITIAL_TERM_LIMIT] + current)[:INITIAL_TERM_LIMIT]
    if not initial:
        initial = list(FALLBACK_TERMS[:INITIAL_TERM_LIMIT])
    expansion = unique_terms(
        learned[INITIAL_TERM_LIMIT:] + suggested + current + list(global_value_terms) + list(FALLBACK_TERMS)
    )
    initial_keys = {norm(term) for term in initial}
    expansion = [term for term in expansion if norm(term) not in initial_keys][:EXPANSION_TERM_LIMIT]
    interest_terms = unique_terms(initial + expansion)
    return {
        "company_vocabulary": enriched,
        "company_vocabulary_count": len(enriched),
        "vocabulary_available": bool(enriched),
        "current_source_terms": current,
        "reassessment_terms": suggested,
        "initial_terms": initial,
        "expansion_terms": expansion,
        "interest_terms": interest_terms,
    }


def source_probe(candidate: Mapping[str, object], plan: Mapping[str, object], timeout: int) -> dict[str, object]:
    url = str(candidate.get("candidate_url") or "").strip()
    if not url:
        return {"status": "NO_CANDIDATE_URL", "job_proof": False}
    try:
        page = fetch_candidate_page(
            url,
            timeout_seconds=timeout,
            max_preview_links=MAX_STATIC_LINKS,
            source_family_candidate=str(candidate.get("source_family_candidate") or "") or None,
        )
    except Exception as exc:
        return {"status": "FETCH_ERROR", "job_proof": False, "error": f"{type(exc).__name__}: {exc}"}

    links = list(page.same_domain_job_links)
    concrete = [link for link in links if concrete_job_detail_url(link)]
    sample_urls = (concrete or links)[:MAX_DETAIL_SAMPLES]
    detail_samples: list[dict[str, object]] = []
    for detail_url in sample_urls:
        try:
            response = requests.get(
                detail_url,
                timeout=timeout,
                headers={"User-Agent": "job-application-pipeline-origin-search-probe/1.0 (+read-only)"},
            )
            text = response.text or ""
            interest = hits(text, plan["interest_terms"])
            local = hits(text, HANNOVER_TERMS)
            remote = hits(text, REMOTE_TERMS)
            detail_samples.append(
                {
                    "url": detail_url,
                    "status_code": response.status_code,
                    "interest_hits": interest,
                    "hannover_hits": local,
                    "remote_hits": remote,
                    "interesting": bool(interest),
                    "interesting_hannover_or_remote": bool(interest and (local or remote)),
                }
            )
        except Exception as exc:
            detail_samples.append({"url": detail_url, "error": f"{type(exc).__name__}: {exc}"})

    page_text = page.text[:500_000]
    return {
        "status": "REACHABLE" if 200 <= page.status_code < 400 else "HTTP_ERROR",
        "status_code": page.status_code,
        "final_url": page.final_url,
        "job_proof": bool(links),
        "job_link_count_lower_bound": len(links),
        "job_link_sample": links[:10],
        "listing_interest_hits": hits(page_text, plan["interest_terms"]),
        "pagination_hints": [marker for marker in PAGINATION_MARKERS if marker in norm(page_text)],
        "detail_samples": detail_samples,
        "interesting_sample_count": sum(bool(row.get("interesting")) for row in detail_samples),
        "interesting_local_remote_sample_count": sum(bool(row.get("interesting_hannover_or_remote")) for row in detail_samples),
    }


def connector_caps(connector: object) -> dict[str, int]:
    module = importlib.import_module(connector.__class__.__module__)
    result: dict[str, int] = {}
    for name in ("MAX_DETAIL_PAGES", "MAX_DETAIL_PAGES_HARD_LIMIT", "MAX_LISTING_PAGES", "MAX_PAGES"):
        value = getattr(module, name, None)
        if isinstance(value, int) and value > 0:
            result[name] = value
    value = getattr(connector, "max_detail_pages", None)
    if isinstance(value, int) and value > 0:
        result["INSTANCE_MAX_DETAIL_PAGES"] = value
    return result


def profile_for(source_name: str, profiles: Sequence[Mapping[str, object]]) -> SearchProfile:
    row = next(
        (item for item in profiles if item.get("source_name") == source_name and item.get("is_active") is True),
        None,
    ) or next((item for item in profiles if item.get("source_name") == source_name), None)
    if row:
        return SearchProfile(
            id=int(row.get("id") or 0),
            profile_name=str(row.get("profile_name") or f"audit_{source_name}"),
            source_name=source_name,
            search_location=str(row.get("search_location") or "Hannover"),
            search_radius_km=int(row.get("search_radius_km") or 50),
            offer_type=int(row.get("offer_type") or 1),
            page_size=max(25, min(100, int(row.get("page_size") or 25))),
        )
    return SearchProfile(0, f"audit_{source_name.replace(':', '_')}", source_name, "Hannover", 50, 1, 25)


def summarize_record(record: RawJobRecord, query_term: str, interest_terms: Sequence[str]) -> dict[str, object]:
    raw = record.raw_data if isinstance(record.raw_data, Mapping) else {}
    text = recursive_text({"url": record.source_url, "job": raw.get("job"), "result_card": raw.get("result_card")})
    interest = hits(text, interest_terms)
    local = hits(text, HANNOVER_TERMS)
    remote = hits(text, REMOTE_TERMS)
    query_match = term_in_text(text, query_term)
    title = ""
    for path in (("result_card", "title"), ("job", "title"), ("job", "name"), ("job", "titel")):
        current: object = raw
        for part in path:
            current = current.get(part) if isinstance(current, Mapping) else None
        if current:
            title = str(current)
            break
    return {
        "external_job_id": record.external_job_id,
        "title": title,
        "source_url": record.source_url,
        "query_term": query_term,
        "query_match": query_match,
        "interest_hits": interest,
        "hannover_hits": local,
        "remote_hits": remote,
        "interesting": bool(interest or query_match),
        "interesting_hannover_or_remote": bool((interest or query_match) and (local or remote)),
    }


def connector_probe(
    source_name: str,
    plan: Mapping[str, object],
    profiles: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    registry = build_default_connector_registry()
    try:
        role = registry.role_for(source_name)
        connector = registry.create(source_name)
    except Exception as exc:
        return {"implemented": False, "status": "NOT_REGISTERED", "error": f"{type(exc).__name__}: {exc}"}
    if role != SourceRole.EMPLOYER_ORIGIN:
        return {"implemented": True, "status": "NON_ORIGIN", "role": role.value}

    profile = profile_for(source_name, profiles)
    caps = connector_caps(connector)
    capabilities = asdict(connector.capabilities)
    single_inventory = bool(connector.capabilities.supports_full_fetch and not connector.capabilities.supports_keyword and not caps)
    requests: list[dict[str, object]] = []
    records: list[tuple[RawJobRecord, str]] = []
    errors: list[dict[str, str]] = []

    def call(term: str) -> None:
        try:
            fetched, requested_url = connector.fetch_jobs(profile, SearchTerm(search_term=term))
            records.extend((record, term) for record in fetched)
            requests.append({"term": term, "requested_url": requested_url, "record_count": len(fetched)})
        except Exception as exc:
            errors.append({"term": term, "error": f"{type(exc).__name__}: {exc}"})

    initial = list(plan["initial_terms"])
    expansion = list(plan["expansion_terms"])
    if single_inventory:
        call(initial[0])
    else:
        for term in initial:
            if len(requests) + len(errors) >= MAX_CONNECTOR_CALLS:
                break
            call(term)
            summaries = _dedupe_summaries(records, plan["interest_terms"])
            if any(row["interesting"] for row in summaries):
                break

    summaries = _dedupe_summaries(records, plan["interest_terms"])
    expansion_used = False
    if not any(row["interesting"] for row in summaries) and not single_inventory:
        expansion_used = True
        for term in expansion:
            if len(requests) + len(errors) >= MAX_CONNECTOR_CALLS:
                break
            call(term)
            summaries = _dedupe_summaries(records, plan["interest_terms"])
            if any(row["interesting"] for row in summaries):
                break

    if single_inventory:
        pagination_contract = "SINGLE_PROVIDER_FEED_OR_API"
    elif connector.capabilities.supports_pagination:
        pagination_contract = "PAGINATION_DECLARED"
    elif caps:
        pagination_contract = "BOUNDED_DETAIL_SELECTION"
    else:
        pagination_contract = "NO_PAGINATION_CONTRACT"

    return {
        "implemented": True,
        "status": "SUCCESS" if requests else "FETCH_ERROR",
        "connector_class": connector.__class__.__name__,
        "capabilities": capabilities,
        "hard_caps": caps,
        "single_inventory_endpoint": single_inventory,
        "pagination_contract": pagination_contract,
        "initial_terms": initial,
        "expansion_terms": expansion,
        "expansion_used": expansion_used,
        "requests": requests,
        "errors": errors,
        "job_proof_count": len(summaries),
        "interesting_count": sum(bool(row["interesting"]) for row in summaries),
        "interesting_local_remote_count": sum(bool(row["interesting_hannover_or_remote"]) for row in summaries),
        "samples": summaries[:12],
    }


def _dedupe_summaries(records: Sequence[tuple[RawJobRecord, str]], interest_terms: Sequence[str]) -> list[dict[str, object]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, object]] = []
    for record, term in records:
        key = (record.source_name, str(record.external_job_id or record.source_url))
        if key in seen:
            continue
        seen.add(key)
        result.append(summarize_record(record, term, interest_terms))
    return result


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
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()

    db = load_db()
    candidates = list(db["candidates"])
    vocabulary_by_company: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in db["vocabulary"]:
        vocabulary_by_company[str(row.get("company_key") or "")].append(row)
    value_by_term = {
        norm(row.get("observed_term")): float(row.get("overall_value_score") or 0)
        for row in db["value_scores"]
    }
    reassessment_by_candidate = {int(row["candidate_id"]): row for row in db["reassessment"]}
    active_terms_by_source: dict[str, list[str]] = defaultdict(list)
    for row in db["active_terms"]:
        active_terms_by_source[str(row.get("source_name") or "")].append(str(row.get("search_term") or ""))
    global_value_terms = [str(row.get("observed_term") or "") for row in db["value_scores"][:30]]

    rows: list[dict[str, object]] = []
    for candidate in candidates:
        plan = build_term_plan(
            candidate,
            vocabulary_by_company=vocabulary_by_company,
            value_by_term=value_by_term,
            reassessment_by_candidate=reassessment_by_candidate,
            active_terms_by_source=active_terms_by_source,
            global_value_terms=global_value_terms,
        )
        page = source_probe(candidate, plan, args.timeout)
        source_name = str(candidate.get("source_name_candidate") or "")
        connector = connector_probe(source_name, plan, db["profiles"]) if source_name else {"implemented": False, "status": "NO_SOURCE_NAME"}

        any_job = bool(page.get("job_proof")) or int(connector.get("job_proof_count") or 0) > 0
        interesting = int(page.get("interesting_sample_count") or 0) > 0 or int(connector.get("interesting_count") or 0) > 0
        local_remote = int(page.get("interesting_local_remote_sample_count") or 0) > 0 or int(connector.get("interesting_local_remote_count") or 0) > 0
        pagination_gap = bool(page.get("pagination_hints")) and connector.get("pagination_contract") in {"BOUNDED_DETAIL_SELECTION", "NO_PAGINATION_CONTRACT", None}

        state = "SOURCE_UNRESOLVED"
        if page.get("status") == "REACHABLE":
            state = "SOURCE_ALIVE"
        if any_job:
            state = "GENERIC_JOB_PROOF"
        if interesting:
            state = "INTERESTING_JOB_PROOF"
        if local_remote:
            state = "INTERESTING_HANNOVER_OR_REMOTE_PROOF"
        next_action = "NEXT_SOURCE" if interesting else "OPERATOR_MANUAL_TEST"

        rows.append(
            {
                "candidate_id": candidate["id"],
                "company_key": candidate["company_key"],
                "company_name": candidate["company_name"],
                "candidate_status": candidate["status"],
                "candidate_url": candidate["candidate_url"],
                "source_name": source_name,
                "term_plan": plan,
                "source_probe": page,
                "connector_probe": connector,
                "any_job_proof": any_job,
                "interesting_job_proof": interesting,
                "interesting_hannover_or_remote_proof": local_remote,
                "pagination_gap_suspected": pagination_gap,
                "state": state,
                "next_action": next_action,
            }
        )

    rows.sort(key=lambda row: str(row["company_key"]))
    summary = {
        "candidate_companies": len(rows),
        "company_vocabulary_rows": len(db["vocabulary"]),
        "candidates_with_learned_vocabulary": sum(bool(row["term_plan"]["vocabulary_available"]) for row in rows),
        "search_term_value_rows": len(db["value_scores"]),
        "sources_reachable": sum(row["source_probe"].get("status") == "REACHABLE" for row in rows),
        "sources_with_any_job_proof": sum(bool(row["any_job_proof"]) for row in rows),
        "sources_with_interesting_job_proof": sum(bool(row["interesting_job_proof"]) for row in rows),
        "sources_with_interesting_hannover_or_remote_proof": sum(bool(row["interesting_hannover_or_remote_proof"]) for row in rows),
        "registered_connectors": sum(bool(row["connector_probe"].get("implemented")) for row in rows),
        "registered_connectors_with_any_job_proof": sum(bool(row["connector_probe"].get("job_proof_count")) for row in rows),
        "registered_connectors_with_interesting_job_proof": sum(bool(row["connector_probe"].get("interesting_count")) for row in rows),
        "operator_manual_tests_required": sum(row["next_action"] == "OPERATOR_MANUAL_TEST" for row in rows),
        "pagination_gaps_suspected": sum(bool(row["pagination_gap_suspected"]) for row in rows),
        "database_writes": 0,
    }

    report = {
        "schema_version": "jap.origin_search_intelligence_probe.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "contract": {
            "full_site_scrape": False,
            "html_listing_pages": 1,
            "detail_sample_limit": MAX_DETAIL_SAMPLES,
            "targeted_connector_call_limit": MAX_CONNECTOR_CALLS,
            "official_single_feed_api_request": True,
            "vocabulary_first": True,
            "expansion_then_operator": True,
            "database_read_only": True,
        },
        "summary": summary,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(json_safe(report), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    print("=" * 72)
    print("JAP ORIGIN SEARCH INTELLIGENCE PROBE")
    print("=" * 72)
    for key, value in summary.items():
        print(f"{key.upper()}={value}")
    print("---")
    for row in rows:
        probe = row["connector_probe"]
        plan = row["term_plan"]
        print(
            "SOURCE="
            f"{row['company_key']}|origin={row['source_name']}|alive={row['source_probe'].get('status')}|"
            f"any_jobs={row['any_job_proof']}|interesting={row['interesting_job_proof']}|"
            f"hannover_remote={row['interesting_hannover_or_remote_proof']}|vocab={plan['company_vocabulary_count']}|"
            f"terms={plan['initial_terms']}|expanded={probe.get('expansion_used', False)}|"
            f"connector={probe.get('status')}|connector_jobs={probe.get('job_proof_count', 0)}|"
            f"pagination_gap={row['pagination_gap_suspected']}|next={row['next_action']}"
        )
    print("DATABASE_WRITES=0")
    print(f"artifact={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
