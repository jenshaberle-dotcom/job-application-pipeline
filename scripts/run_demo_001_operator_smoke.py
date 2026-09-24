"""Final local operator smoke for the DEMO-001 reviewable demo path.

Requires the local demo server to be running. The smoke reads Product V1 truth,
re-validates all Top-5 employer-origin URLs live, and explicitly invokes one review-
only application generation for rank 1. It never submits or sends an application.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


from src.job_lifecycle_health import OUTCOME_SEEN_ACTIVE, JobLifecycleHealthRepository, classify_exact_detail, fetch_exact_detail

AGGREGATOR_HOSTS = (
    "arbeitsagentur.de",
    "gute-jobs.de",
    "stepstone.de",
    "indeed.com",
    "linkedin.com",
)


class DemoOperatorSmokeStop(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DemoOperatorSmokeStop(message)


def _host(url: object) -> str:
    return (urlsplit(str(url or "")).hostname or "").casefold()


def _is_aggregator(url: object) -> bool:
    host = _host(url)
    return any(host == item or host.endswith("." + item) for item in AGGREGATOR_HOSTS)


def main() -> int:
    base = "http://127.0.0.1:8781"
    with urlopen(f"{base}/api/v1/product-v1", timeout=15) as response:
        product = json.load(response)

    top = list(product.get("top_jobs") or [])
    _require(len(top) == 5, f"expected exactly five Top jobs, got {len(top)}")
    top.sort(key=lambda row: int(row.get("product_rank") or 999))

    print("=== DEMO-001 OPERATOR SMOKE ===")
    print(f"TOP_JOBS={len(top)}")
    health = JobLifecycleHealthRepository()
    for row in top:
        job_id = int(row["silver_job_id"])
        url = row.get("source_url")
        _require(str(row.get("product_readiness_status") or "") == "rankable", f"Top job not rankable: {job_id}")
        _require(bool(url), f"Top job source URL missing: {job_id}")
        _require(not _is_aggregator(url), f"aggregator leaked into Top-5 action URL: {job_id}|{url}")
        target = health.load_target(job_id)
        probe = fetch_exact_detail(str(url))
        classification = classify_exact_detail(target, probe)
        _require(classification.outcome == OUTCOME_SEEN_ACTIVE, f"Top job not live active: {job_id}|{classification.outcome}")
        print(
            "TOP_LIVE="
            f"{row.get('product_rank')}|{job_id}|score={row.get('overall_quality_score')}|"
            f"{_host(probe.final_url)}|{row.get('company_name')}|{row.get('title')}"
        )

    selected = top[0]
    selected_id = int(selected["silver_job_id"])
    body = json.dumps({"action": "generate_review_draft", "silver_job_id": selected_id}).encode("utf-8")
    request = Request(
        f"{base}/api/v1/product-v1/application-draft",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        draft = json.load(response)

    _require(draft.get("status") == "draft_for_review", "application did not reach draft_for_review")
    _require(int(draft.get("database_writes") or 0) == 0, "application generation wrote database state")
    _require(int(draft.get("submission_writes") or 0) == 0, "application generation wrote submission state")
    _require(int(draft.get("send_actions") or 0) == 0, "application generation performed send action")

    _require(
        draft.get("render_status") == "template_bound_renderer_qualified_review_export_available",
        "F6 renderer must expose only the qualified template-bound review/export path",
    )
    _require(
        draft.get("legacy_generic_document_export") is False,
        "legacy generic application export regained authority",
    )
    _require("document_package" not in draft, "legacy document package leaked into F6 draft")

    print(f"APPLICATION_JOB={selected_id}|{selected.get('company_name')}|{selected.get('title')}")
    print(f"DRAFT_MODE={draft.get('draft_mode')}")
    print(f"PROVIDER_REQUESTS={draft.get('provider_requests')}")
    print("F6_TEMPLATE_AUTHORITY=READY")
    print("LEGACY_GENERIC_DOCUMENT_EXPORT=false")
    print("RENDER_STATUS=template_bound_renderer_qualified_review_export_available")
    print("DATABASE_WRITES=0")
    print("SUBMISSION_WRITES=0")
    print("SEND_ACTIONS=0")
    print("DEMO_001_OPERATOR_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
