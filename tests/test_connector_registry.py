from __future__ import annotations

import pytest

from src.connectors.generic_employer_origin import GenericEmployerOriginConnector
from src.connectors.greenhouse import GreenhouseConnector
from src.connectors.personio import PersonioConnector
from src.connectors.registry import (
    ConnectorRegistry,
    SourceRole,
    create_connector,
    greenhouse_factory,
    personio_factory,
    source_family,
    source_role,
    source_target,
)


def test_source_family_and_target_are_explicit() -> None:
    assert source_family("generic_origin:finanz_informatik") == "generic_origin"
    assert source_target("generic_origin:finanz_informatik") == "finanz_informatik"

    with pytest.raises(ValueError):
        source_target("generic_origin")

    with pytest.raises(ValueError):
        source_target("generic_origin:")


def test_default_registry_exposes_one_generic_employer_origin_family() -> None:
    connector = create_connector("generic_origin:finanz_informatik")

    assert isinstance(connector, GenericEmployerOriginConnector)
    assert connector.company_key == "finanz_informatik"
    assert connector.source_name == "generic_origin:finanz_informatik"
    assert source_role(connector.source_name) == SourceRole.EMPLOYER_ORIGIN


def test_provider_specific_connectors_are_capabilities_not_default_product_truth() -> None:
    for source_name in (
        "greenhouse:stripe",
        "personio:eraneos",
        "successfactors:eon_germany",
        "finanz_informatik:hannover",
        "enercity:discovery",
        "hdi:hannover",
        "accompio:discovery",
        "computacenter:discovery",
    ):
        with pytest.raises(ValueError, match="No connector configured"):
            create_connector(source_name)


def test_provider_connector_factories_remain_reusable_generic_capabilities() -> None:
    registry = ConnectorRegistry()
    registry.register_family("greenhouse", greenhouse_factory)
    registry.register_family("personio", personio_factory)

    assert isinstance(registry.create("greenhouse:stripe"), GreenhouseConnector)
    assert isinstance(registry.create("personio:eraneos"), PersonioConnector)


def test_registry_rejects_duplicate_registration_without_replace() -> None:
    registry = ConnectorRegistry()
    registry.register_family("greenhouse", greenhouse_factory)

    with pytest.raises(ValueError):
        registry.register_family("greenhouse", greenhouse_factory)


def test_registry_keeps_registration_separate_from_activation() -> None:
    registry = ConnectorRegistry()
    registry.register_family("personio", personio_factory)

    connector = registry.create("personio:example")

    assert isinstance(connector, PersonioConnector)
    assert not hasattr(registry, "activate")
