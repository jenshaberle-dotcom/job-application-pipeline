from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.personio import PersonioConnector
from src.ingestion.recurring_observation_evidence import recurring_observation_evidence
from src.search_intelligence.personio_legacy_authority_bindings import (
    REVIEWED_LEGACY_PERSONIO_AUTHORITY_BINDINGS,
    reviewed_personio_authority_binding,
)
from src.search_intelligence.personio_target_authority import (
    validate_personio_target_authority,
)


ONEKOMMA5_XML = b"""<?xml version='1.0' encoding='UTF-8'?>
<workzag-jobs>
  <position>
    <id>1001</id>
    <name>Senior Analytics Engineer</name>
    <subcompany>1KOMMA5Â    <subcompany>1KOMMA5\xc2°    <subcompany>1KOMMA5\xc2\xb0 GmbH</subcompany>
    <office>Hamburg</office>
  </position>
  <position>
    <id>1002</id>
    <name>ML Engineer</name>
    <subcompany>Heartbeat AI GmbH</subcompany>
    <office>Remote</office>
  </position>
</workzag-jobs>
"""

ERANEOS_XML = b"""<?xml version='1.0' encoding='UTF-8'?>
<workzag-jobs>
  <position>
    <id>2001</id>
    <name>Senior AI Engineer</name>
    <subcompany>Eraneos Analytics Germany GmbH</subcompany>
    <office>Hamburg</office>
  </position>
</workzag-jobs>
"""


class FakeResponse:
    def __init__(self, *, content: bytes, url: str, status_code: int = 200) -> None:
        self.content = content
        self.url = url
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None


def make_profile(source_name: str) -> SearchProfile:
    return SearchProfile(
        id=1,
        profile_name=f"{source_name.replace(':', '_')}_profile",
        source_name=source_name,
        search_location=None,
        search_radius_km=None,
        offer_type=None,
        page_size=100,
    )


def test_reviewed_legacy_bindings_are_only_the_shadow_proven_targets() -> None:
    assert set(REVIEWED_LEGACY_PERSONIO_AUTHORITY_BINDINGS) == {
        "1komma5grad",
        "eraneos",
    }
    assert reviewed_personio_authority_binding("it-p") is None
    assert reviewed_personio_authority_binding("otl-akademie") is None
    assert reviewed_personio_authority_binding("schluetersche-mediengruppe") is None


def test_unreviewed_personio_target_never_gets_recurring_authority(monkeypatch) -> None:
    target = "schluetersche-mediengruppe"
    url = f"https://{target}.jobs.personio.de/xml?language=de"
    fixture = Path("tests/fixtures/personio_jobs_sample.xml").read_bytes()
    monkeypatch.setattr(
        "src.connectors.personio.requests.get",
        lambda *_args, **_kwargs: FakeResponse(content=fixture, url=url),
    )

    records, _ = PersonioConnector(target).fetch_jobs(
        make_profile(f"personio:{target}"), SearchTerm(search_term="*")
    )

    assert records
    assert all("ats_feed_authority" not in record.raw_data for record in records)
    assert all("source_type" not in record.raw_data for record in records)


def test_reviewed_personio_feed_validates_once_and_projects_current_authority(monkeypatch) -> None:
    target = "1komma5grad"
    url = f"https://{target}.jobs.personio.de/xml?language=de"
    monkeypatch.setattr(
        "src.connectors.personio.requests.get",
        lambda *_args, **_kwargs: FakeResponse(content=ONEKOMMA5_XML, url=url),
    )

    calls = []
    original = validate_personio_target_authority

    def spy(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(
        "src.search_intelligence.personio_target_authority.validate_personio_target_authority",
        spy,
    )

    records, _ = PersonioConnector(target).fetch_jobs(
        make_profile(f"personio:{target}"), SearchTerm(search_term="*")
    )

    assert len(calls) == 1
    assert len(records) == 2
    for record in records:
        authority = record.raw_data["ats_feed_authority"]
        assert record.raw_data["source_type"] == "employer_origin_ats_backed_career_site"
        assert authority["contract_version"] == "personio-recurring-feed-authority.v1"
        assert authority["reviewed_binding_contract"] == (
            "runtime_203_personio_target_authority_shadow_v1"
        )
        assert authority["provider"] == "personio"
        assert authority["target_key"] == target
        assert authority["authority_validated"] is True
        assert authority["employer_identity_bound"] is True
        assert authority["feed_inventory_complete"] is True
        assert authority["http_status_code"] == 200
        assert authority["product_authority"] is False
        assert record.raw_data["extraction"]["detail_page_fetched"] is False

        projected = recurring_observation_evidence(record)
        current = projected["raw_evidence"]
        assert current["source_type"] == "employer_origin_ats_backed_career_site"
        assert current["ats_feed_authority"]["authority_validated"] is True
        assert current["job"]["source_url"] == record.source_url
        assert "extraction" not in current


def test_reviewed_personio_validation_failure_does_not_grant_source_type(monkeypatch) -> None:
    target = "eraneos"
    url = f"https://{target}.jobs.personio.de/xml?language=de"
    mismatched = ERANEOS_XML.replace(
        b"Eraneos Analytics Germany GmbH", b"Unrelated Example Company GmbH"
    )
    monkeypatch.setattr(
        "src.connectors.personio.requests.get",
        lambda *_args, **_kwargs: FakeResponse(content=mismatched, url=url),
    )

    records, _ = PersonioConnector(target).fetch_jobs(
        make_profile(f"personio:{target}"), SearchTerm(search_term="*")
    )

    assert records
    for record in records:
        authority = record.raw_data["ats_feed_authority"]
        assert authority["authority_validated"] is False
        assert authority["employer_identity_bound"] is False
        assert authority["feed_inventory_complete"] is False
        assert "source_type" not in record.raw_data
        assert authority["product_authority"] is False


def test_authority_binding_does_not_change_personio_no_detail_fetch_contract() -> None:
    connector = PersonioConnector("1komma5grad")
    assert connector.capabilities.supports_full_fetch is True
    assert connector.capabilities.supports_pagination is False
