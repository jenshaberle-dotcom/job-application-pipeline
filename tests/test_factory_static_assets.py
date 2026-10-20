import pytest
from src.connectors.employer_origin_acquisition import non_job_url, parse_page
from src.connectors.employer_origin_acquisition_v4 import discover_navigation_candidates


@pytest.mark.parametrize("path", ["/gtag/js?id=12345", "/jobs/app.js?id=12345",
                                 "/assets/career.css", "/jobs/logo.svg"])
def test_static_assets_cannot_be_job_details(path):
    url="https://employer.example"+path
    assert non_job_url(url)
    page=parse_page(requested_url="https://employer.example",
                    final_url="https://employer.example",status_code=200,
                    html=f'<html><a href="{url}">Jobs</a><script src="{url}"></script></html>')
    assert not discover_navigation_candidates(page,allowed_hosts=("employer.example",),known_detail_urls=())


def test_pdf_and_json_are_not_blanket_excluded():
    assert not non_job_url("https://employer.example/jobs/123.pdf")
    assert not non_job_url("https://employer.example/jobs/123.json")
