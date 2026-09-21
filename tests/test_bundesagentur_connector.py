from __future__ import annotations

from unittest.mock import Mock, patch

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.bundesagentur import BundesagenturConnector


def _profile() -> SearchProfile:
    return SearchProfile(
        id=1,
        profile_name="ba-demo",
        source_name="bundesagentur_fuer_arbeit",
        search_location="30629",
        search_radius_km=50,
        offer_type=1,
        page_size=10,
    )


def test_bundesagentur_uses_current_v6_search_endpoint_and_accepts_referenznummer() -> None:
    response = Mock()
    response.url = (
        "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
        "?was=Analytics+Engineer&wo=30629"
    )
    response.json.return_value = {
        "stellenangebote": [
            {
                "referenznummer": "10001-123-S",
                "externeUrl": "https://example.org/jobs/123",
                "titel": "Analytics Engineer",
            }
        ]
    }

    with patch("src.connectors.bundesagentur.requests.get", return_value=response) as get:
        records, request_url = BundesagenturConnector().fetch_jobs(
            _profile(),
            SearchTerm("Analytics Engineer"),
        )

    response.raise_for_status.assert_called_once_with()
    assert get.call_args.args[0].endswith("/pc/v6/jobs")
    assert get.call_args.kwargs["headers"]["X-API-Key"] == "jobboerse-jobsuche"
    assert records[0].external_job_id == "10001-123-S"
    assert records[0].source_url == "https://example.org/jobs/123"
    assert request_url == response.url


def test_bundesagentur_keeps_refnr_compatibility_in_payload_shape() -> None:
    response = Mock()
    response.url = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
    response.json.return_value = {
        "stellenangebote": [
            {
                "refnr": "10001-legacy-S",
                "url": "https://example.org/jobs/legacy",
            }
        ]
    }

    with patch("src.connectors.bundesagentur.requests.get", return_value=response):
        records, _request_url = BundesagenturConnector().fetch_jobs(
            _profile(),
            SearchTerm("Data Engineer"),
        )

    assert records[0].external_job_id == "10001-legacy-S"
    assert records[0].source_url == "https://example.org/jobs/legacy"



def test_bundesagentur_pages_until_short_page_and_deduplicates() -> None:
    profile = SearchProfile(
        id=1,
        profile_name="ba-demo",
        source_name="bundesagentur_fuer_arbeit",
        search_location="30629",
        search_radius_km=50,
        offer_type=1,
        page_size=2,
    )

    page1 = Mock()
    page1.url = "https://example.test/ba?page=1"
    page1.json.return_value = {
        "stellenangebote": [
            {"referenznummer": "10001-a-S", "titel": "Role A"},
            {"referenznummer": "10001-b-S", "titel": "Role B"},
        ]
    }
    page2 = Mock()
    page2.url = "https://example.test/ba?page=2"
    page2.json.return_value = {
        "stellenangebote": [
            {"referenznummer": "10001-b-S", "titel": "Role B duplicate"},
        ]
    }

    with patch(
        "src.connectors.bundesagentur.requests.get",
        side_effect=[page1, page2],
    ) as get:
        records, request_url = BundesagenturConnector().fetch_jobs(
            profile,
            SearchTerm("AI Automation Architect"),
        )

    assert get.call_count == 2
    assert get.call_args_list[0].kwargs["params"]["page"] == 1
    assert get.call_args_list[1].kwargs["params"]["page"] == 2
    assert [record.external_job_id for record in records] == [
        "10001-a-S",
        "10001-b-S",
    ]
    assert records[0].raw_data["search_profile"]["page"] == 1
    assert request_url == page1.url


def test_bundesagentur_pagination_is_bounded_by_connector_cap() -> None:
    profile = SearchProfile(
        id=1,
        profile_name="ba-demo",
        source_name="bundesagentur_fuer_arbeit",
        search_location="30629",
        search_radius_km=50,
        offer_type=1,
        page_size=1,
    )
    responses = []
    for page in range(1, BundesagenturConnector.max_pages + 1):
        response = Mock()
        response.url = f"https://example.test/ba?page={page}"
        response.json.return_value = {
            "stellenangebote": [
                {"referenznummer": f"10001-{page}-S", "titel": f"Role {page}"}
            ]
        }
        responses.append(response)

    with patch(
        "src.connectors.bundesagentur.requests.get",
        side_effect=responses,
    ) as get:
        records, _ = BundesagenturConnector().fetch_jobs(
            profile,
            SearchTerm("AI"),
        )

    assert get.call_count == BundesagenturConnector.max_pages
    assert len(records) == BundesagenturConnector.max_pages



def test_bundesagentur_maps_current_v6_ergebnisliste_to_canonical_bronze_contract() -> None:
    response = Mock()
    response.url = (
        "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
        "?was=AI&wo=30629&page=1"
    )
    response.json.return_value = {
        "ergebnisliste": [
            {
                "referenznummer": "10001-1003339347-S",
                "externeURL": "https://example.org/jobs/hornet",
                "stellenangebotsTitel": (
                    "AI Automation Architect - Software Development Lifecycle"
                ),
                "firma": "Hornetsecurity GmbH",
                "stellenlokationen": [{"ort": "Hannover", "plz": "30159"}],
                "datumErsteVeroeffentlichung": "2026-08-01",
                "aenderungsdatum": "2026-09-16",
            }
        ],
        "page": 1,
        "size": 10,
    }

    with patch("src.connectors.bundesagentur.requests.get", return_value=response):
        records, _ = BundesagenturConnector().fetch_jobs(
            _profile(),
            SearchTerm("AI"),
        )

    assert len(records) == 1
    record = records[0]
    assert record.external_job_id == "10001-1003339347-S"
    assert record.source_url == "https://example.org/jobs/hornet"
    assert record.raw_data["provider_schema"] == "ba_jobsuche_v6"
    assert record.raw_data["job"]["titel"] == (
        "AI Automation Architect - Software Development Lifecycle"
    )
    assert record.raw_data["job"]["arbeitgeber"] == "Hornetsecurity GmbH"
    assert record.raw_data["job"]["arbeitsort"] == [
        {"ort": "Hannover", "plz": "30159"}
    ]
    assert record.raw_data["job"]["aktuelleVeroeffentlichungsdatum"] == "2026-09-16"
