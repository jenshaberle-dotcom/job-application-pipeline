from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qsl, urlparse, urlunparse

import requests

from scripts import run_deterministic_connector_builder_layer_audit as base_audit
from scripts import run_deterministic_connector_builder_layer_audit_v4 as v4_audit
from scripts import run_deterministic_connector_builder_layer_audit_v5 as v5_audit
from scripts.run_deterministic_connector_builder_layer_audit_v3 import (
    discover_navigation_candidates_with_provider_inventory,
)
from scripts.run_origin_source_discovery_agent_v4 import run_for_company as run_origin_discovery_v4
from src.connectors.employer_origin_provider_public_feed import (
    SUPPORTED_PUBLIC_FEED_PROVIDERS,
    acquire_from_authorized_provider_host,
)
from src.search_intelligence.ats_provider_registry import recognize_ats_provider
from src.search_intelligence.deterministic_connector_builder import (
    ConnectorBuilderAssessment,
    passed,
    rewrite_residual_suffix,
    summarize_assessments,
)


SCHEMA = "job_application_pipeline.deterministic_connector_builder_layer_audit.v6"
PUBLIC_FEED_OVERLAY_REQUEST_CAP = 3
MAX_BODY_BYTES = 5_000_000


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


def _url_from_shape(shape: object) -> str | None:
    if not isinstance(shape, dict):
        return None
    scheme = str(shape.get("scheme") or "").casefold()
    host = str(shape.get("host") or "").casefold().strip(".")
    path = str(shape.get("path") or "/")
    if scheme != "https" or not host:
        return None
    return urlunparse((scheme, host, path, "", "", ""))


def _provider_target(
    baseline: ConnectorBuilderAssessment,
) -> tuple[str, str] | None:
    """Reuse only provider/host authority already present in the V5 assessment."""

    provider_layer = baseline.layers[4]
    provider = str(provider_layer.evidence.get("provider") or "")
    if provider not in SUPPORTED_PUBLIC_FEED_PROVIDERS:
        return None

    root_provider = str(provider_layer.evidence.get("root_provider") or "")
    if root_provider == provider:
        final_url = _url_from_shape(baseline.layers[2].evidence.get("final"))
        if final_url:
            return provider, final_url

    delegation = baseline.layers[3].evidence.get("delegated_hosts")
    if not isinstance(delegation, (list, tuple)):
        return None
    matches: list[str] = []
    for raw_host in delegation:
        host = str(raw_host or "").casefold().strip(".")
        if not host:
            continue
        recognition = recognize_ats_provider(f"https://{host}/")
        if recognition is not None and recognition.provider == provider:
            matches.append(host)
    unique = tuple(dict.fromkeys(matches))
    if len(unique) != 1:
        return None
    return provider, f"https://{unique[0]}/"


def _promote_via_public_feed(
    baseline: ConnectorBuilderAssessment,
    *,
    provider: str,
    provider_page_url: str,
    feed_url: str,
    detail_url: str,
    proof_kind: str,
    discovery_source: str,
    detail_candidate_count: int,
    requests: list[dict[str, object]],
) -> ConnectorBuilderAssessment:
    failure = baseline.first_failure
    if failure is None or failure.layer not in {"inventory", "detail"}:
        raise ValueError("public-feed promotion requires inventory/detail residual")

    return rewrite_residual_suffix(
        baseline,
        expected_first_failure=failure.layer,
        rewrite_from_layer="provider",
        replacement_suffix=(
            passed(
                "provider",
                "already-authorized provider host has a validated fixed public-feed capability",
                provider=provider,
                provider_page=_url_shape(provider_page_url),
                overlay="external_provider_public_feed_v1",
            ),
            passed(
                "inventory",
                "provider public feed validated and emitted concrete same-authority job identities",
                provider=provider,
                feed=_url_shape(feed_url),
                detail_candidate_count=detail_candidate_count,
                overlay_requests=requests,
            ),
            passed(
                "detail",
                "provider public feed yielded a concrete detail that was fetched on existing authority",
                public_detail=_url_shape(detail_url),
                discovery_source=discovery_source,
            ),
            passed(
                "proof",
                "feed-carried detail passes unchanged strict genuine-job proof",
                proof_kind=proof_kind,
            ),
            passed(
                "recipe",
                "all evidence-required layers are satisfied; connector recipe is compile-ready",
                materialization_performed=False,
                public_feed_overlay=True,
                provider=provider,
            ),
        ),
    )


def _public_feed_overlay(
    row: dict[str, Any],
    args: argparse.Namespace,
    baseline: ConnectorBuilderAssessment,
) -> tuple[ConnectorBuilderAssessment, dict[str, object] | None]:
    del row  # baseline already carries the admitted identity/origin/provider evidence.

    failure = baseline.first_failure
    if failure is None or failure.layer not in {"inventory", "detail"}:
        return baseline, None

    target = _provider_target(baseline)
    if target is None:
        return baseline, None
    provider, provider_page_url = target
    provider_host = (urlparse(provider_page_url).hostname or "").casefold()
    if not provider_host:
        return baseline, {
            "company_key": baseline.company_key,
            "decision": "not_attempted",
            "reason": "authorized provider target lacks host",
            "provider": provider,
            "requests": [],
        }

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-builder-v6-public-feed/0.1 (+bounded read-only)",
            "Accept": "application/json,application/rss+xml,application/xml,text/xml,text/html,*/*;q=0.8",
        }
    )
    calls: list[dict[str, object]] = []

    def fetcher(url: str) -> tuple[str, str, int]:
        if len(calls) >= PUBLIC_FEED_OVERLAY_REQUEST_CAP:
            raise RuntimeError("absolute provider public-feed overlay request cap exceeded")
        parsed = urlparse(url)
        if (
            parsed.scheme.casefold() != "https"
            or not parsed.hostname
            or parsed.hostname.casefold() != provider_host
            or parsed.username
            or parsed.password
        ):
            raise RuntimeError("public-feed overlay permits exact-authorized-host HTTPS GET only")

        response = session.get(
            url,
            timeout=args.http_timeout_seconds,
            allow_redirects=True,
        )
        body = response.content
        if len(body) > MAX_BODY_BYTES:
            raise RuntimeError("public-feed overlay response body cap exceeded")
        text = body.decode(response.encoding or "utf-8", errors="replace")
        calls.append(
            {
                "method": "GET",
                "requested": _url_shape(url),
                "final": _url_shape(str(response.url)),
                "status": int(response.status_code),
                "body_bytes": len(body),
            }
        )
        return text, str(response.url), int(response.status_code)

    try:
        result = acquire_from_authorized_provider_host(
            provider=provider,
            provider_page_url=provider_page_url,
            allowed_hosts=(provider_host,),
            fetcher=fetcher,
            max_detail_attempts=2,
        )
    except Exception as exc:
        return baseline, {
            "company_key": baseline.company_key,
            "decision": "not_proven",
            "reason": f"{type(exc).__name__}: {exc}"[:500],
            "provider": provider,
            "provider_page": _url_shape(provider_page_url),
            "requests": calls,
        }

    if result is None:
        return baseline, {
            "company_key": baseline.company_key,
            "decision": "not_admitted",
            "reason": "provider/host pair has no first-tranche fixed public-feed contract",
            "provider": provider,
            "provider_page": _url_shape(provider_page_url),
            "requests": calls,
        }

    if result.acquired_job is None:
        return baseline, {
            "company_key": baseline.company_key,
            "decision": "not_proven",
            "reason": "public feed did not yield a concrete detail passing unchanged proof",
            "provider": provider,
            "provider_page": _url_shape(provider_page_url),
            "feed": _url_shape(result.feed_url),
            "detail_candidate_count": len(result.detail_candidates),
            "requests": calls,
        }

    job = result.acquired_job
    promoted = _promote_via_public_feed(
        baseline,
        provider=provider,
        provider_page_url=provider_page_url,
        feed_url=result.feed_url,
        detail_url=job.final_url,
        proof_kind=job.proof_kind,
        discovery_source=job.discovery_source,
        detail_candidate_count=len(result.detail_candidates),
        requests=calls,
    )
    return promoted, {
        "company_key": baseline.company_key,
        "decision": "promoted",
        "from_first_failure": failure.layer,
        "to_recipe_ready": True,
        "provider": provider,
        "provider_page": _url_shape(provider_page_url),
        "feed": _url_shape(result.feed_url),
        "detail_candidate_count": len(result.detail_candidates),
        "public_detail": _url_shape(job.final_url),
        "proof_kind": job.proof_kind,
        "discovery_source": job.discovery_source,
        "requests": calls,
    }


def _print_assessment(item: ConnectorBuilderAssessment, index: int, total: int) -> None:
    failure = item.first_failure
    print(
        f"[{index}/{total}] {item.company_key}: recipe_ready={item.recipe_ready} "
        f"first_failure={failure.layer if failure else '-'}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Replay the same all-candidate V5 cohort and apply one monotonic, evidence-bounded "
            "public ATS feed residual overlay to Inventory/Detail first-failures."
        )
    )
    parser.add_argument("--output", default="/tmp/deterministic_connector_builder_layer_audit_v6.json")
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument(
        "--origin-max-candidates",
        type=int,
        default=base_audit.DEFAULT_ORIGIN_MAX_CANDIDATES,
    )
    parser.add_argument(
        "--origin-timeout-seconds",
        type=float,
        default=base_audit.DEFAULT_ORIGIN_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--http-timeout-seconds",
        type=float,
        default=base_audit.DEFAULT_HTTP_TIMEOUT_SECONDS,
    )
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    args = parser.parse_args()

    base_audit.run_origin_discovery = run_origin_discovery_v4
    base_audit.discover_navigation_candidates = (
        discover_navigation_candidates_with_provider_inventory
    )

    with base_audit._connect() as conn:
        candidates = base_audit._load_candidates(conn)

    v5_assessments: list[ConnectorBuilderAssessment] = []
    v6_assessments: list[ConnectorBuilderAssessment] = []
    public_feed_results: list[dict[str, object]] = []

    for index, row in enumerate(candidates, start=1):
        v3 = base_audit._assessment(row, args)
        v4, _workday = v4_audit._workday_overlay(row, args, v3)
        v5, _portal = v5_audit._portal_overlay(row, args, v4)
        v5_assessments.append(v5)

        v6, public_feed = _public_feed_overlay(row, args, v5)
        v6_assessments.append(v6)
        if public_feed is not None:
            public_feed_results.append(public_feed)

        _print_assessment(v6, index, len(candidates))
        if index < len(candidates) and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    v5_summary = summarize_assessments(v5_assessments)
    v6_summary = summarize_assessments(v6_assessments)
    promoted = [item for item in public_feed_results if item.get("decision") == "promoted"]

    payload = {
        "schema": SCHEMA,
        "measurement_note": (
            "V6 is a read-only diagnostic replay of the same candidate cohort. External "
            "provider knowledge defines only fixed same-host public-feed capability shapes; "
            "all employer/provider authority comes from the existing V5 assessment and final "
            "acceptance uses unchanged genuine-job proof. Recipe-ready remains diagnostic and "
            "does not promote canonical product coverage without materialized strict E2E proof."
        ),
        "overlay_order": [
            "workday_cxs_detail_v1",
            "evidence_bounded_portal_v1",
            "external_provider_public_feed_v1",
        ],
        "public_feed_capabilities": sorted(SUPPORTED_PUBLIC_FEED_PROVIDERS),
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
            "public_feed_overlay_network_methods": ["GET"],
            "public_feed_overlay_request_cap_per_eligible_residual": PUBLIC_FEED_OVERLAY_REQUEST_CAP,
            "public_feed_overlay_allowed_first_failures": ["inventory", "detail"],
            "external_tenant_or_slug_guessing": False,
            "external_shard_or_board_bruteforce": False,
            "cross_host_feed_authority": False,
        },
        "comparison": {
            "v5_summary": v5_summary,
            "v6_summary": v6_summary,
            "public_feed_attempted_count": len(public_feed_results),
            "public_feed_promoted_count": len(promoted),
            "public_feed_promoted_company_keys": [
                str(item["company_key"]) for item in promoted
            ],
        },
        "public_feed_overlay_results": public_feed_results,
        "results": [item.to_json() for item in v6_assessments],
    }

    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("============================================")
    print("DETERMINISTIC CONNECTOR BUILDER V6")
    print("============================================")
    print("V5_READY=" + str(v5_summary["recipe_ready_count"]))
    print("V6_READY=" + str(v6_summary["recipe_ready_count"]))
    print("PUBLIC_FEED_ATTEMPTED=" + str(len(public_feed_results)))
    print("PUBLIC_FEED_PROMOTED=" + str(len(promoted)))
    print(
        "PUBLIC_FEED_PROMOTED_KEYS="
        + json.dumps([str(item["company_key"]) for item in promoted], sort_keys=True)
    )
    print("DATABASE_WRITES=0")
    print("PROVIDER_REQUESTS=0")
    print("LLM_REQUESTS=0")
    print("TAVILY_REQUESTS=0")
    print(f"artifact={out}")
    print("DETERMINISTIC_CONNECTOR_BUILDER_V6=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
