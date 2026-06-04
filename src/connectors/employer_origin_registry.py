from __future__ import annotations

from src.connectors.enercity import EnercityConnector
from src.connectors.finanz_informatik import FinanzInformatikConnector
from src.connectors.hdi import HdiConnector
from src.connectors.registry import ConnectorRegistry


# Employer-origin connector registration is intentionally code-backed.
# Adding a connector here does not activate ingestion by itself; Bronze writes still require
# a separately reviewed active search profile / controlled activation migration.
def finanz_informatik_hannover_factory(source_name: str) -> FinanzInformatikConnector:
    return FinanzInformatikConnector()


def enercity_discovery_factory(source_name: str) -> EnercityConnector:
    return EnercityConnector()



def hdi_hannover_factory(source_name: str) -> HdiConnector:
    return HdiConnector()


def register_employer_origin_connectors(registry: ConnectorRegistry) -> None:
    registry.register_exact(
        "finanz_informatik:hannover",
        finanz_informatik_hannover_factory,
    )
    registry.register_exact(
        "enercity:discovery",
        enercity_discovery_factory,
    )
    registry.register_exact(
        "hdi:hannover",
        hdi_hannover_factory,
    )

