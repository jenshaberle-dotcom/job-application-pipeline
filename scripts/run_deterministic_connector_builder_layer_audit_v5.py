from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qsl, urlparse

import requests

from scripts import run_deterministic_connector_builder_layer_audit as base_audit
from scripts import run_deterministic_connector_builder_layer_audit_v4 as v4_audit
from scripts.run_deterministic_connector_builder_layer_audit_v3 import (
    discover_navigation_candidates_with_provider_inventory,
)
from scripts.run_origin_source_discovery_agent_v4 import run_for_company as run_origin_discovery_v4
from src.connectors.employer_origin_acquisition import AcquiredJobPage
from src.connectors.employer_origin_acquisition_v4_forms import MeteredRequest
from src.connectors.employer_origin_portal_delegation_acquisition import (
    acquire_via_explicit_portal,
)
from src.search_intelligence.deterministic_connector_builder import (
    ConnectorBuilderAssessment,
    passed,
    rewrite_residual_suffix,
    summarize_assessments,
)


SCHEMA = "job_application_pipeline.deterministic_connector_builder_layer_audit.v5"
PORTAL_OVERLAY_REQUEST_CAP = 4
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


def _promote_inventory_failure_via_portal(
    baseline: ConnectorBuilderAssessment,
    *,
    job: AcquiredJobPage,
    observed_portal: str,
    requests: list[dict[str, object]],
) -> ConnectorBuilderAssessment:
    """Promote one Inventory residual through a uniquely bound portal delegation."""

    # Inventory is the first failure, so Provider was already evaluated. Preserve
    # that provider decision rather than inventing a new ATS classification from
    # the portal bridge. Delegation, however, must be rewritten because the overlay
    # proves that an explicit employer -> portal handoff is required and executable.
    provider_result = baseline.layers[4]
    return rewrite_residual_suffix(
        baseline,
        expected_first_failure="inventory",
        rewrite_from_layer="delegation",
        replacement_suffix=(
            passed(
                "delegation",
                "one explicit strong employer portal CTA is uniquely bound and executable",
                carrier="explicit_portal_cta",
                observed_portal=_url_shape(observed_portal),
                overlay="evidence_bounded_portal_v1",
            ),
            provider_result,
            passed(
                "inventory",
                "portal-bound deterministic acquisition exposed a concrete job path",
                discovery_source=job.discovery_source,
                overlay_requests=requests,
            ),
            passed(
                "detail",
                "portal-bound deterministic acquisition reached a concrete job detail",
                public_detail=_url_shape(job.final_url),
                discovery_source=job.discovery_source,
            ),
            passed(
                "proof",
                "portal detail passes unchanged strict genuine-job proof",
                proof_kind=job.proof_kind,
            ),
            passed(
                "recipe",
                "all evidence-required layers are satisfied; connector recipe is compile-ready",
                materialization_performed=False,
                observed_portal=_url_shape(observed_portal),
                portal_overlay=True,
            ),
        ),
    )


def _portal_overlay(
    row: dict[str, Any],
    args: argparse.Namespace,
    baseline: ConnectorBuilderAssessment,
) -> tuple[ConnectorBuilderAssessment, dict[str, object] | None]:
    failure = baseline.first_failure
    if failure is None or failure.layer != "inventory":
        return baseline, None

    origin_url, origin_evidence = base_audit._resolve_origin(row, args)
    if not origin_url:
        return baseline, {
            "company_key": baseline.company_key,
            "decision": "not_attempted",
            "reason": "origin unavailable during portal overlay",
            "origin_evidence": origin_evidence,
            "requests": [],
        }

    origin_host = (urlparse(origin_url).hostname or "").casefold()
    if not origin_host:
        return baseline, {
            "company_key": baseline.company_key,
            "decision": "not_attempted",
            "reason": "origin lacks a valid host during portal overlay",
            "origin": _url_shape(origin_url),
            "requests": [],
        }

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-builder-v5-portal-overlay/0.1 (+bounded read-only)",
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        }
    )
    calls: list[dict[str, object]] = []

    def execute(request: MeteredRequest) -> tuple[str, str, int]:
        if len(calls) >= PORTAL_OVERLAY_REQUEST_CAP:
            raise RuntimeError("absolute portal overlay request cap exceeded")
        parsed = urlparse(request.url)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            raise RuntimeError("portal overlay permits absolute HTTPS only")

        method = request.method.upper()
        fields = dict(request.fields)
        if method == "GET":
            response = session.get(
                request.url,
                params=fields or None,
                timeout=args.http_timeout_seconds,
                allow_redirects=True,
            )
        elif method == "POST":
            response = session.post(
                request.url,
                data=fields,
                timeout=args.http_timeout_seconds,
                allow_redirects=True,
            )
        else:
            raise RuntimeError(f"unsupported portal overlay method: {method}")

        body = response.content
        if len(body) > MAX_BODY_BYTES:
            raise RuntimeError("portal overlay response body cap exceeded")
        text = body.decode(response.encoding or "utf-8", errors="replace")
        calls.append(
            {
                "method": method,
                "requested": _url_shape(request.url),
                "final": _url_shape(str(response.url)),
                "field_keys": sorted(fields),
                "status": int(response.status_code),
                "body_bytes": len(body),
            }
        )
        return text, str(response.url), int(response.status_code)

    try:
        jobs, observed_portal = acquire_via_explicit_portal(
            listing_url=origin_url,
            allowed_hosts=(origin_host,),
            known_detail_urls=(),
            fetcher=lambda url: execute(MeteredRequest(url)),
            request_executor=execute,
            max_followup_requests=2,
            max_results=1,
        )
    except Exception as exc:
        return baseline, {
            "company_key": baseline.company_key,
            "decision": "not_proven",
            "reason": f"{type(exc).__name__}: {exc}"[:500],
            "origin": _url_shape(origin_url),
            "requests": calls,
        }

    if not jobs:
        return baseline, {
            "company_key": baseline.company_key,
            "decision": "not_proven",
            "reason": "strict portal overlay did not produce unchanged genuine-job proof",
            "origin": _url_shape(origin_url),
            "observed_portal": _url_shape(observed_portal),
            "requests": calls,
        }

    job = jobs[0]
    promoted = _promote_inventory_failure_via_portal(
        baseline,
        job=job,
        observed_portal=observed_portal,
        requests=calls,
    )
    return promoted, {
        "company_key": baseline.company_key,
        "decision": "promoted",
        "from_first_failure": "inventory",
        "to_recipe_ready": True,
        "observed_portal": _url_shape(observed_portal),
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
            "Replay the same all-candidate builder cohort and compose ordered, monotonic "
            "Workday then portal residual overlays only on Inventory first-failures."
        )
    )
    parser.add_argument("--output", default="/tmp/deterministic_connector_builder_layer_audit_v5.json")
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

    # Preserve the exact V3 baseline semantics. V5 is only ordered residual
    # composition above that baseline: Workday first, then portal if Inventory still
    # remains the first failure.
    base_audit.run_origin_discovery = run_origin_discovery_v4
    base_audit.discover_navigation_candidates = (
        discover_navigation_candidates_with_provider_inventory
    )

    with base_audit._connect() as conn:
        candidates = base_audit._load_candidates(conn)

    v3_assessments: list[ConnectorBuilderAssessment] = []
    v4_assessments: list[ConnectorBuilderAssessment] = []
    v5_assessments: list[ConnectorBuilderAssessment] = []
    workday_results: list[dict[str, object]] = []
    portal_results: list[dict[str, object]] = []

    for index, row in enumerate(candidates, start=1):
        v3 = base_audit._assessment(row, args)
        v3_assessments.append(v3)

        v4, workday = v4_audit._workday_overlay(row, args, v3)
        v4_assessments.append(v4)
        if workday is not None:
            workday_results.append(workday)

        v5, portal = _portal_overlay(row, args, v4)
        v5_assessments.append(v5)
        if portal is not None:
            portal_results.append(portal)

        _print_assessment(v5, index, len(candidates))
        if index < len(candidates) and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    v3_summary = summarize_assessments(v3_assessments)
    v4_summary = summarize_assessments(v4_assessments)
    v5_summary = summarize_assessments(v5_assessments)
    workday_promoted = [item for item in workday_results if item.get("decision") == "promoted"]
    portal_promoted = [item for item in portal_results if item.get("decision") == "promoted"]

    payload = {
        "schema": SCHEMA,
        "measurement_note": (
            "V5 is a read-only diagnostic replay of the same candidate cohort. Ordered "
            "residual overlays are monotonic by builder contract. Recipe-ready remains "
            "diagnostic and does not promote canonical product coverage without materialized "
            "unchanged strict E2E proof."
        ),
        "overlay_order": ["workday_cxs_detail_v1", "evidence_bounded_portal_v1"],
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
            "baseline_network_methods": ["GET"],
            "workday_overlay_network_methods": ["GET", "POST"],
            "portal_overlay_network_methods": ["GET", "POST"],
            "baseline_absolute_get_cap_per_candidate": base_audit.ABSOLUTE_ACQUISITION_GET_CAP,
            "workday_overlay_request_cap_per_inventory_residual": v4_audit.WORKDAY_OVERLAY_REQUEST_CAP,
            "portal_overlay_request_cap_per_remaining_inventory_residual": PORTAL_OVERLAY_REQUEST_CAP,
            "diagnostic_overlays_have_independent_caps": True,
            "origin_generated_candidate_cap": args.origin_max_candidates,
        },
        "comparison": {
            "v3_summary": v3_summary,
            "v4_summary": v4_summary,
            "v5_summary": v5_summary,
            "workday_promoted_count": len(workday_promoted),
            "workday_promoted_company_keys": [
                str(item["company_key"]) for item in workday_promoted
            ],
            "portal_promoted_count": len(portal_promoted),
            "portal_promoted_company_keys": [
                str(item["company_key"]) for item in portal_promoted
            ],
        },
        "workday_overlay_results": workday_results,
        "portal_overlay_results": portal_results,
        "results": [item.to_json() for item in v5_assessments],
    }

    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("============================================")
    print("DETERMINISTIC CONNECTOR BUILDER V5")
    print("============================================")
    print("v3=" + json.dumps(v3_summary, sort_keys=True))
    print("v4=" + json.dumps(v4_summary, sort_keys=True))
    print("v5=" + json.dumps(v5_summary, sort_keys=True))
    print(f"workday_promoted={len(workday_promoted)}")
    print(f"portal_promoted={len(portal_promoted)}")
    print(f"artifact={out}")
    print("CONNECTOR_BUILDER_V5=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
