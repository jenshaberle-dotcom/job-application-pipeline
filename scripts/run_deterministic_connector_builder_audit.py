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
from src.connectors.employer_origin_ats_navigation import (
    authorized_ats_provider,
    provider_detail_urls,
    provider_listing_urls,
)
from src.connectors.employer_origin_greenhouse_navigation import (
    explicit_greenhouse_board_token,
)
from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.ats_provider_registry import recognize_ats_provider
from src.search_intelligence.connector_feasibility_query_runtime import (
    QUERY_JOB_IDENTIFIER_KEYS,
)
from src.search_intelligence.deterministic_connector_builder import (
    ConnectorBuilderAssessment,
    complete_after_failure,
    failed,
    passed,
    skipped,
    summarize_assessments,
)
from src.search_intelligence.multi_origin_evidence import job_detail_url_shape


SCHEMA = "job_application_pipeline.deterministic_connector_builder_audit.v1"
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
DEFAULT_ORIGIN_TIMEOUT_SECONDS = 5.0
DEFAULT_ORIGIN_MAX_CANDIDATES = 12
ABSOLUTE_ACQUISITION_GET_CAP = 4
MAX_BODY_BYTES = 5_000_000


class EmbeddedNavigationParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.iframes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "iframe":
            return
        values = {str(key or "").casefold(): str(value or "") for key, value in attrs}
        src = values.get("src", "").strip()
        if src:
            self.iframes.append(urljoin(self.base_url, src))


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def load_current_candidates(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
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


def url_shape(value: str | None) -> dict[str, object] | None:
    if not value:
        return None
    parsed = urlparse(str(value))
    return {
        "scheme": parsed.scheme.casefold(),
        "host": (parsed.hostname or "").casefold(),
        "path": parsed.path or "/",
        "query_keys": sorted({key for key, _value in parse_qsl(parsed.query, keep_blank_values=True)}),
    }


def registered_domain(value: str) -> str:
    host = (urlparse(value).hostname or value).casefold().strip(".").removeprefix("www.")
    parts = [part for part in host.split(".") if part]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def same_registered_domain(left: str, right: str) -> bool:
    left_domain = registered_domain(left)
    return bool(left_domain and left_domain == registered_domain(right))


def valid_https_url(value: str | None) -> bool:
    parsed = urlparse(str(value or ""))
    return bool(parsed.scheme.casefold() == "https" and parsed.hostname and not parsed.username and not parsed.password)


def jobish_url(value: str) -> bool:
    parsed = urlparse(value)
    surface = f"{parsed.hostname or ''}{parsed.path or ''}".casefold()
    return any(
        marker in surface
        for marker in ("job", "jobs", "career", "careers", "karriere", "stellen", "recruit")
    )


def detailish_url(value: str) -> bool:
    if job_detail_url_shape(value):
        return True
    query_keys = {
        key.replace("_", "").replace("-", "").casefold()
        for key, _value in parse_qsl(urlparse(value).query, keep_blank_values=True)
    }
    normalized_identifiers = {
        key.replace("_", "").replace("-", "").casefold()
        for key in QUERY_JOB_IDENTIFIER_KEYS
    }
    return bool(query_keys.intersection(normalized_identifiers))


def embedded_job_iframes(page_url: str, html: str, allowed_hosts: set[str]) -> list[dict[str, object]]:
    parser = EmbeddedNavigationParser(page_url)
    parser.feed(html)
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in parser.iframes:
        parsed = urlparse(raw)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme.casefold() != "https" or not host or host in seen:
            continue
        recognition = recognize_ats_provider(raw)
        if host in allowed_hosts:
            continue
        if recognition is None and not jobish_url(raw):
            continue
        seen.add(host)
        result.append(
            {
                "url": url_shape(raw),
                "host": host,
                "provider_hint": recognition.provider if recognition else None,
            }
        )
    return result


def origin_args(args: argparse.Namespace) -> argparse.Namespace:
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


def resolve_origin(row: dict[str, Any], args: argparse.Namespace) -> tuple[str | None, dict[str, object]]:
    persisted = str(row.get("candidate_url") or "").strip()
    if persisted:
        if not valid_https_url(persisted):
            return None, {
                "source": "persisted_candidate_url",
                "reason": "persisted candidate_url is not a valid public HTTPS URL",
                "candidate_url": url_shape(persisted),
            }
        return persisted, {
            "source": "persisted_candidate_url",
            "candidate_url": url_shape(persisted),
        }

    try:
        payload = run_origin_discovery(origin_args(args), str(row["company_key"]))
    except BaseException as exc:
        return None, {
            "source": "provider_free_origin_discovery",
            "reason": f"{type(exc).__name__}: {exc}"[:500],
            "diagnostic_failure": True,
        }

    selected = str(payload.get("selected_url") or "").strip()
    return (
        selected if payload.get("decision") == "origin_url_candidate_selected" and valid_https_url(selected) else None,
        {
            "source": "provider_free_origin_discovery",
            "decision": payload.get("decision"),
            "selected_url": url_shape(selected),
            "confidence_score": payload.get("confidence_score"),
            "risk_level": payload.get("risk_level"),
            "candidate_count": payload.get("candidate_count"),
            "assessed_count": payload.get("assessed_count"),
            "provider_requests": 0,
        },
    )


def assess_candidate(row: dict[str, Any], args: argparse.Namespace) -> ConnectorBuilderAssessment:
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
            "candidate has a stable employer key and non-empty normalized company identity",
            company_key=company_key,
            normalized_company_name=normalized_name,
            status=str(row.get("status") or ""),
        )
    )

    origin_url, origin_evidence = resolve_origin(row, args)
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
            "authorized deterministic employer-origin URL is available",
            **origin_evidence,
        )
    )

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-connector-builder-audit/0.1 (+bounded read-only)",
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        }
    )
    calls: list[dict[str, object]] = []
    cached: dict[str, tuple[str, str, int]] = {}

    def network_fetch(url: str) -> tuple[str, str, int]:
        canonical = canonical_url(url)
        if canonical in cached:
            return cached[canonical]
        if len(calls) >= ABSOLUTE_ACQUISITION_GET_CAP:
            raise RuntimeError("absolute acquisition GET cap exceeded")
        if not valid_https_url(url):
            raise RuntimeError("connector-builder audit permits HTTPS GET only")
        response = session.get(url, timeout=args.http_timeout_seconds, allow_redirects=True)
        body = response.content
        if len(body) > MAX_BODY_BYTES:
            raise RuntimeError("response body cap exceeded")
        text = body.decode(response.encoding or "utf-8", errors="replace")
        record = {
            "requested": url_shape(url),
            "final": url_shape(str(response.url)),
            "status": int(response.status_code),
            "body_bytes": len(body),
        }
        calls.append(record)
        result = (text, str(response.url), int(response.status_code))
        cached[canonical] = result
        cached[canonical_url(str(response.url))] = result
        return result

    try:
        root_html, root_final_url, root_status = network_fetch(origin_url)
    except Exception as exc:
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="origin_reachability",
                failure_reason="selected origin could not be fetched within the bounded read-only contract",
                failure_evidence={"exception": f"{type(exc).__name__}: {exc}"[:500], "requests": calls},
            ),
        )

    initial_host = url_host(origin_url)
    final_host = url_host(root_final_url)
    if root_status >= 400:
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="origin_reachability",
                failure_reason="selected origin returned an HTTP error",
                failure_evidence={"status": root_status, "origin": url_shape(origin_url), "final": url_shape(root_final_url)},
            ),
        )
    if final_host != initial_host and not same_registered_domain(origin_url, root_final_url):
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="origin_reachability",
                failure_reason="selected origin redirects across employer-domain authority without an existing explicit delegation contract",
                failure_evidence={"origin": url_shape(origin_url), "final": url_shape(root_final_url)},
            ),
        )

    allowed_hosts = {initial_host, final_host}
    layers.append(
        passed(
            "origin_reachability",
            "selected origin is reachable and remains inside established employer-domain authority",
            status=root_status,
            origin=url_shape(origin_url),
            final=url_shape(root_final_url),
            request_count=len(calls),
        )
    )

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
                skipped("delegation", "origin itself is already a strict job detail; no portal handoff is required"),
                skipped("provider", "origin itself is already a strict job detail; provider classification is unnecessary"),
                skipped("inventory", "origin itself is already a concrete job detail; inventory enumeration is unnecessary"),
                passed("detail", "origin itself is the concrete job detail", detail=url_shape(root_final_url)),
                passed("proof", "origin detail passed the unchanged strict genuine-job proof", proof_kind=root_proof),
                passed(
                    "recipe",
                    "all evidence-required layers are satisfied; deterministic connector recipe is compile-ready",
                    materialization_performed=False,
                ),
            ]
        )
        return ConnectorBuilderAssessment(candidate_id, company_key, company_name, tuple(layers))

    preliminary_navigation = discover_navigation_candidates(
        root,
        allowed_hosts=allowed_hosts,
        known_detail_urls=(),
    )
    explicit_delegated_hosts = set(
        explicit_root_delegated_listing_hosts(root, allowed_hosts=allowed_hosts)
    )
    iframe_delegations = embedded_job_iframes(root.final_url, root.html, allowed_hosts)
    same_origin_navigation = [
        item for item in preliminary_navigation if url_host(item.url) in allowed_hosts
    ]

    if iframe_delegations and not explicit_delegated_hosts and not same_origin_navigation:
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="delegation",
                failure_reason="an explicit external job/ATS iframe is observed but the current deterministic delegation executor only follows supported anchor-based handoffs",
                failure_evidence={"iframe_delegations": iframe_delegations, "supported_anchor_delegated_hosts": []},
            ),
        )

    if explicit_delegated_hosts:
        delegation_required = not bool(same_origin_navigation)
        layers.append(
            passed(
                "delegation",
                "first-party origin exposes an explicit supported external job-portal anchor",
                required=delegation_required,
                delegated_hosts=sorted(explicit_delegated_hosts),
                same_origin_navigation_count=len(same_origin_navigation),
            )
        )
        allowed_hosts.update(explicit_delegated_hosts)
    elif iframe_delegations:
        layers.append(
            skipped(
                "delegation",
                "external iframe exists but observed same-origin navigation means the external handoff is not required for this candidate",
                iframe_delegations=iframe_delegations,
                same_origin_navigation_count=len(same_origin_navigation),
            )
        )
    else:
        layers.append(
            skipped(
                "delegation",
                "no external job-surface handoff is required by the currently observed root evidence",
                same_origin_navigation_count=len(same_origin_navigation),
            )
        )

    navigation = discover_navigation_candidates(root, allowed_hosts=allowed_hosts, known_detail_urls=())
    root_provider = authorized_ats_provider(
        page_url=root.final_url,
        html=root.html,
        allowed_hosts=allowed_hosts,
        delegated_hosts=explicit_delegated_hosts,
    )
    delegated_provider_hints = sorted(
        {
            recognition.provider
            for host in explicit_delegated_hosts
            if (recognition := recognize_ats_provider(f"https://{host}/")) is not None
        }
    )
    provider_name = root_provider or (delegated_provider_hints[0] if len(delegated_provider_hints) == 1 else None)

    provider_listing = ()
    provider_details = ()
    if root_provider:
        provider_listing = provider_listing_urls(
            provider=root_provider,
            page_url=root.final_url,
            html=root.html,
            allowed_hosts=allowed_hosts,
        )
        provider_details = provider_detail_urls(
            provider=root_provider,
            page_url=root.final_url,
            body=root.html,
            allowed_hosts=allowed_hosts,
        )

    generic_navigation_available = bool(navigation)
    if provider_name:
        provider_required = not generic_navigation_available
        layers.append(
            passed(
                "provider",
                "a deterministic ATS/provider family is recognized from authorized evidence",
                required=provider_required,
                provider=provider_name,
                root_provider=root_provider,
                delegated_provider_hints=delegated_provider_hints,
                generic_navigation_count=len(navigation),
            )
        )
    else:
        layers.append(
            skipped(
                "provider",
                "no uniquely authorized provider family is required by current evidence; generic inventory discovery is evaluated directly",
                generic_navigation_count=len(navigation),
            )
        )

    greenhouse_token = explicit_greenhouse_board_token(root.html)
    inventory_evidence = {
        "navigation_candidate_count": len(navigation),
        "navigation_kinds": sorted({item.kind for item in navigation}),
        "provider_listing_count": len(provider_listing),
        "provider_detail_count": len(provider_details),
        "greenhouse_binding_observed": bool(greenhouse_token),
    }
    preliminary_inventory = bool(navigation or provider_listing or provider_details or greenhouse_token)

    v4_error: str | None = None
    try:
        jobs, observed_root = acquire_genuine_job_pages(
            listing_url=origin_url,
            allowed_hosts=tuple(sorted(allowed_hosts)),
            known_detail_urls=(),
            fetcher=network_fetch,
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
                    "current deterministic acquisition stack exposed a concrete job path from the authorized origin",
                    **inventory_evidence,
                    discovery_source=job.discovery_source,
                    total_get_count=len(calls),
                ),
                passed(
                    "detail",
                    "current deterministic acquisition stack reached a concrete job detail",
                    detail=url_shape(job.final_url),
                    discovery_source=job.discovery_source,
                ),
                passed(
                    "proof",
                    "concrete detail passed the unchanged strict genuine-job proof",
                    proof_kind=job.proof_kind,
                ),
                passed(
                    "recipe",
                    "all evidence-required layers are satisfied; deterministic connector recipe is compile-ready",
                    materialization_performed=False,
                    observed_root=url_shape(observed_root),
                ),
            ]
        )
        return ConnectorBuilderAssessment(candidate_id, company_key, company_name, tuple(layers))

    if not preliminary_inventory:
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="inventory",
                failure_reason="authorized root exposed no currently supported deterministic inventory/detail path",
                failure_evidence={**inventory_evidence, "v4_error": v4_error, "requests": calls},
            ),
        )

    layers.append(
        passed(
            "inventory",
            "authorized root exposes deterministic inventory/navigation evidence",
            **inventory_evidence,
            v4_error=v4_error,
            total_get_count=len(calls),
        )
    )

    followup_shapes = [
        item.get("requested")
        for item in calls[1:]
        if isinstance(item.get("requested"), dict)
    ]
    reached_detail = any(
        detailish_url(
            "https://"
            + str(shape.get("host") or "")
            + str(shape.get("path") or "/")
            + (
                "?" + "&".join(f"{key}=x" for key in shape.get("query_keys") or [])
                if shape.get("query_keys")
                else ""
            )
        )
        for shape in followup_shapes
    )

    if not reached_detail:
        return ConnectorBuilderAssessment(
            candidate_id,
            company_key,
            company_name,
            complete_after_failure(
                layers,
                failed_layer="detail",
                failure_reason="inventory evidence exists but the current deterministic path did not resolve a concrete job detail within the bounded request contract",
                failure_evidence={"v4_error": v4_error, "requests": calls},
            ),
        )

    layers.append(
        passed(
            "detail",
            "a concrete detail-shaped follow-up was reached",
            followup_requests=followup_shapes,
        )
    )
    return ConnectorBuilderAssessment(
        candidate_id,
        company_key,
        company_name,
        complete_after_failure(
            layers,
            failed_layer="proof",
            failure_reason="a concrete detail-shaped surface was reached but unchanged strict genuine-job proof did not pass",
            failure_evidence={"v4_error": v4_error, "requests": calls},
        ),
    )


def print_assessment(assessment: ConnectorBuilderAssessment, index: int, total: int) -> None:
    failure = assessment.first_failure
    print(
        f"[{index}/{total}] {assessment.company_key}: "
        f"recipe_ready={assessment.recipe_ready} "
        f"first_failure={failure.layer if failure else '-'}"
    )
    for item in assessment.layers:
        required = "?" if item.required is None else str(item.required).lower()
        print(f"  {item.layer:20s} {item.state.value:11s} required={required} | {item.reason}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the evidence-driven deterministic connector-builder layer model across all current Employer-Origin candidates."
    )
    parser.add_argument("--output", default="/tmp/deterministic_connector_builder_audit.json")
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--origin-max-candidates", type=int, default=DEFAULT_ORIGIN_MAX_CANDIDATES)
    parser.add_argument("--origin-timeout-seconds", type=float, default=DEFAULT_ORIGIN_TIMEOUT_SECONDS)
    parser.add_argument("--http-timeout-seconds", type=float, default=DEFAULT_HTTP_TIMEOUT_SECONDS)
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    args = parser.parse_args()

    with connect() as conn:
        candidates = load_current_candidates(conn)

    assessments: list[ConnectorBuilderAssessment] = []
    for index, row in enumerate(candidates, start=1):
        assessment = assess_candidate(row, args)
        assessments.append(assessment)
        print_assessment(assessment, index, len(candidates))
        if index < len(candidates) and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    summary = summarize_assessments(assessments)
    output = {
        "schema": SCHEMA,
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
        "measurement_note": (
            "This is a connector-builder composition diagnostic. It does not replace the canonical accumulated 36/65 strict coverage counter until all historical Runtime deterministic capability classes are integrated into this builder."
        ),
        "summary": summary,
        "results": [assessment.to_json() for assessment in assessments],
    }

    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    print()
    print("============================================")
    print("DETERMINISTIC CONNECTOR BUILDER AUDIT")
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
    print("CONNECTOR_BUILDER_AUDIT=COMPLETE")


if __name__ == "__main__":
    main()
