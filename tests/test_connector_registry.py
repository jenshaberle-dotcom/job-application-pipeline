from __future__ import annotations

import pytest

from src.connectors.finanz_informatik import FinanzInformatikConnector
from src.connectors.greenhouse import GreenhouseConnector
from src.connectors.personio import PersonioConnector
from src.connectors.registry import (
    ConnectorRegistry,
    create_connector,
    greenhouse_factory,
    personio_factory,
    source_family,
    source_target,
)


def test_source_family_and_target_are_explicit() -> None:
    assert source_family("greenhouse:stripe") == "greenhouse"
    assert source_target("greenhouse:stripe") == "stripe"

    with pytest.raises(ValueError):
        source_target("greenhouse")

    with pytest.raises(ValueError):
        source_target("greenhouse:")


def test_default_registry_creates_existing_dynamic_connectors() -> None:
    assert isinstance(create_connector("greenhouse:stripe"), GreenhouseConnector)
    assert isinstance(create_connector("personio:eraneos"), PersonioConnector)


def test_default_registry_creates_existing_employer_origin_connector() -> None:
    connector = create_connector("finanz_informatik:hannover")

    assert isinstance(connector, FinanzInformatikConnector)
    assert connector.source_name == "finanz_informatik:hannover"


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
