from __future__ import annotations

import src.ingest_jobs as ingest_jobs
from src.connectors.base import SearchProfile
from src.connectors.capabilities import SourceCapabilities
from src.connectors.registry import SourceRole


PROFILE = SearchProfile(
    id=7,
    profile_name="example_origin",
    source_name="example:origin",
    search_location=None,
    search_radius_km=None,
    offer_type=None,
    page_size=25,
)


class FakeConnector:
    source_name = "example:origin"

    capabilities = SourceCapabilities(
        supports_keyword=False,
        supports_location=False,
        supports_radius=False,
        supports_employment_type=False,
        supports_remote_filter=False,
        supports_pagination=False,
        supports_full_fetch=True,
    )


def test_recurring_employer_origin_full_fetch_enables_health_repository(
    monkeypatch,
) -> None:
    sentinel = object()
    captured = {}

    monkeypatch.setattr(
        ingest_jobs,
        "create_connector",
        lambda source_name: FakeConnector(),
    )
    monkeypatch.setattr(
        ingest_jobs,
        "profile_source_role",
        lambda profile: SourceRole.EMPLOYER_ORIGIN,
    )
    monkeypatch.setattr(
        ingest_jobs,
        "JobLifecycleHealthRepository",
        lambda: sentinel,
    )

    class FakeRunner:
        def __init__(self, *, repository, connector, health_repository):
            captured["health_repository"] = health_repository

        def run(self, profile_name):
            captured["profile_name"] = profile_name

    monkeypatch.setattr(ingest_jobs, "JobIngestionRunner", FakeRunner)

    ingest_jobs.run_profile(
        repository=object(),
        profile=PROFILE,
        recurring_health_enabled=True,
    )

    assert captured["health_repository"] is sentinel
    assert captured["profile_name"] == PROFILE.profile_name


def test_explicit_profile_run_does_not_enable_recurring_health(
    monkeypatch,
) -> None:
    captured = {}

    monkeypatch.setattr(
        ingest_jobs,
        "create_connector",
        lambda source_name: FakeConnector(),
    )

    class FakeRunner:
        def __init__(self, *, repository, connector, health_repository):
            captured["health_repository"] = health_repository

        def run(self, profile_name):
            pass

    monkeypatch.setattr(ingest_jobs, "JobIngestionRunner", FakeRunner)

    ingest_jobs.run_profile(
        repository=object(),
        profile=PROFILE,
        recurring_health_enabled=False,
    )

    assert captured["health_repository"] is None
