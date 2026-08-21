from __future__ import annotations

from src.connectors.employer_origin_acquisition_v4_forms import (
    MeteredRequest,
    acquire_genuine_job_pages,
)


HOST = "jobs.example.invalid"
ROOT = f"https://{HOST}/"
SITEMAP = f"https://{HOST}/sitemap.xml"
GO = f"https://{HOST}/go/Germany/4411601"
DETAIL = f"https://{HOST}/job/Berlin-Platform-Engineer-BE-10115/1234567890"
SF_HINT = "https://career5.successfactors.eu/career?company=example"


def _root_html(*, with_form: bool = False) -> str:
    form = "<form method='get' action='/search'><input name='q' type='text'></form>" if with_form else ""
    return (
        "<html><title>Jobs</title><body>"
        f"<a href='{SF_HINT}'>Sign in</a>"
        f"<a href='{GO}'>Germany</a>"
        f"{form}</body></html>"
    )


def _sitemap_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>{DETAIL}</loc></url>
    </urlset>
    """


def _job_html() -> str:
    return (
        "<html><title>Platform Engineer</title><body>"
        "Apply now. Responsibilities, requirements and your profile. "
        "Build and operate reliable distributed services with production ownership, "
        "engineering quality standards and cross-functional delivery responsibility."
        "</body></html>"
    )


def test_successfactors_sitemap_inventory_reaches_strict_detail_in_three_requests() -> None:
    calls: list[MeteredRequest] = []

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(ROOT):
            return _root_html(), ROOT, 200
        if request == MeteredRequest(SITEMAP):
            return _sitemap_xml(), SITEMAP, 200
        if request == MeteredRequest(DETAIL):
            return _job_html(), DETAIL, 200
        if request == MeteredRequest(GO):
            raise AssertionError("sitemap detail inventory must outrank weaker /go listing navigation")
        raise AssertionError(request)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=ROOT,
        allowed_hosts=(HOST,),
        known_detail_urls=(),
        fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
        request_executor=executor,
        max_followup_requests=2,
    )

    assert calls == [MeteredRequest(ROOT), MeteredRequest(SITEMAP), MeteredRequest(DETAIL)]
    assert len(jobs) == 1
    assert jobs[0].final_url == DETAIL
    assert jobs[0].discovery_source == "successfactors_sitemap_detail"
    assert jobs[0].proof_kind == "job_url_and_job_content"


def test_sitemap_transport_failure_is_optional_and_old_provider_path_still_fits_cap() -> None:
    calls: list[MeteredRequest] = []

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(ROOT):
            return _root_html(), ROOT, 200
        if request == MeteredRequest(SITEMAP):
            raise RuntimeError("simulated sitemap 404")
        if request == MeteredRequest(GO):
            return f"<html><a href='{DETAIL}'>Platform Engineer</a></html>", GO, 200
        if request == MeteredRequest(DETAIL):
            return _job_html(), DETAIL, 200
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
        MeteredRequest(SITEMAP),
        MeteredRequest(GO),
        MeteredRequest(DETAIL),
    ]
    assert len(jobs) == 1


def test_explicit_root_search_form_remains_preferred_over_sitemap() -> None:
    search = f"https://{HOST}/search"
    calls: list[MeteredRequest] = []

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(ROOT):
            return _root_html(with_form=True), ROOT, 200
        if request == MeteredRequest(search, "GET", (("q", ""),)):
            return f"<html><a href='{DETAIL}'>Platform Engineer</a></html>", search, 200
        if request == MeteredRequest(DETAIL):
            return _job_html(), DETAIL, 200
        if request == MeteredRequest(SITEMAP):
            raise AssertionError("root form must suppress sitemap fallback")
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
        MeteredRequest(search, "GET", (("q", ""),)),
        MeteredRequest(DETAIL),
    ]
    assert len(jobs) == 1
