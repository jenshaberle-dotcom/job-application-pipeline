from pathlib import Path
from types import SimpleNamespace

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.stepstone import (
    StepStoneConnector,
    build_stepstone_search_url,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "stepstone_result_cards_sample.html"


class FakeResponse:
    def __init__(self, text: str, url: str) -> None:
        self.text = text
        self.url = url
        self.status_code = 200
        self.headers = {"content-type": "text/html; charset=utf-8"}
        self.content = text.encode("utf-8")
        self.elapsed = SimpleNamespace(total_seconds=lambda: 0.01)

    def raise_for_status(self) -> None:
        return None


def make_profile(page_size: int = 25) -> SearchProfile:
    return SearchProfile(
        id=1,
        profile_name="stepstone_data_engineer_hannover",
        source_name="stepstone",
        search_location="Hannover",
        search_radius_km=None,
        offer_type=None,
        page_size=page_size,
    )


def test_build_stepstone_search_url_with_location() -> None:
    url = build_stepstone_search_url(
        search_term="Data Engineer",
        search_location="Hannover",
    )

    assert url == "https://www.stepstone.de/jobs/data-engineer/in-hannover"


def test_stepstone_connector_capabilities_are_limited() -> None:
    connector = StepStoneConnector()

    assert connector.source_name == "stepstone"
    assert connector.capabilities.supports_keyword is True
    assert connector.capabilities.supports_location is True
    assert connector.capabilities.supports_radius is False
    assert connector.capabilities.supports_pagination is False
    assert connector.capabilities.supports_full_fetch is False


def test_fetch_jobs_builds_raw_job_records_from_result_cards(monkeypatch) -> None:
    fixture_html = FIXTURE_PATH.read_text()
    final_url = "https://www.stepstone.de/jobs/data-engineer/in-hannover"

    def fake_get(url, headers, timeout, allow_redirects):
        assert url == final_url
        assert "limited result-card connector" in headers["User-Agent"]
        assert timeout == 20
        assert allow_redirects is True
        return FakeResponse(text=fixture_html, url=final_url)

    monkeypatch.setattr("src.connectors.stepstone.requests.get", fake_get)

    connector = StepStoneConnector()

    records, returned_url = connector.fetch_jobs(
        profile=make_profile(),
        search_term=SearchTerm(search_term="Data Engineer"),
    )

    assert returned_url == final_url
    assert len(records) == 2

    first = records[0]

    assert first.source_name == "stepstone"
    assert first.external_job_id == "123456"
    assert first.source_url == (
        "https://www.stepstone.de/stellenangebote--"
        "Data-Engineer-Hannover-Example-Data-GmbH--123456-inline.html"
    )

    assert first.raw_data["result_card"]["title"] == "Data Engineer (m/w/d)"
    assert first.raw_data["result_card"]["company_name"] == "Example Data GmbH"
    assert first.raw_data["result_card"]["location"] == "Hannover"
    assert first.raw_data["result_card"]["publication_hint_text"] == "vor 2 Tagen"
    assert first.raw_data["result_card"]["salary_hint_text"] is None
    assert first.raw_data["result_card"]["salary_ui_prompt_text"] == "Gehalt anzeigen"
    assert first.raw_data["result_card"]["remote_hint_text"] == "Teilweise Home-Office"
    assert first.raw_data["result_card"]["employment_type_hint_text"] == "Vollzeit"

    assert first.raw_data["source_specific"]["article_external_job_id"] == "123456"
    assert first.raw_data["source_specific"]["detail_url_external_job_id"] == "123456"
    assert first.raw_data["source_specific"]["title_id_matches_article_id"] is True

    assert first.raw_data["extraction"]["detail_page_fetched"] is False
    assert first.raw_data["extraction"]["pagination_used"] is False
    assert first.raw_data["extraction"]["connector_mode"] == "limited_result_card"
    assert first.raw_data["quality_signals"]["id_match"] is True


def test_fetch_jobs_does_not_promote_mismatching_external_id(monkeypatch) -> None:
    fixture_html = FIXTURE_PATH.read_text()
    final_url = "https://www.stepstone.de/jobs/data-engineer/in-hannover"

    def fake_get(url, headers, timeout, allow_redirects):
        return FakeResponse(text=fixture_html, url=final_url)

    monkeypatch.setattr("src.connectors.stepstone.requests.get", fake_get)

    connector = StepStoneConnector()

    records, _ = connector.fetch_jobs(
        profile=make_profile(),
        search_term=SearchTerm(search_term="Data Engineer"),
    )

    second = records[1]

    assert second.raw_data["result_card"]["external_job_id_candidate"] == "222222"
    assert second.raw_data["source_specific"]["detail_url_external_job_id"] == "333333"
    assert second.raw_data["quality_signals"]["id_match"] is False
    assert second.external_job_id is None


def test_fetch_jobs_respects_profile_page_size(monkeypatch) -> None:
    fixture_html = FIXTURE_PATH.read_text()
    final_url = "https://www.stepstone.de/jobs/data-engineer/in-hannover"

    def fake_get(url, headers, timeout, allow_redirects):
        return FakeResponse(text=fixture_html, url=final_url)

    monkeypatch.setattr("src.connectors.stepstone.requests.get", fake_get)

    connector = StepStoneConnector()

    records, _ = connector.fetch_jobs(
        profile=make_profile(page_size=1),
        search_term=SearchTerm(search_term="Data Engineer"),
    )

    assert len(records) == 1
