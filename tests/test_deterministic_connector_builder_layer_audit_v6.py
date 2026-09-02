from __future__ import annotations

from scripts.run_deterministic_connector_builder_layer_audit_v6 import (
    _promote_via_public_feed,
    _provider_target,
)
from src.search_intelligence.deterministic_connector_builder import (
    ConnectorBuilderAssessment,
    complete_after_failure,
    passed,
    skipped,
)


def _inventory_failure(*, provider: str, root_provider: str | None) -> ConnectorBuilderAssessment:
    prefix = [
        passed("identity", "identity"),
        passed("origin", "origin"),
        passed(
            "origin_reachability",
            "reachable",
            final={
                "scheme": "https",
                "host": "jobs.example.com",
                "path": "/careers",
                "query_keys": [],
            },
        ),
        skipped("delegation", "not required"),
        passed(
            "provider",
            "provider",
            provider=provider,
            root_provider=root_provider,
            delegated_provider_hints=[],
        ),
    ]
    return ConnectorBuilderAssessment(
        1,
        "acme",
        "Acme GmbH",
        complete_after_failure(
            prefix,
            failed_layer="inventory",
            failure_reason="inventory gap",
        ),
    )


def test_provider_target_reuses_existing_root_provider_authority() -> None:
    baseline = _inventory_failure(
        provider="successfactors",
        root_provider="successfactors",
    )
    assert _provider_target(baseline) == (
        "successfactors",
        "https://jobs.example.com/careers",
    )


def test_provider_target_rejects_unsupported_provider() -> None:
    baseline = _inventory_failure(provider="greenhouse", root_provider="greenhouse")
    assert _provider_target(baseline) is None


def test_provider_target_uses_one_explicit_delegated_canonical_host() -> None:
    prefix = [
        passed("identity", "identity"),
        passed("origin", "origin"),
        passed(
            "origin_reachability",
            "reachable",
            final={
                "scheme": "https",
                "host": "www.example.com",
                "path": "/careers",
                "query_keys": [],
            },
        ),
        passed(
            "delegation",
            "explicit provider host",
            delegated_hosts=["acme.recruitee.com"],
        ),
        passed(
            "provider",
            "delegated provider",
            provider="recruitee",
            root_provider=None,
            delegated_provider_hints=["recruitee"],
        ),
    ]
    baseline = ConnectorBuilderAssessment(
        2,
        "acme",
        "Acme GmbH",
        complete_after_failure(
            prefix,
            failed_layer="inventory",
            failure_reason="inventory gap",
        ),
    )
    assert _provider_target(baseline) == (
        "recruitee",
        "https://acme.recruitee.com/",
    )


def test_public_feed_promotion_is_monotonic_and_ready() -> None:
    baseline = _inventory_failure(
        provider="successfactors",
        root_provider="successfactors",
    )
    promoted = _promote_via_public_feed(
        baseline,
        provider="successfactors",
        provider_page_url="https://jobs.example.com/",
        feed_url="https://jobs.example.com/sitemal.xml",
        detail_url="https://jobs.example.com/job/data/123-en_US/",
        proof_kind="known_detail_and_job_content",
        discovery_source="successfactors_provider_public_feed",
        detail_candidate_count=8,
        requests=[{"method": "GET"}],
    )

    assert promoted.layers[:4] == baseline.layers[:4]
    assert promoted.first_failure is None
    assert promoted.recipe_ready is True
    assert promoted.layers[4].evidence["provider"] == "successfactors"
    assert promoted.layers[5].evidence["detail_candidate_count"] == 8
