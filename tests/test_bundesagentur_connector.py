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
