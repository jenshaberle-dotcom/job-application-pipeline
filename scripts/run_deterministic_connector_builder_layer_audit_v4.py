from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qsl, urlparse

import requests

from scripts import run_deterministic_connector_builder_layer_audit as base_audit
from scripts.run_deterministic_connector_builder_layer_audit_v3 import (
    discover_navigation_candidates_with_provider_inventory,
)
from scripts.run_origin_source_discovery_agent_v4 import run_for_company as run_origin_discovery_v4
from src.connectors.employer_origin_acquisition import AcquiredJobPage
from src.connectors.employer_origin_workday_acquisition import (
    WorkdayAcquisitionRequest,
    acquire_workday_job_page,
)
from src.search_intelligence.deterministic_connector_builder import (
    ConnectorBuilderAssessment,
    passed,
    summarize_assessments,
)


SCHEMA = "job_application_pipeline.deterministic_connector_builder_layer_audit.v4"
WORKDAY_OVERLAY_REQUEST_CAP = 3
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


def _promote_inventory_failure(
    baseline: ConnectorBuilderAssessment,
    *,
    job: AcquiredJobPage,
    observed_root: str,
    requests: list[dict[str, object]],
) -> ConnectorBuilderAssessment:
    """Promote only an existing Inventory failure after strict Workday E2E proof."""

    failure = baseline.first_failure
    if failure is None or failure.layer != "inventory":
        raise ValueError("Workday overlay may promote only an Inventory first-failure")

    layers = list(baseline.layers[:4])
    layers.extend(
        [
            passed(
                "provider",
                "strict employer-backed Workday route is executable through same-host CXS",
                provider="workday",
                overlay="workday_cxs_detail_v1",
            ),
            passed(
                "inventory",
                "exact authorized Workday CXS inventory returned one bounded same-board detail path",
                discovery_source=job.discovery_source,
                overlay_requests=requests,
            ),
            passed(
                "detail",
                "exact same-host Workday CXS detail carrier resolved the public job detail",
                public_detail=_url_shape(job.final_url),
                discovery_source=job.discovery_source,
            ),
            passed(
                "proof",
                "Workday CXS detail content passes unchanged strict genuine-job proof",
                proof_kind=job.proof_kind,
            ),
            passed(
                "recipe",
                "all evidence-required layers are satisfied; connector recipe is compile-ready",
                materialization_performed=False,
                observed_root=_url_shape(observed_root),
                workday_overlay=True,
            ),
        ]
    )
    return ConnectorBuilderAssessment(
        baseline.candidate_id,
        baseline.company_key,
        baseline.company_name,
        tuple(layers),
    )


def _workday_overlay(
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
            "reason": "origin unavailable during Workday overlay",
            "origin_evidence": origin_evidence,
            "requests": [],
        }

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-builder-v4-workday-overlay/0.1 (+bounded read-only)",
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        }
    )
    calls: list[dict[str, object]] = []

    def execute(request: WorkdayAcquisitionRequest) -> tuple[str, str, int]:
        if len(calls) >= WORKDAY_OVERLAY_REQUEST_CAP:
            raise RuntimeError("absolute Workday overlay request cap exceeded")
        parsed = urlparse(request.url)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            raise RuntimeError("Workday overlay permits absolute HTTPS only")

        method = request.method.upper()
        if method == "GET":
            if request.json_fields:
                raise RuntimeError("GET Workday overlay request cannot carry JSON fields")
            response = session.get(
                request.url,
                timeout=args.http_timeout_seconds,
                allow_redirects=True,
            )
        elif method == "POST":
            response = session.post(
                request.url,
                json=dict(request.json_fields),
                timeout=args.http_timeout_seconds,
                allow_redirects=False,
                headers={"Content-Type": "application/json"},
            )
        else:
            raise RuntimeError(f"unsupported Workday overlay method: {method}")

        body = response.content
        if len(body) > MAX_BODY_BYTES:
            raise RuntimeError("Workday overlay response body cap exceeded")
        text = body.decode(response.encoding or "utf-8", errors="replace")
        calls.append(
            {
                "method": method,
                "requested": _url_shape(request.url),
                "final": _url_shape(str(response.url)),
                "status": int(response.status_code),
                "body_bytes": len(body),
            }
        )
        return text, str(response.url), int(response.status_code)

    try:
        job, observed_root = acquire_workday_job_page(
            listing_url=origin_url,
            allowed_hosts=tuple(
                sorted(
                    {
                        host
                        for value in (origin_url,)
                        if (host := (urlparse(value).hostname or "").casefold())
                    }
                )
            ),
            request_executor=execute,
        )
    except Exception as exc:
        return baseline, {
            "company_key": baseline.company_key,
            "decision": "not_proven",
            "reason": f"{type(exc).__name__}: {exc}"[:500],
            "origin": _url_shape(origin_url),
            "requests": calls,
        }

    if job is None:
        return baseline, {
            "company_key": baseline.company_key,
            "decision": "not_proven",
            "reason": "strict Workday overlay did not produce unchanged genuine-job proof",
            "origin": _url_shape(origin_url),
            "requests": calls,
        }

    promoted = _promote_inventory_failure(
        baseline,
        job=job,
        observed_root=observed_root,
        requests=calls,
    )
    return promoted, {
        "company_key": baseline.company_key,
        "decision": "promoted",
        "from_first_failure": "inventory",
        "to_recipe_ready": True,
        "public_detail": _url_shape(job.final_url),
        "proof_kind": job.proof_kind,
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
        description="Replay V3 builder across all candidates and overlay strict Workday CXS proof only on Inventory residuals."
    )
    parser.add_argument("--output", default="/tmp/deterministic_connector_builder_layer_audit_v4.json")
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

    # V4 is intentionally V3 + one Workday proof composition.  Preserve the
    # balanced origin planner and provider-inventory composition unchanged.
    base_audit.run_origin_discovery = run_origin_discovery_v4
    base_audit.discover_navigation_candidates = (
        discover_navigation_candidates_with_provider_inventory
    )

    with base_audit._connect() as conn:
        candidates = base_audit._load_candidates(conn)

    baseline_assessments: list[ConnectorBuilderAssessment] = []
    assessments: list[ConnectorBuilderAssessment] = []
    overlay_results: list[dict[str, object]] = []

    for index, row in enumerate(candidates, start=1):
        baseline = base_audit._assessment(row, args)
        baseline_assessments.append(baseline)
        assessment, overlay = _workday_overlay(row, args, baseline)
        assessments.append(assessment)
        if overlay is not None:
            overlay_results.append(overlay)
        _print_assessment(assessment, index, len(candidates))
        if index < len(candidates) and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    baseline_summary = summarize_assessments(baseline_assessments)
    summary = summarize_assessments(assessments)
    promoted = [item for item in overlay_results if item.get("decision") == "promoted"]

    payload = {
        "schema": SCHEMA,
        "measurement_note": (
            "V4 is a read-only diagnostic replay of the same candidate cohort. "
            "Recipe-ready remains diagnostic and does not promote canonical product coverage without materialized strict E2E proof."
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
            "baseline_network_methods": ["GET"],
            "workday_overlay_network_methods": ["GET", "POST"],
            "baseline_absolute_get_cap_per_candidate": base_audit.ABSOLUTE_ACQUISITION_GET_CAP,
            "workday_overlay_request_cap_per_inventory_residual": WORKDAY_OVERLAY_REQUEST_CAP,
            "origin_generated_candidate_cap": args.origin_max_candidates,
        },
        "comparison": {
            "baseline_v3_summary": baseline_summary,
            "v4_summary": summary,
            "workday_promoted_count": len(promoted),
            "workday_promoted_company_keys": [str(item["company_key"]) for item in promoted],
        },
        "workday_overlay_results": overlay_results,
        "results": [item.to_json() for item in assessments],
    }

    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("============================================")
    print("DETERMINISTIC CONNECTOR BUILDER V4")
    print("============================================")
    print("baseline=" + json.dumps(baseline_summary, sort_keys=True))
    print("v4=" + json.dumps(summary, sort_keys=True))
    print(f"workday_promoted={len(promoted)}")
    print(f"artifact={out}")
    print("CONNECTOR_BUILDER_V4=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
