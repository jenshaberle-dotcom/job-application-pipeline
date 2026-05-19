from pathlib import Path

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.personio import (
    PersonioConnector,
    build_personio_xml_url,
    normalize_target_key,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "personio_jobs_sample.xml"


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


def make_profile(page_size: int = 25) -> SearchProfile:
    return SearchProfile(
        id=1,
        profile_name="personio_schluetersche_data_engineer_hannover",
        source_name="personio:schluetersche-mediengruppe",
        search_location="Hannover",
        search_radius_km=None,
        offer_type=None,
        page_size=page_size,
    )


def fake_personio_get(fixture: bytes):
    def fake_get(url, headers, timeout):
        assert url == (
            "https://schluetersche-mediengruppe.jobs.personio.de"
            "/xml?language=de"
        )
        assert "public XML feed" in headers["User-Agent"]
        assert timeout == 20
        return FakeResponse(content=fixture)

    return fake_get


def test_normalize_target_key_accepts_key_and_host() -> None:
    assert (
        normalize_target_key("schluetersche-mediengruppe")
        == "schluetersche-mediengruppe"
    )
    assert (
        normalize_target_key("schluetersche-mediengruppe.jobs.personio.de")
        == "schluetersche-mediengruppe"
    )


def test_build_personio_xml_url() -> None:
    assert build_personio_xml_url(
        host="schluetersche-mediengruppe.jobs.personio.de",
        language="de",
    ) == "https://schluetersche-mediengruppe.jobs.personio.de/xml?language=de"


def test_personio_connector_capabilities_are_defensive() -> None:
    connector = PersonioConnector(target_key="schluetersche-mediengruppe")

    assert connector.source_name == "personio:schluetersche-mediengruppe"
    assert connector.capabilities.supports_keyword is False
    assert connector.capabilities.supports_location is False
    assert connector.capabilities.supports_radius is False
    assert connector.capabilities.supports_pagination is False
    assert connector.capabilities.supports_full_fetch is True


def test_fetch_jobs_filters_records_by_search_term(monkeypatch) -> None:
    fixture = FIXTURE_PATH.read_bytes()
    monkeypatch.setattr(
        "src.connectors.personio.requests.get",
        fake_personio_get(fixture),
    )

    connector = PersonioConnector(target_key="schluetersche-mediengruppe")

    records, requested_url = connector.fetch_jobs(
        profile=make_profile(),
        search_term=SearchTerm(id=1, search_term="Data Engineer"),
    )

    assert requested_url == (
        "https://schluetersche-mediengruppe.jobs.personio.de"
        "/xml?language=de"
    )
    assert len(records) == 1

    first = records[0]

    assert first.source_name == "personio:schluetersche-mediengruppe"
    assert first.external_job_id == "2498694"
    assert first.source_url == (
        "https://schluetersche-mediengruppe.jobs.personio.de"
        "/job/2498694?language=de"
    )

    assert "search_profile" not in first.raw_data
    assert first.raw_data["source_target"]["source_family"] == "personio"
    assert first.raw_data["source_target"]["target_key"] == "schluetersche-mediengruppe"
    assert first.raw_data["job"]["title"] == "Data Engineer (m/w/d)"
    assert first.raw_data["job"]["company_name"] == (
        "Schlütersche Verlagsgesellschaft mbH & Co. KG"
    )
    assert first.raw_data["job"]["location"] == "Hannover"
    assert first.raw_data["extraction"]["detail_page_fetched"] is False
    assert first.raw_data["extraction"]["pagination_used"] is False
    assert first.raw_data["extraction"]["local_keyword_filtering_used"] is True
    assert first.raw_data["quality_signals"]["has_external_job_id"] is True


def test_fetch_jobs_allows_wildcard_search_term(monkeypatch) -> None:
    fixture = FIXTURE_PATH.read_bytes()
    monkeypatch.setattr(
        "src.connectors.personio.requests.get",
        fake_personio_get(fixture),
    )

    connector = PersonioConnector(target_key="schluetersche-mediengruppe")

    records, _ = connector.fetch_jobs(
        profile=make_profile(),
        search_term=SearchTerm(id=1, search_term="*"),
    )

    assert len(records) == 2


def test_fetch_jobs_respects_profile_page_size_after_filtering(monkeypatch) -> None:
    fixture = FIXTURE_PATH.read_bytes()
    monkeypatch.setattr(
        "src.connectors.personio.requests.get",
        fake_personio_get(fixture),
    )

    connector = PersonioConnector(target_key="schluetersche-mediengruppe")

    records, _ = connector.fetch_jobs(
        profile=make_profile(page_size=1),
        search_term=SearchTerm(id=1, search_term="*"),
    )

    assert len(records) == 1
