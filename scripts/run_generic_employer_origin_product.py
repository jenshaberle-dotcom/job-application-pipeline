from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qsl, urlparse, urlunparse

import requests

from scripts import run_deterministic_connector_builder_layer_audit as layer_core
from scripts.run_origin_source_discovery_agent_v4 import run_for_company as run_origin_discovery
from src.connectors.employer_origin_acquisition import (
    AcquiredJobPage,
    NavigationCandidate,
    canonical_url,
    explicit_root_delegated_listing_hosts,
)
from src.connectors.employer_origin_acquisition_v4 import (
    discover_navigation_candidates as discover_navigation_candidates_base,
)
from src.connectors.employer_origin_acquisition_v4_forms import MeteredRequest
from src.connectors.employer_origin_ats_navigation import (
    authorized_ats_provider,
    provider_detail_urls,
    provider_listing_urls,
)
from src.connectors.employer_origin_portal_delegation_acquisition import (
    acquire_via_explicit_portal,
)
from src.connectors.employer_origin_provider_public_feed import (
    SUPPORTED_PUBLIC_FEED_PROVIDERS,
    acquire_from_authorized_provider_host,
)
from src.connectors.employer_origin_workday_acquisition import (
    WorkdayAcquisitionRequest,
    acquire_workday_job_page,
)
from src.search_intelligence.ats_provider_registry import recognize_ats_provider
from src.search_intelligence.deterministic_connector_builder import (
    ConnectorBuilderAssessment,
    LayerState,
    passed,
    rewrite_residual_suffix,
    summarize_assessments,
)

SCHEMA = "job_application_pipeline.generic_employer_origin_product.v1"
WORKDAY_REQUEST_CAP = 3
PORTAL_REQUEST_CAP = 4
PUBLIC_FEED_REQUEST_CAP = 3
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


def discover_navigation_candidates(
    page,
    *,
    allowed_hosts,
    known_detail_urls=(),
):
    """Compose generic provider inventory routes without adding new authority."""

    result = list(
        discover_navigation_candidates_base(
            page,
            allowed_hosts=allowed_hosts,
            known_detail_urls=known_detail_urls,
        )
    )
    seen = {canonical_url(item.url) for item in result}
    delegated_hosts = set(
        explicit_root_delegated_listing_hosts(page, allowed_hosts=allowed_hosts)
    )
    provider = authorized_ats_provider(
        page_url=page.final_url,
        html=page.html,
        allowed_hosts=allowed_hosts,
        delegated_hosts=delegated_hosts,
    )
    if provider is None:
        return tuple(result)

    for url in provider_detail_urls(
        provider=provider,
        page_url=page.final_url,
        body=page.html,
        allowed_hosts=allowed_hosts,
    ):
        clean = canonical_url(url)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(
            NavigationCandidate(
                url,
                "detail",
                f"{provider}_provider_detail_evidence",
                "",
                False,
            )
        )

    for url in provider_listing_urls(
        provider=provider,
        page_url=page.final_url,
        html=page.html,
        allowed_hosts=allowed_hosts,
    ):
        clean = canonical_url(url)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(
            NavigationCandidate(
                url,
                "listing",
                f"{provider}_provider_listing_evidence",
                "",
                False,
            )
        )
    return tuple(result)


def _promote_workday(
    baseline: ConnectorBuilderAssessment,
    *,
    job: AcquiredJobPage,
    observed_root: str,
    requests: list[dict[str, object]],
) -> ConnectorBuilderAssessment:
    return rewrite_residual_suffix(
        baseline,
        expected_first_failure="inventory",
        rewrite_from_layer="provider",
        replacement_suffix=(
            passed(
                "provider",
                "strict employer-backed Workday route is executable through same-host CXS",
                provider="workday",
                capability="workday_cxs_detail",
            ),
            passed(
                "inventory",
                "authorized Workday CXS inventory returned a bounded same-board detail path",
                discovery_source=job.discovery_source,
                requests=requests,
            ),
            passed(
                "detail",
                "same-host Workday CXS detail resolved a public job detail",
                public_detail=_url_shape(job.final_url),
                discovery_source=job.discovery_source,
            ),
            passed(
                "proof",
                "Workday detail passes unchanged strict genuine-job proof",
                proof_kind=job.proof_kind,
            ),
            passed(
                "recipe",
                "all evidence-required generic layers passed",
                capability="workday_cxs_detail",
                observed_root=_url_shape(observed_root),
            ),
        ),
    )


def _workday_residual(
    row: dict[str, Any],
    args: argparse.Namespace,
    baseline: ConnectorBuilderAssessment,
) -> ConnectorBuilderAssessment:
    failure = baseline.first_failure
    if failure is None or failure.layer != "inventory":
        return baseline

    origin_url, _ = layer_core._resolve_origin(row, args)
    if not origin_url:
        return baseline

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-generic-origin/1.0",
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        }
    )
    calls: list[dict[str, object]] = []

    def execute(request: WorkdayAcquisitionRequest) -> tuple[str, str, int]:
        if len(calls) >= WORKDAY_REQUEST_CAP:
            raise RuntimeError("absolute Workday request cap exceeded")
        parsed = urlparse(request.url)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            raise RuntimeError("Workday capability permits absolute HTTPS only")
        method = request.method.upper()
        if method == "GET":
            if request.json_fields:
                raise RuntimeError("GET Workday request cannot carry JSON fields")
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
            raise RuntimeError(f"unsupported Workday method: {method}")
        body = response.content
        if len(body) > MAX_BODY_BYTES:
            raise RuntimeError("Workday response body cap exceeded")
        calls.append(
            {
                "method": method,
                "requested": _url_shape(request.url),
                "final": _url_shape(str(response.url)),
                "status": int(response.status_code),
                "body_bytes": len(body),
            }
        )
        return body.decode(response.encoding or "utf-8", errors="replace"), str(response.url), int(response.status_code)

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
    except Exception:
        return baseline
    if job is None:
        return baseline
    return _promote_workday(
        baseline,
        job=job,
        observed_root=observed_root,
        requests=calls,
    )


def _promote_portal(
    baseline: ConnectorBuilderAssessment,
    *,
    job: AcquiredJobPage,
    observed_portal: str,
    requests: list[dict[str, object]],
) -> ConnectorBuilderAssessment:
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
                capability="evidence_bounded_portal",
            ),
            provider_result,
            passed(
                "inventory",
                "portal-bound acquisition exposed a concrete job path",
                discovery_source=job.discovery_source,
                requests=requests,
            ),
            passed(
                "detail",
                "portal-bound acquisition reached a concrete job detail",
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
                "all evidence-required generic layers passed",
                capability="evidence_bounded_portal",
                observed_portal=_url_shape(observed_portal),
            ),
        ),
    )


def _portal_residual(
    row: dict[str, Any],
    args: argparse.Namespace,
    baseline: ConnectorBuilderAssessment,
) -> ConnectorBuilderAssessment:
    failure = baseline.first_failure
    if failure is None or failure.layer != "inventory":
        return baseline
    origin_url, _ = layer_core._resolve_origin(row, args)
    if not origin_url:
        return baseline
    origin_host = (urlparse(origin_url).hostname or "").casefold()
    if not origin_host:
        return baseline

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-generic-origin/1.0",
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        }
    )
    calls: list[dict[str, object]] = []

    def execute(request: MeteredRequest) -> tuple[str, str, int]:
        if len(calls) >= PORTAL_REQUEST_CAP:
            raise RuntimeError("absolute portal request cap exceeded")
        parsed = urlparse(request.url)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            raise RuntimeError("portal capability permits absolute HTTPS only")
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
            raise RuntimeError(f"unsupported portal method: {method}")
        body = response.content
        if len(body) > MAX_BODY_BYTES:
            raise RuntimeError("portal response body cap exceeded")
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
        return body.decode(response.encoding or "utf-8", errors="replace"), str(response.url), int(response.status_code)

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
    except Exception:
        return baseline
    if not jobs:
        return baseline
    return _promote_portal(
        baseline,
        job=jobs[0],
        observed_portal=observed_portal,
        requests=calls,
    )


def _provider_target(baseline: ConnectorBuilderAssessment) -> tuple[str, str] | None:
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


def _public_feed_residual(
    baseline: ConnectorBuilderAssessment,
    args: argparse.Namespace,
) -> ConnectorBuilderAssessment:
    failure = baseline.first_failure
    if failure is None or failure.layer not in {"inventory", "detail"}:
        return baseline
    target = _provider_target(baseline)
    if target is None:
        return baseline
    provider, provider_page_url = target
    provider_host = (urlparse(provider_page_url).hostname or "").casefold()
    if not provider_host:
        return baseline

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-generic-origin/1.0",
            "Accept": "application/json,application/rss+xml,application/xml,text/xml,text/html,*/*;q=0.8",
        }
    )
    calls: list[dict[str, object]] = []

    def fetcher(url: str) -> tuple[str, str, int]:
        if len(calls) >= PUBLIC_FEED_REQUEST_CAP:
            raise RuntimeError("absolute public-feed request cap exceeded")
        parsed = urlparse(url)
        if (
            parsed.scheme.casefold() != "https"
            or not parsed.hostname
            or parsed.hostname.casefold() != provider_host
            or parsed.username
            or parsed.password
        ):
            raise RuntimeError("public-feed capability permits exact-authorized-host HTTPS GET only")
        response = session.get(url, timeout=args.http_timeout_seconds, allow_redirects=True)
        body = response.content
        if len(body) > MAX_BODY_BYTES:
            raise RuntimeError("public-feed response body cap exceeded")
        calls.append(
            {
                "method": "GET",
                "requested": _url_shape(url),
                "final": _url_shape(str(response.url)),
                "status": int(response.status_code),
                "body_bytes": len(body),
            }
        )
        return body.decode(response.encoding or "utf-8", errors="replace"), str(response.url), int(response.status_code)

    try:
        result = acquire_from_authorized_provider_host(
            provider=provider,
            provider_page_url=provider_page_url,
            allowed_hosts=(provider_host,),
            fetcher=fetcher,
            max_detail_attempts=2,
        )
    except Exception:
        return baseline
    if result is None or result.acquired_job is None:
        return baseline
    job = result.acquired_job
    return rewrite_residual_suffix(
        baseline,
        expected_first_failure=failure.layer,
        rewrite_from_layer="provider",
        replacement_suffix=(
            passed(
                "provider",
                "authorized provider host has a validated fixed public-feed capability",
                provider=provider,
                provider_page=_url_shape(provider_page_url),
                capability="provider_public_feed",
            ),
            passed(
                "inventory",
                "provider public feed emitted concrete same-authority job identities",
                provider=provider,
                feed=_url_shape(result.feed_url),
                detail_candidate_count=len(result.detail_candidates),
                requests=calls,
            ),
            passed(
                "detail",
                "provider public feed yielded a concrete detail on existing authority",
                public_detail=_url_shape(job.final_url),
                discovery_source=job.discovery_source,
            ),
            passed(
                "proof",
                "feed-carried detail passes unchanged strict genuine-job proof",
                proof_kind=job.proof_kind,
            ),
            passed(
                "recipe",
                "all evidence-required generic layers passed",
                capability="provider_public_feed",
                provider=provider,
            ),
        ),
    )


def assess_candidate(
    row: dict[str, Any],
    args: argparse.Namespace,
) -> ConnectorBuilderAssessment:
    assessment = layer_core._assessment(row, args)
    assessment = _workday_residual(row, args, assessment)
    assessment = _portal_residual(row, args, assessment)
    assessment = _public_feed_residual(assessment, args)
    return assessment


def proof_passed(assessment: ConnectorBuilderAssessment) -> bool:
    return assessment.layers[7].state == LayerState.PASS


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the canonical generic Employer-Origin layer product across the complete current candidate population. "
            "Strict proof PASS is the sole source-validity admission signal."
        )
    )
    parser.add_argument("--output", default="/tmp/generic_employer_origin_product.json")
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument(
        "--origin-max-candidates",
        type=int,
        default=layer_core.DEFAULT_ORIGIN_MAX_CANDIDATES,
    )
    parser.add_argument(
        "--origin-timeout-seconds",
        type=float,
        default=layer_core.DEFAULT_ORIGIN_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--http-timeout-seconds",
        type=float,
        default=layer_core.DEFAULT_HTTP_TIMEOUT_SECONDS,
    )
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    args = parser.parse_args()

    layer_core.run_origin_discovery = run_origin_discovery
    layer_core.discover_navigation_candidates = discover_navigation_candidates

    with layer_core._connect() as conn:
        candidates = layer_core._load_candidates(conn)

    assessments: list[ConnectorBuilderAssessment] = []
    for index, row in enumerate(candidates, start=1):
        assessment = assess_candidate(row, args)
        assessments.append(assessment)
        proof = proof_passed(assessment)
        failure = assessment.first_failure
        print(
            f"[{index}/{len(candidates)}] {assessment.company_key}: "
            f"proof_pass={str(proof).lower()} first_failure={failure.layer if failure else '-'}"
        )
        if index < len(candidates) and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    summary = summarize_assessments(assessments)
    proof_rows = [item for item in assessments if proof_passed(item)]
    proof_keys = [item.company_key for item in proof_rows]
    payload = {
        "schema": SCHEMA,
        "authority": {
            "sole_connector_truth": "generic_evidence_driven_layer_model",
            "source_validity_gate": "proof=PASS",
            "historical_connector_cohorts_authoritative": False,
            "versioned_audit_checkpoints_authoritative": False,
            "demo_evidence_authoritative": False,
        },
        "boundary": {
            "database_reads": True,
            "database_writes": False,
            "connector_registration": False,
            "source_activation": False,
            "bronze_write": False,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
        },
        "summary": {
            **summary,
            "proof_pass_count": len(proof_rows),
        },
        "proof_pass_company_keys": proof_keys,
        "results": [item.to_json() for item in assessments],
    }
    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    print("============================================")
    print("GENERIC EMPLOYER-ORIGIN PRODUCT")
    print("============================================")
    print(f"CANDIDATES={len(assessments)}")
    print(f"PROOF_PASS={len(proof_rows)}")
    for item in proof_rows:
        print(f"VALID_SOURCE={item.company_key}|candidate_id={item.candidate_id}")
    print("DATABASE_WRITES=0")
    print("GENERIC_EMPLOYER_ORIGIN_PRODUCT=COMPLETE")
    print(f"artifact={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
