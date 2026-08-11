from __future__ import annotations

from src.connectors.accompio import AccompioConnector
from src.connectors.computacenter import ComputacenterConnector
from src.connectors.enercity import EnercityConnector
from src.connectors.finanz_informatik import FinanzInformatikConnector
from src.connectors.hdi import HdiConnector
from src.connectors.registry import ConnectorRegistry, SourceRole


# Employer-origin connector registration is intentionally code-backed.
# Adding a connector here does not activate ingestion by itself; Bronze writes still require
# a separately reviewed active search profile / controlled activation migration.
def finanz_informatik_hannover_factory(source_name: str) -> FinanzInformatikConnector:
    return FinanzInformatikConnector()


def enercity_discovery_factory(source_name: str) -> EnercityConnector:
    return EnercityConnector()


def hdi_hannover_factory(source_name: str) -> HdiConnector:
    return HdiConnector()


def accompio_discovery_factory(source_name: str) -> AccompioConnector:
    return AccompioConnector()


def computacenter_discovery_factory(source_name: str) -> ComputacenterConnector:
    return ComputacenterConnector()


def register_employer_origin_connectors(registry: ConnectorRegistry) -> None:
    registry.register_exact(
        "finanz_informatik:hannover",
        finanz_informatik_hannover_factory,
        role=SourceRole.EMPLOYER_ORIGIN,
    )
    registry.register_exact(
        "enercity:discovery",
        enercity_discovery_factory,
        role=SourceRole.EMPLOYER_ORIGIN,
    )
    registry.register_exact(
        "hdi:hannover",
        hdi_hannover_factory,
        role=SourceRole.EMPLOYER_ORIGIN,
    )
    registry.register_exact(
        "accompio:discovery",
        accompio_discovery_factory,
        role=SourceRole.EMPLOYER_ORIGIN,
    )
    registry.register_exact(
        "computacenter:discovery",
        computacenter_discovery_factory,
        role=SourceRole.EMPLOYER_ORIGIN,
    )
