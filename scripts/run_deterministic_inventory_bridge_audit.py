from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qsl, urlparse

import requests

from scripts.run_deterministic_inventory_surface_audit import _origin_from_layer
from src.connectors.employer_origin_acquisition import (
    explicit_root_delegated_listing_hosts,
    looks_like_listing_navigation,
    parse_page,
    url_host,
)
from src.connectors.employer_origin_ats_navigation import (
    authorized_ats_provider,
    provider_detail_urls,
    provider_listing_urls,
)
from src.search_intelligence.ats_provider_registry import recognize_ats_provider

SCHEMA = "job_application_pipeline.deterministic_inventory_bridge_audit.v1"
MAX_BODY_BYTES = 5_000_000
JOB_MARKERS = (
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "stelle",
    "stellen",
    "vacan",
    "recruit",
    "bewerb",
)
BRIDGE_SIGNALS = {
    "authorized_provider_without_executable_inventory",
    "same_origin_jobish_anchor_not_classified",
    "external_jobish_anchor_not_promoted",
}


def _jobish(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in JOB_MARKERS)


def safe_url_shape(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    return {
        "scheme": parsed.scheme.casefold(),
        "host": (parsed.hostname or "").casefold(),
        "path": parsed.path or "/",
        "query_keys": sorted({key for key, _value in parse_qsl(parsed.query, keep_blank_values=True)}),
    }


def _label(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()[:160]


def classify_bridge(
    item: dict[str, Any],
    *,
    html: str,
    final_url: str,
    status: int,
) -> dict[str, object]:
    page = parse_page(
        requested_url=final_url,
        html=html,
        final_url=final_url,
        status_code=status,
    )
    origin_host = url_host(final_url)
    allowed_hosts = {origin_host} if origin_host else set()
    delegated_hosts = set(explicit_root_delegated_listing_hosts(page, allowed_hosts=allowed_hosts))
    effective_hosts = set(allowed_hosts) | delegated_hosts

    provider = authorized_ats_provider(
        page_url=page.final_url,
        html=page.html,
        allowed_hosts=effective_hosts,
        delegated_hosts=delegated_hosts,
    )
    current_provider_listing = (
        provider_listing_urls(
            provider=provider,
            page_url=page.final_url,
            html=page.html,
            allowed_hosts=effective_hosts,
        )
        if provider
        else ()
    )
    current_provider_detail = (
        provider_detail_urls(
            provider=provider,
            page_url=page.final_url,
            body=page.html,
            allowed_hosts=effective_hosts,
        )
        if provider
        else ()
    )

    carriers: list[dict[str, object]] = []
    canonical_provider_anchor_count = 0
    matching_provider_anchor_count = 0
    same_origin_unclassified = 0
    external_unpromoted = 0

    for url, anchor_text in page.links:
        target_host = url_host(url)
        recognition = recognize_ats_provider(url)
        broad_jobish = _jobish(f"{url} {anchor_text}")
        if not broad_jobish and recognition is None:
            continue

        same_origin = bool(target_host and target_host in allowed_hosts)
        currently_listing = looks_like_listing_navigation(url, anchor_text)
        target_provider = recognition.provider if recognition is not None else None
        delegated = bool(target_host and target_host in delegated_hosts)

        if recognition is not None and not same_origin:
            canonical_provider_anchor_count += 1
            if provider and target_provider == provider:
                matching_provider_anchor_count += 1
        if same_origin and broad_jobish and not currently_listing:
            same_origin_unclassified += 1
        if (not same_origin) and broad_jobish and not delegated:
            external_unpromoted += 1

        carriers.append(
            {
                "shape": safe_url_shape(url),
                "anchor_text": _label(anchor_text),
                "same_origin": same_origin,
                "broad_jobish": broad_jobish,
                "currently_listing_navigation": currently_listing,
                "delegated_by_current_rules": delegated,
                "recognized_provider": target_provider,
            }
        )

    hypotheses: list[str] = []
    if provider and matching_provider_anchor_count and not current_provider_listing and not current_provider_detail:
        hypotheses.append("explicit_canonical_provider_anchor_not_authorized")
    if same_origin_unclassified:
        hypotheses.append("same_origin_listing_vocabulary_gap")
    if external_unpromoted:
        hypotheses.append("external_listing_vocabulary_gap")
    if provider and not current_provider_listing and not current_provider_detail and not matching_provider_anchor_count:
        hypotheses.append("provider_route_adapter_gap")
    if not hypotheses:
        hypotheses.append("no_bridge_gap_observed")

    return {
        "candidate_id": item.get("candidate_id"),
        "company_key": item.get("company_key"),
        "company_name": item.get("company_name"),
        "origin": safe_url_shape(final_url),
        "status": status,
        "authorized_provider": provider,
        "current_provider_listing_count": len(current_provider_listing),
        "current_provider_detail_count": len(current_provider_detail),
        "delegated_hosts": sorted(delegated_hosts),
        "canonical_provider_anchor_count": canonical_provider_anchor_count,
        "matching_provider_anchor_count": matching_provider_anchor_count,
        "same_origin_unclassified_count": same_origin_unclassified,
        "external_unpromoted_count": external_unpromoted,
        "hypotheses": hypotheses,
        "carriers": carriers[:40],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only bridge audit for evidence-rich inventory failures.")
    parser.add_argument("--layer-audit", required=True)
    parser.add_argument("--surface-audit", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    layer_payload = json.loads(Path(args.layer_audit).read_text(encoding="utf-8"))
    surface_payload = json.loads(Path(args.surface_audit).read_text(encoding="utf-8"))
    surface_by_key = {
        str(item.get("company_key")): item
        for item in surface_payload.get("results", [])
        if item.get("company_key")
    }
    failures = []
    for item in layer_payload.get("results", []):
        if item.get("first_failure_layer") != "inventory":
            continue
        surface = surface_by_key.get(str(item.get("company_key"))) or {}
        signals = {str(signal) for signal in surface.get("signals", [])}
        if signals.intersection(BRIDGE_SIGNALS):
            failures.append(item)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-inventory-bridge-audit/0.1 (+bounded read-only)",
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        }
    )

    results: list[dict[str, object]] = []
    request_count = 0
    for item in failures:
        origin = _origin_from_layer(item)
        if not origin:
            results.append(
                {
                    "candidate_id": item.get("candidate_id"),
                    "company_key": item.get("company_key"),
                    "company_name": item.get("company_name"),
                    "hypotheses": ["origin_shape_not_replayable"],
                }
            )
            continue
        try:
            response = session.get(origin, timeout=args.timeout_seconds, allow_redirects=True)
            request_count += 1
            body = response.content
            if len(body) > MAX_BODY_BYTES:
                raise RuntimeError("response body cap exceeded")
            html = body.decode(response.encoding or "utf-8", errors="replace")
            results.append(
                classify_bridge(
                    item,
                    html=html,
                    final_url=str(response.url),
                    status=int(response.status_code),
                )
            )
        except requests.RequestException as exc:
            request_count += 1
            results.append(
                {
                    "candidate_id": item.get("candidate_id"),
                    "company_key": item.get("company_key"),
                    "company_name": item.get("company_name"),
                    "hypotheses": ["root_fetch_failed"],
                    "exception": f"{type(exc).__name__}: {exc}"[:500],
                }
            )

    hypothesis_counts = Counter(
        hypothesis
        for item in results
        for hypothesis in item.get("hypotheses", [])
    )
    output = {
        "schema": SCHEMA,
        "boundary": {
            "input_bridge_cases": len(failures),
            "http_get_requests": request_count,
            "max_gets_per_candidate": 1,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
            "database_reads": 0,
            "database_writes": 0,
            "connector_materialization": 0,
            "query_values_persisted": 0,
        },
        "summary": {
            "bridge_case_count": len(failures),
            "hypothesis_counts": dict(sorted(hypothesis_counts.items())),
        },
        "results": results,
    }
    Path(args.output).write_text(
        json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("============================================")
    print("DETERMINISTIC INVENTORY BRIDGE AUDIT")
    print("============================================")
    print(f"bridge_case_count={len(failures)}")
    print("hypothesis_counts=" + json.dumps(dict(sorted(hypothesis_counts.items())), sort_keys=True))
    print()
    for item in results:
        print(f"{str(item.get('candidate_id')):>3} | {item.get('company_key')} | {item.get('company_name')}")
        print("  hypotheses=" + ", ".join(str(v) for v in item.get("hypotheses", [])))
        print(
            "  provider=" + str(item.get("authorized_provider"))
            + " provider_anchors=" + str(item.get("matching_provider_anchor_count"))
            + " same_unclassified=" + str(item.get("same_origin_unclassified_count"))
            + " external_unpromoted=" + str(item.get("external_unpromoted_count"))
        )
        for carrier in item.get("carriers", [])[:12]:
            shape = carrier.get("shape") or {}
            print(
                "    - "
                + str(shape.get("host"))
                + str(shape.get("path"))
                + " qkeys=" + ",".join(str(v) for v in shape.get("query_keys", []))
                + " same=" + str(carrier.get("same_origin"))
                + " listing=" + str(carrier.get("currently_listing_navigation"))
                + " provider=" + str(carrier.get("recognized_provider"))
                + " label=" + repr(carrier.get("anchor_text"))
            )
    print()
    print(f"HTTP_GET_REQUESTS={request_count}")
    print("PROVIDER_REQUESTS=0")
    print("DATABASE_WRITES=0")
    print("QUERY_VALUES_PERSISTED=0")
    print(f"artifact={args.output}")
    print("INVENTORY_BRIDGE_AUDIT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
