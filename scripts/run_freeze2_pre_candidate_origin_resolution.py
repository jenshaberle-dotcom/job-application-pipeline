"""Resolve Freeze-II S0.6 review companies to direct Employer-Origin/ATS sources.

This is a pre-candidate read-only adapter over the existing generic F1 discovery
engine. It deliberately runs *before* employer_origin_source_candidates rows are
created, so aggregator discovery evidence cannot become candidate/source
authority by persistence order.

Input: S0.6 sensor candidate-expansion review artifact.
Network: bounded Wikidata P856 + bounded direct HTTP probes only.
Provider/search API requests: 0.
Writes: 0.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Mapping

import requests

from scripts.run_origin_source_discovery_agent import (
    HTTP_USER_AGENT,
    HttpDiscoveryClient,
)
from src.search_intelligence.official_domain_evidence import (
    resolve_wikidata_official_domains,
)
from src.search_intelligence.origin_jobspace_discovery import (
    discover_official_origin_jobspace,
)


SCHEMA = "job_application_pipeline.freeze2_pre_candidate_origin_resolution.v1"
ELIGIBLE_REVIEW_DECISIONS = {
    "manual_review_required",
    "create_candidate_recommended",
}


def _request_json(
    url: str,
    params: Mapping[str, str],
    *,
    timeout_seconds: float,
) -> Mapping[str, object]:
    response = requests.get(
        url,
        params=dict(params),
        timeout=timeout_seconds,
        headers={
            "User-Agent": HTTP_USER_AGENT,
            "Accept": "application/json",
        },
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, Mapping) else {}


def select_review_items(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    review = payload.get("review")
    if not isinstance(review, Mapping):
        return []
    raw_items = review.get("items")
    if not isinstance(raw_items, list):
        return []

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("decision") or "") not in ELIGIBLE_REVIEW_DECISIONS:
            continue
        company_key = str(raw.get("company_key") or "").strip()
        company_name = str(raw.get("company_name") or "").strip()
        if not company_key or not company_name or company_key in seen:
            continue
        seen.add(company_key)
        selected.append(
            {
                "company_key": company_key,
                "company_name": company_name,
                "sensor_decision": str(raw.get("decision") or ""),
                "sensor_evidence_count": int(raw.get("evidence_count") or 0),
                "sensor_source_name": str(raw.get("source_name") or ""),
            }
        )
    return selected


def resolution_state(decision: str, selected_url: str | None) -> str:
    if decision == "origin_url_candidate_selected" and selected_url:
        return "direct_source_resolved"
    if decision == "manual_review_required":
        return "direct_source_review_required"
    return "direct_source_unresolved"


def resolve_company(
    item: Mapping[str, Any],
    *,
    target_location: str,
    timeout_seconds: float,
    http_request_cap: int,
    max_generated_candidates: int,
    wikidata_max_entities: int,
) -> dict[str, Any]:
    company_key = str(item["company_key"])
    company_name = str(item["company_name"])

    try:
        official = resolve_wikidata_official_domains(
            company_name,
            request_json=lambda url, params: _request_json(
                url,
                params,
                timeout_seconds=timeout_seconds,
            ),
            max_entities=wikidata_max_entities,
        )
        wikidata_status = "ok"
    except (requests.RequestException, ValueError, TypeError) as exc:
        official = ()
        wikidata_status = f"unavailable:{exc.__class__.__name__}"

    http = HttpDiscoveryClient(
        timeout_seconds=timeout_seconds,
        max_requests=http_request_cap,
    )
    expanded = discover_official_origin_jobspace(
        company_key=company_key,
        company_name=company_name,
        official_domain_urls=[e.url for e in official],
        target_location=target_location,
        probe=http.probe,
        fetch_page=http.fetch_page,
        max_generated_candidates=max_generated_candidates,
    )
    origin = expanded.origin
    state = resolution_state(origin.decision, origin.selected_url)

    return {
        **dict(item),
        "resolution_state": state,
        "origin_decision": origin.decision,
        "selected_url": origin.selected_url,
        "selected_domain": origin.selected_domain,
        "confidence_score": origin.confidence_score,
        "risk_level": origin.risk_level,
        "reason": origin.reason,
        "candidate_count": origin.candidate_count,
        "assessed_count": origin.assessed_count,
        "ats_families": list(expanded.ats_families),
        "surface_page_count": expanded.surface_page_count,
        "discovered_jobspace_url_count": expanded.discovered_jobspace_url_count,
        "direct_http_request_count": http.request_count,
        "wikidata_status": wikidata_status,
        "official_domain_evidence": [asdict(e) for e in official],
        "alternatives": [
            {
                "url": a.final_url or a.normalized_url or a.candidate.url,
                "decision": a.decision,
                "total_score": a.total_score,
                "identity_score": a.identity_score,
                "career_score": a.career_score,
                "provider": a.candidate.provider,
            }
            for a in origin.alternatives[:5]
        ],
    }


def build_summary(results: list[Mapping[str, Any]]) -> dict[str, int]:
    states = {
        "direct_source_resolved": 0,
        "direct_source_review_required": 0,
        "direct_source_unresolved": 0,
    }
    for result in results:
        state = str(result.get("resolution_state") or "")
        if state in states:
            states[state] += 1
    return {
        "company_count": len(results),
        **states,
        "provider_search_requests": 0,
        "database_writes": 0,
        "candidate_creations": 0,
        "source_activations": 0,
        "total_direct_http_requests": sum(
            int(r.get("direct_http_request_count") or 0) for r in results
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--timeout-seconds", type=float, default=6.0)
    parser.add_argument("--http-request-cap", type=int, default=24)
    parser.add_argument("--max-generated-candidates", type=int, default=18)
    parser.add_argument("--wikidata-max-entities", type=int, default=3)
    args = parser.parse_args()

    if not 1 <= args.http_request_cap <= 48:
        raise SystemExit("--http-request-cap must be between 1 and 48")
    if not 1 <= args.max_generated_candidates <= 30:
        raise SystemExit("--max-generated-candidates must be between 1 and 30")
    if not 1 <= args.wikidata_max_entities <= 5:
        raise SystemExit("--wikidata-max-entities must be between 1 and 5")

    review_payload = json.loads(args.review_json.read_text(encoding="utf-8"))
    items = select_review_items(review_payload)
    results = [
        resolve_company(
            item,
            target_location=args.target_location,
            timeout_seconds=args.timeout_seconds,
            http_request_cap=args.http_request_cap,
            max_generated_candidates=args.max_generated_candidates,
            wikidata_max_entities=args.wikidata_max_entities,
        )
        for item in items
    ]
    report = {
        "schema": SCHEMA,
        "source_review_schema": review_payload.get("schema"),
        "source_review_company_count": len(items),
        "summary": build_summary(results),
        "results": results,
        "boundary": {
            "search_provider_requests": 0,
            "database_reads": 0,
            "database_writes": 0,
            "candidate_creation": 0,
            "candidate_url_write": 0,
            "connector_registration": 0,
            "source_activation": 0,
            "bronze_silver_product_writes": 0,
            "aggregator_url_authority": 0,
            "network_scope": "wikidata_p856_plus_bounded_direct_http_only",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]
    print("============================================")
    print("FREEZE-II PRE-CANDIDATE ORIGIN RESOLUTION")
    print("============================================")
    print(f"COMPANIES={summary['company_count']}")
    print(f"DIRECT_SOURCE_RESOLVED={summary['direct_source_resolved']}")
    print(f"DIRECT_SOURCE_REVIEW_REQUIRED={summary['direct_source_review_required']}")
    print(f"DIRECT_SOURCE_UNRESOLVED={summary['direct_source_unresolved']}")
    print(f"DIRECT_HTTP_REQUESTS={summary['total_direct_http_requests']}")
    print("SEARCH_PROVIDER_REQUESTS=0")
    print("DATABASE_WRITES=0")
    print("CANDIDATE_CREATIONS=0")
    print("SOURCE_ACTIVATIONS=0")
    for result in results:
        print(
            "RESULT="
            f"{result['company_key']}|{result['resolution_state']}|"
            f"{result.get('selected_url') or '-'}|"
            f"{result.get('origin_decision')}"
        )
    print(f"artifact={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
