from __future__ import annotations

from src.connectors.employer_origin_acquisition_v4_forms import (
    MeteredRequest,
    acquire_genuine_job_pages,
)


ROOT = "https://jobs.example.invalid/"
HOST = "jobs.example.invalid"
LISTING = "https://jobs.example.invalid/Stellenangebote.html"
ASSET = "https://jobs.example.invalid/_Resources/JavaScript/main.min.js"
API = "https://jobs.example.invalid/api/job-links"
DETAIL = "https://jobs.example.invalid/stellenausschreibungen/platform-engineer-m-w-d-108436.html"
LEGACY_DETAIL = "https://jobs.example.invalid/jobs/platform-engineer-67890"


def _root_html(*, strong_detail: bool = False, ambiguous_assets: bool = False) -> str:
    detail = f"<a href='{LEGACY_DETAIL}'>Platform Engineer</a>" if strong_detail else ""
    second_asset = "<script src='/assets/app.js'></script>" if ambiguous_assets else ""
    return (
        "<html><title>Karriere</title><body>"
        f"{detail}<a href='{LISTING}'>Stellenangebote</a>"
        "<script src='/_Resources/JavaScript/main.min.js'></script>"
        f"{second_asset}</body></html>"
    )


def _job_html() -> str:
    return (
        "<html><title>Platform Engineer (m/w/d)</title><body>"
        "<h1>Platform Engineer (m/w/d)</h1>"
        "<h2>Ihre Aufgaben</h2><p>Sie entwickeln und betreiben unsere Plattform.</p>"
        "<h2>Ihre Qualifikation</h2><p>Erfahrung mit Python und Cloud-Systemen.</p>"
        "<p>Jetzt bewerben. Bewerbungsschluss und Stellennummer 108436.</p>"
        "</body></html>"
    )


def test_explicit_app_asset_to_job_link_api_to_known_detail_fits_hard_four_request_path() -> None:
    calls: list[MeteredRequest] = []

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(ROOT):
            return _root_html(), ROOT, 200
        if request == MeteredRequest(ASSET):
            return 'const endpoint="/api/job-links"; fetch(endpoint);', ASSET, 200
        if request == MeteredRequest(API):
            return '{"items":[{"url":"/stellenausschreibungen/platform-engineer-m-w-d-108436.html"}]}', API, 200
        if request == MeteredRequest(DETAIL):
            return _job_html(), DETAIL, 200
        if request == MeteredRequest(LISTING):
            raise AssertionError("weak listing must not preempt explicit job-link path")
        raise AssertionError(request)

    jobs, observed_root = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
        request_executor=executor,
        max_followup_requests=2,
    )

    assert observed_root == ROOT
    assert calls == [
        MeteredRequest(ROOT),
        MeteredRequest(ASSET),
        MeteredRequest(API),
        MeteredRequest(DETAIL),
    ]
    assert len(jobs) == 1
    assert jobs[0].final_url == DETAIL
    assert jobs[0].proof_kind == "known_detail_and_job_content"
    assert jobs[0].discovery_source == "explicit_job_link_inventory_detail"


def test_existing_strong_root_detail_keeps_priority_over_application_asset() -> None:
    calls: list[MeteredRequest] = []

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(ROOT):
            return _root_html(strong_detail=True), ROOT, 200
        if request == MeteredRequest(LEGACY_DETAIL):
            return _job_html(), LEGACY_DETAIL, 200
        if request == MeteredRequest(ASSET):
            raise AssertionError("application asset must stay behind strong root detail")
        raise AssertionError(request)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
        request_executor=executor,
        max_followup_requests=2,
    )

    assert calls == [MeteredRequest(ROOT), MeteredRequest(LEGACY_DETAIL)]
    assert len(jobs) == 1


def test_asset_without_explicit_job_link_route_restores_legacy_listing_opportunity() -> None:
    calls: list[MeteredRequest] = []

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(ROOT):
            return _root_html(), ROOT, 200
        if request == MeteredRequest(ASSET):
            return 'fetch("/api/departments")', ASSET, 200
        if request == MeteredRequest(LISTING):
            return f"<html><a href='{LEGACY_DETAIL}'>Platform Engineer</a></html>", LISTING, 200
        if request == MeteredRequest(LEGACY_DETAIL):
            return _job_html(), LEGACY_DETAIL, 200
        raise AssertionError(request)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
        request_executor=executor,
        max_followup_requests=2,
    )

    assert calls == [
        MeteredRequest(ROOT),
        MeteredRequest(ASSET),
        MeteredRequest(LISTING),
        MeteredRequest(LEGACY_DETAIL),
    ]
    assert len(jobs) == 1


def test_ambiguous_application_assets_leave_legacy_path_unchanged() -> None:
    calls: list[MeteredRequest] = []

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(ROOT):
            return _root_html(ambiguous_assets=True), ROOT, 200
        if request == MeteredRequest(LISTING):
            return f"<html><a href='{LEGACY_DETAIL}'>Platform Engineer</a></html>", LISTING, 200
        if request == MeteredRequest(LEGACY_DETAIL):
            return _job_html(), LEGACY_DETAIL, 200
        if request in {MeteredRequest(ASSET), MeteredRequest("https://jobs.example.invalid/assets/app.js")}:
            raise AssertionError("ambiguous assets must not create acquisition authority")
        raise AssertionError(request)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
        request_executor=executor,
        max_followup_requests=2,
    )

    assert calls == [MeteredRequest(ROOT), MeteredRequest(LISTING), MeteredRequest(LEGACY_DETAIL)]
    assert len(jobs) == 1
