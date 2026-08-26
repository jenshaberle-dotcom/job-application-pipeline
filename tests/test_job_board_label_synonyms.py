from src.search_intelligence.connector_feasibility_runtime import (
    extract_trusted_delegated_job_board_urls,
)


def test_stellenboerse_is_strong_only_on_job_specific_same_site_route() -> None:
    origin_url = "https://www.example.com/karriere"
    board_url = "https://www.example.com/karriere/stellenboerse"
    html = f'<a href="{board_url}">Stellenbörse</a>'

    assert extract_trusted_delegated_job_board_urls(origin_url, html) == (board_url,)


def test_stellensuche_is_strong_only_on_job_specific_same_site_route() -> None:
    origin_url = "https://www.example.com/karriere"
    board_url = "https://www.example.com/karriere/stellensuche"
    html = f'<a href="{board_url}">Stellensuche</a>'

    assert extract_trusted_delegated_job_board_urls(origin_url, html) == (board_url,)


def test_generic_boerse_label_does_not_expand_discovery() -> None:
    origin_url = "https://www.example.com/karriere"
    html = '<a href="https://www.example.com/boerse">Börse</a>'

    assert extract_trusted_delegated_job_board_urls(origin_url, html) == ()
