from src.search_intelligence.origin_url_policy import has_disallowed_source_url_shape


def test_origin_url_policy_rejects_static_assets() -> None:
    for url in (
        "https://jobs.ivv.de/templates/ivv_oevb/styles/base.css",
        "https://jobs.example.test/app.js",
        "https://jobs.example.test/font.woff2",
        "https://jobs.example.test/logo.svg",
    ):
        assert has_disallowed_source_url_shape(url) == "candidate URL points to a static asset"


def test_origin_url_policy_keeps_legitimate_jobspace_urls() -> None:
    assert has_disallowed_source_url_shape("https://www.jobs.ivv.de/") is None
    assert has_disallowed_source_url_shape("https://www.tib.eu/de/die-tib/karriere-und-ausbildung") is None
