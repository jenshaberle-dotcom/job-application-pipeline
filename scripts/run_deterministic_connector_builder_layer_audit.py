from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlparse

import psycopg
from psycopg.rows import dict_row
import requests

from scripts.run_origin_source_discovery_agent import run_for_company as run_origin_discovery
from src.config import get_database_config
from src.connectors.employer_origin_acquisition import (
    canonical_url,
    explicit_root_delegated_listing_hosts,
    genuine_job_detail_proof,
    parse_page,
    url_host,
)
from src.connectors.employer_origin_acquisition_v4 import (
    acquire_genuine_job_pages,
    discover_navigation_candidates,
)
from src.connectors.employer_origin_ats_navigation import authorized_ats_provider
from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.ats_provider_registry import recognize_ats_provider
from src.search_intelligence.connector_feasibility_query_runtime import QUERY_JOB_IDENTIFIER_KEYS
from src.search_intelligence.deterministic_connector_builder import (
    ConnectorBuilderAssessment,
    complete_after_failure,
    passed,
    skipped,
    summarize_assessments,
)
from src.search_intelligence.multi_origin_evidence import job_detail_url_shape


SCHEMA = "job_application_pipeline.deterministic_connector_builder_layer_audit.v1"
DEFAULT_ORIGIN_MAX_CANDIDATES = 12
DEFAULT_ORIGIN_TIMEOUT_SECONDS = 5.0
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
ABSOLUTE_ACQUISITION_GET_CAP = 4
MAX_BODY_BYTES = 5_000_000


class _IframeParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "iframe":
            return
        amap = {str(k or "").casefold(): str(v or "") for k, v in attrs}
        src = amap.get("src", "").strip()
        if src:
            self.urls.append(urljoin(self.base_url, src))


def _connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _load_candidates(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (company_key)
                id,
                company_key,
                company_name,
                candidate_url,
                source_name_candidate,
                source_family_candidate,
                source_type_candidate,
                status,
                risk_level,
                updated_at
            FROM employer_origin_source_candidates
            ORDER BY company_key, updated_at DESC NULLS LAST, id DESC
            """
        )
        return [dict(row) for row in cur.fetchall()]


def _url_shape(value: str | None) -> dict[str, object] | None:
    if not value:
        return None
    parsed = urlparse(str(value))
    return {
        "scheme": parsed.scheme.casefold(),
        "host": (parsed.hostname or "").casefold(),
        "path": parsed.path or "/",
        "query_keys": sorted({key for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}),
    }


def _valid_https(value: str | None) -> bool:
    parsed = urlparse(str(value or ""))
    return bool(
        parsed.scheme.casefold() == "https"
        and parsed.hostname
        and not parsed.username
        and not parsed.password
    )


def _registered_domain(value: str) -> str:
    host = (urlparse(value).hostname or value).casefold().strip(".").removeprefix("www.")
    parts = [part for part in host.split(".") if part]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _same_registered_domain(left: str, right: str) -> bool:
    domain = _registered_domain(left)
    return bool(domain and domain == _registered_domain(right))


def _jobish_url(value: str) -> bool:
    parsed = urlparse(value)
    surface = f"{parsed.hostname or ''}{parsed.path or ''}".casefold()
    return any(
        marker in surface
        for marker in ("job", "jobs", "career", "careers", "karriere", "stellen", "recruit")
    )


def _detailish_url(value: str) -> bool:
    if job_detail_url_shape(value):
        return True
    keys = {
        key.replace("_", "").replace("-", "").casefold()
        for key, _ in parse_qsl(urlparse(value).query, keep_blank_values=True)
    }
    identifiers = {
        key.replace("_", "").replace("-", "").casefold()
        for key in QUERY_JOB_IDENTIFIER_KEYS
    }
    return bool(keys.intersection(identifiers))


def _iframe_delegations(page_url: str, html: str, allowed_hosts: set[str]) -> list[dict[str, object]]:
    parser = _IframeParser(page_url)
    parser.feed(html)
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in parser.urls:
        parsed = urlparse(raw)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme.casefold() != "https" or not host or host in allowed_hosts or host in seen:
            continue
        recognition = recognize_ats_provider(raw)
        if recognition is None and not _jobish_url(raw):
            continue
        seen.add(host)
        result.append(
            {
                "host": host,
                "url": _url_shape(raw),
                "provider_hint": recognition.provider if recognition else None,
            }
        )
    return result


def _origin_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        target_location=args.target_location,
        timeout_seconds=args.origin_timeout_seconds,
        max_candidates=args.origin_max_candidates,
        market_evidence_limit=10,
        search_provider=["none"],
        search_query_limit=2,
        search_max_results=5,
        search_timeout_seconds=8.0,
        search_depth="basic",
        search_results_json=None,
        no_probe=False,
    )


def _resolve_origin(row: dict[str, Any], args: argparse.Namespace) -> tuple[str | None, dict[str, object]]:
    persisted = str(row.get("candidate_url") or "").strip()
    if persisted:
        return (
            persisted if _valid_https(persisted) else None,
            {
                "source": "persisted_candidate_url",
                "candidate_url": _url_shape(persisted),
                "valid_https": _valid_https(persisted),
            },
        )

    try:
        payload = run_origin_discovery(_origin_args(args), str(row["company_key"]))
    except BaseException as exc:
        return None, {
            "source": "provider_free_origin_discovery",
            "diagnostic_failure": True,
            "exception": f"{type(exc).__name__}: {exc}"[:500],
        }

    selected = str(payload.get("selected_url") or "").strip()
    selected_ok = payload.get("decision") == "origin_url_candidate_selected" and _valid_https(selected)
    return (
        selected if selected_ok else None,
        {
            "source": "provider_free_origin_discovery",
            "decision": payload.get("decision"),
            "selected_url": _url_shape(selected),
            "confidence_score": payload.get("confidence_score"),
            "risk_level": payload.get("risk_level"),
            "candidate_count": payload.get("candidate_count"),
            "assessed_count": payload.get("assessed_count"),
            "provider_requests": 0,
        },
    )


def _assessment(
    row: dict[str, Any],
    args: argparse.Namespace,
) -> ConnectorBuilderAssessment:
    candidate_id = int(row["id"])
    company_key = str(row.get("company_key") or "").strip()
    company_name = str(row.get("company_name") or "").strip()
    layers = []

    normalized_name = normalize_company_key(company_name)
    if not company_key or not company_name or not normalized_name:
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                (),
                failed_layer="identity",
                failure_reason="candidate lacks a stable non-empty employer identity",
                failure_evidence={"normalized_company_name": normalized_name},
            ),
        )

    layers.append(
        passed(
            "identity",
            "stable candidate key and normalized employer identity are present",
            company_key=company_key,
            normalized_company_name=normalized_name,
            candidate_status=str(row.get("status") or ""),
        )
    )

    origin_url, origin_evidence = _resolve_origin(row, args)
    if not origin_url:
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="origin",
                failure_reason="no authorized deterministic employer-origin candidate was selected",
                failure_evidence=origin_evidence,
            ),
        )

    layers.append(
        passed(
            "origin",
            "an authorized deterministic employer-origin URL is available",
            **origin_evidence,
        )
    )

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-connector-builder-layer-audit/0.1 (+bounded read-only)",
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        }
    )
    calls: list[dict[str, object]] = []
    cache: dict[str, tuple[str, str, int]] = {}

    def fetcher(url: str) -> tuple[str, str, int]:
        clean = canonical_url(url)
        if clean in cache:
            return cache[clean]
        if len(calls) >= ABSOLUTE_ACQUISITION_GET_CAP:
            raise RuntimeError("absolute acquisition GET cap exceeded")
        if not _valid_https(url):
            raise RuntimeError("layer audit permits HTTPS GET only")
        response = session.get(url, timeout=args.http_timeout_seconds, allow_redirects=True)
        body = response.content
        if len(body) > MAX_BODY_BYTES:
            raise RuntimeError("response body cap exceeded")
        text = body.decode(response.encoding or "utf-8", errors="replace")
        result = (text, str(response.url), int(response.status_code))
        calls.append(
            {
                "requested": _url_shape(url),
                "final": _url_shape(str(response.url)),
                "status": int(response.status_code),
                "body_bytes": len(body),
            }
        )
        cache[clean] = result
        cache[canonical_url(str(response.url))] = result
        return result

    try:
        root_html, root_final_url, root_status = fetcher(origin_url)
    except Exception as exc:
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="origin_reachability",
                failure_reason="selected origin could not be fetched within the bounded GET contract",
                failure_evidence={"exception": f"{type(exc).__name__}: {exc}"[:500], "requests": calls},
            ),
        )

    if root_status >= 400:
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="origin_reachability",
                failure_reason="selected origin returned an HTTP error",
                failure_evidence={"status": root_status, "origin": _url_shape(origin_url), "final": _url_shape(root_final_url)},
            ),
        )

    initial_host = url_host(origin_url)
    final_host = url_host(root_final_url)
    cross_host_redirect = bool(
        final_host
        and final_host != initial_host
        and not _same_registered_domain(origin_url, root_final_url)
    )
    layers.append(
        passed(
            "origin_reachability",
            "selected origin returned a reachable public surface",
            status=root_status,
            origin=_url_shape(origin_url),
            final=_url_shape(root_final_url),
            cross_host_redirect=cross_host_redirect,
            request_count=len(calls),
        )
    )

    if cross_host_redirect:
        recognition = recognize_ats_provider(root_final_url)
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="delegation",
                failure_reason="first-party origin performs an explicit cross-host redirect, but the current acquisition authority contract does not yet promote that redirect carrier",
                failure_evidence={
                    "redirect_target": _url_shape(root_final_url),
                    "provider_hint": recognition.provider if recognition else None,
                    "carrier": "http_redirect",
                },
            ),
        )

    allowed_hosts = {host for host in (initial_host, final_host) if host}
    root = parse_page(
        requested_url=origin_url,
        html=root_html,
        final_url=root_final_url,
        status_code=root_status,
    )

    root_proof = genuine_job_detail_proof(root, allowed_hosts=allowed_hosts, known_detail=False)
    if root_proof:
        layers.extend(
            [
                skipped("delegation", "origin itself is already a strict job detail"),
                skipped("provider", "provider classification is unnecessary because origin is already a strict detail"),
                skipped("inventory", "inventory enumeration is unnecessary because origin is already a strict detail"),
                passed("detail", "origin itself is the concrete job detail", detail=_url_shape(root.final_url)),
                passed("proof", "origin detail passes unchanged strict genuine-job proof", proof_kind=root_proof),
                passed(
                    "recipe",
                    "all evidence-required layers are satisfied; connector recipe is compile-ready",
                    materialization_performed=False,
                ),
            ]
        )
        return ConnectorBuilderAssessment(candidate_id, company_key, company_name, tuple(layers))

    initial_navigation = discover_navigation_candidates(root, allowed_hosts=allowed_hosts, known_detail_urls=())
    same_origin_navigation = [item for item in initial_navigation if url_host(item.url) in allowed_hosts]
    delegated_hosts = set(explicit_root_delegated_listing_hosts(root, allowed_hosts=allowed_hosts))
    iframes = _iframe_delegations(root.final_url, root.html, allowed_hosts)

    if iframes and not delegated_hosts and not same_origin_navigation:
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="delegation",
                failure_reason="external job/ATS iframe is explicit and required, but iframe delegation is not yet an executable deterministic carrier",
                failure_evidence={
                    "carrier": "iframe",
                    "iframe_delegations": iframes,
                    "same_origin_navigation_count": 0,
                },
            ),
        )

    if delegated_hosts:
        layers.append(
            passed(
                "delegation",
                "first-party origin exposes a supported explicit external job-portal anchor",
                required=not bool(same_origin_navigation),
                delegated_hosts=sorted(delegated_hosts),
                same_origin_navigation_count=len(same_origin_navigation),
            )
        )
        allowed_hosts.update(delegated_hosts)
    elif iframes:
        layers.append(
            skipped(
                "delegation",
                "external iframe exists but a same-origin deterministic path is already observed, so iframe delegation is not required",
                iframe_delegations=iframes,
                same_origin_navigation_count=len(same_origin_navigation),
            )
        )
    else:
        layers.append(
            skipped(
                "delegation",
                "no external handoff is required by the observed root evidence",
                same_origin_navigation_count=len(same_origin_navigation),
            )
        )

    navigation = discover_navigation_candidates(root, allowed_hosts=allowed_hosts, known_detail_urls=())
    direct_details = [item for item in navigation if item.kind == "detail"]
    root_provider = authorized_ats_provider(
        page_url=root.final_url,
        html=root.html,
        allowed_hosts=allowed_hosts,
        delegated_hosts=delegated_hosts,
    )
    delegated_provider_hints = sorted(
        {
            recognition.provider
            for host in delegated_hosts
            if (recognition := recognize_ats_provider(f"https://{host}/")) is not None
        }
    )
    provider = root_provider or (delegated_provider_hints[0] if len(delegated_provider_hints) == 1 else None)

    if provider:
        layers.append(
            passed(
                "provider",
                "a deterministic ATS/provider family is recognized from authorized evidence",
                required=not bool(direct_details),
                provider=provider,
                root_provider=root_provider,
                delegated_provider_hints=delegated_provider_hints,
                direct_detail_count=len(direct_details),
            )
        )
    else:
        layers.append(
            skipped(
                "provider",
                "no uniquely authorized provider family is required by observed evidence; generic inventory discovery remains applicable",
                navigation_candidate_count=len(navigation),
            )
        )

    inventory_evidence = {
        "navigation_candidate_count": len(navigation),
        "navigation_kinds": sorted({item.kind for item in navigation}),
        "direct_detail_count": len(direct_details),
        "provider": provider,
    }
    inventory_observed = bool(navigation)

    v4_error: str | None = None
    try:
        jobs, observed_root = acquire_genuine_job_pages(
            listing_url=origin_url,
            allowed_hosts=tuple(sorted(allowed_hosts)),
            known_detail_urls=(),
            fetcher=fetcher,
            max_followup_requests=2,
            max_results=1,
        )
    except Exception as exc:
        jobs = []
        observed_root = root.final_url
        v4_error = f"{type(exc).__name__}: {exc}"[:500]

    if jobs:
        job = jobs[0]
        layers.extend(
            [
                passed(
                    "inventory",
                    "current deterministic stack exposed a concrete job path from the authorized origin",
                    **inventory_evidence,
                    discovery_source=job.discovery_source,
                    total_get_count=len(calls),
                ),
                passed(
                    "detail",
                    "current deterministic stack reached a concrete job detail",
                    detail=_url_shape(job.final_url),
                    discovery_source=job.discovery_source,
                ),
                passed("proof", "detail passes unchanged strict genuine-job proof", proof_kind=job.proof_kind),
                passed(
                    "recipe",
                    "all evidence-required layers are satisfied; connector recipe is compile-ready",
                    materialization_performed=False,
                    observed_root=_url_shape(observed_root),
                ),
            ]
        )
        return ConnectorBuilderAssessment(candidate_id, company_key, company_name, tuple(layers))

    if not inventory_observed:
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="inventory",
                failure_reason="authorized surface exposes no currently supported deterministic inventory/detail path",
                failure_evidence={**inventory_evidence, "v4_error": v4_error, "requests": calls},
            ),
        )

    layers.append(
        passed(
            "inventory",
            "authorized surface exposes deterministic inventory/navigation evidence",
            **inventory_evidence,
            v4_error=v4_error,
            total_get_count=len(calls),
        )
    )

    followup_requested_urls: list[str] = []
    for item in calls[1:]:
        shape = item.get("requested")
        if not isinstance(shape, dict):
            continue
        host = str(shape.get("host") or "")
        path = str(shape.get("path") or "/")
        query_keys = list(shape.get("query_keys") or [])
        suffix = ""
        if query_keys:
            suffix = "?" + "&".join(f"{key}=x" for key in query_keys)
        followup_requested_urls.append(f"https://{host}{path}{suffix}")

    reached_detail = any(_detailish_url(url) for url in followup_requested_urls)
    if not reached_detail:
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="detail",
                failure_reason="inventory exists but no concrete detail was resolved within the current bounded deterministic path",
                failure_evidence={"v4_error": v4_error, "requests": calls},
            ),
        )

    layers.append(
        passed(
            "detail",
            "a concrete detail-shaped follow-up was reached",
            followup_urls=[_url_shape(url) for url in followup_requested_urls],
        )
    )
    return ConnectorBuilderAssessment(
        candidate_id,
        company_key,
        company_name,
        complete_after_failure(
            layers,
            failed_layer="proof",
            failure_reason="detail-shaped surface was reached but unchanged strict genuine-job proof did not pass",
            failure_evidence={"v4_error": v4_error, "requests": calls},
        ),
    )


def _print_assessment(item: ConnectorBuilderAssessment, index: int, total: int) -> None:
    failure = item.first_failure
    print(
        f"[{index}/{total}] {item.company_key}: recipe_ready={item.recipe_ready} "
        f"first_failure={failure.layer if failure else '-'}"
    )
    for layer in item.layers:
        required = "?" if layer.required is None else str(layer.required).lower()
        print(f"  {layer.layer:20s} {layer.state.value:11s} required={required} | {layer.reason}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the evidence-driven connector-builder layer audit across every current Employer-Origin candidate."
    )
    parser.add_argument("--output", default="/tmp/deterministic_connector_builder_layer_audit.json")
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--origin-max-candidates", type=int, default=DEFAULT_ORIGIN_MAX_CANDIDATES)
    parser.add_argument("--origin-timeout-seconds", type=float, default=DEFAULT_ORIGIN_TIMEOUT_SECONDS)
    parser.add_argument("--http-timeout-seconds", type=float, default=DEFAULT_HTTP_TIMEOUT_SECONDS)
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    args = parser.parse_args()

    with _connect() as conn:
        candidates = _load_candidates(conn)

    assessments: list[ConnectorBuilderAssessment] = []
    for index, row in enumerate(candidates, start=1):
        item = _assessment(row, args)
        assessments.append(item)
        _print_assessment(item, index, len(candidates))
        if index < len(candidates) and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    summary = summarize_assessments(assessments)
    payload = {
        "schema": SCHEMA,
        "measurement_note": (
            "Layer-composition diagnostic only. It does not supersede the canonical accumulated 36/65 strict coverage metric until historical Runtime capability classes are integrated into the connector builder."
        ),
        "boundary": {
            "database_reads": True,
            "database_writes": False,
            "candidate_url_writes": False,
            "connector_materialization": False,
            "connector_registration": False,
            "source_activation": False,
            "bronze_write": False,
            "silver_write": False,
            "product_write": False,
            "application_action": False,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
            "network_methods": ["GET"],
            "absolute_acquisition_get_cap_per_candidate": ABSOLUTE_ACQUISITION_GET_CAP,
            "origin_generated_candidate_cap": args.origin_max_candidates,
        },
        "summary": summary,
        "results": [item.to_json() for item in assessments],
    }

    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    print()
    print("============================================")
    print("DETERMINISTIC CONNECTOR BUILDER LAYER AUDIT")
    print("============================================")
    print(f"candidate_count={summary['candidate_count']}")
    print(f"diagnostic_recipe_ready={summary['recipe_ready_count']}/{summary['candidate_count']}")
    print("first_failure_counts=" + json.dumps(summary["first_failure_counts"], sort_keys=True))
    print("layer_state_counts=" + json.dumps(summary["layer_state_counts"], sort_keys=True))
    print("provider_requests=0")
    print("llm_requests=0")
    print("tavily_requests=0")
    print("database_writes=0")
    print("connector_materialization=0")
    print(f"artifact={out}")
    print("CONNECTOR_BUILDER_LAYER_AUDIT=COMPLETE")


if __name__ == "__main__":
    main()
