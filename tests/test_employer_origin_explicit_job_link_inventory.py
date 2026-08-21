from __future__ import annotations

from src.connectors.employer_origin_explicit_job_link_inventory import (
    explicit_job_detail_urls_from_inventory,
    explicit_same_host_job_link_inventory_url,
    strict_same_host_application_script_url,
)


ROOT = "https://jobs.example.invalid/"
HOST = "jobs.example.invalid"
MAIN = "https://jobs.example.invalid/_Resources/JavaScript/main.min.js"


def test_unique_same_host_main_script_outranks_libraries_and_external_assets() -> None:
    html = """
    <html><body>
      <script src="/_Resources/JavaScript/main.min.js"></script>
      <script src="/_Resources/Assets/swiper/swiper-bundle.min.js"></script>
      <script src="/_Resources/Assets/shareon/shareon.iife.js"></script>
      <script src="https://static.other.invalid/app.js"></script>
    </body></html>
    """
    assert (
        strict_same_host_application_script_url(
            page_url=ROOT,
            html=html,
            allowed_hosts=(HOST,),
        )
        == MAIN
    )


def test_multiple_application_scripts_fail_closed() -> None:
    html = """
    <script src="/assets/main.js"></script>
    <script src="/assets/app.js"></script>
    """
    assert (
        strict_same_host_application_script_url(
            page_url=ROOT,
            html=html,
            allowed_hosts=(HOST,),
        )
        is None
    )


def test_asset_must_explicitly_name_one_same_host_job_link_inventory() -> None:
    assert (
        explicit_same_host_job_link_inventory_url(
            asset_url=MAIN,
            javascript='const endpoint="/api/job-links"; fetch(endpoint);',
            allowed_hosts=(HOST,),
        )
        == "https://jobs.example.invalid/api/job-links"
    )
    assert (
        explicit_same_host_job_link_inventory_url(
            asset_url=MAIN,
            javascript='fetch("/api/job-links"); fetch("/api/job-urls");',
            allowed_hosts=(HOST,),
        )
        is None
    )
    assert (
        explicit_same_host_job_link_inventory_url(
            asset_url=MAIN,
            javascript='fetch("/api/departments");',
            allowed_hosts=(HOST,),
        )
        is None
    )


def test_inventory_extracts_only_strict_same_host_vacancy_details() -> None:
    body = """
    {
      "items": [
        {"url": "/stellenausschreibungen/platform-engineer-m-w-d-108436.html"},
        {"url": "/dienststellen/ministerium.html"},
        {"url": "/_Resources/Persistent/image.jpg"},
        {"url": "https://external.invalid/stellenausschreibungen/data-engineer-117652.html"}
      ]
    }
    """
    assert explicit_job_detail_urls_from_inventory(
        api_url="https://jobs.example.invalid/api/job-links",
        body=body,
        allowed_hosts=(HOST,),
    ) == ("https://jobs.example.invalid/stellenausschreibungen/platform-engineer-m-w-d-108436.html",)


def test_inventory_rejects_non_json_and_generic_listing_paths() -> None:
    assert explicit_job_detail_urls_from_inventory(
        api_url="https://jobs.example.invalid/api/job-links",
        body="not-json",
        allowed_hosts=(HOST,),
    ) == ()
    assert explicit_job_detail_urls_from_inventory(
        api_url="https://jobs.example.invalid/api/job-links",
        body='{"url":"/Stellenangebote.html"}',
        allowed_hosts=(HOST,),
    ) == ()
