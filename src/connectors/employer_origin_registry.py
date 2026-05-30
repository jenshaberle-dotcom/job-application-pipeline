from __future__ import annotations

from src.connectors.finanz_informatik import FinanzInformatikConnector
from src.connectors.registry import ConnectorRegistry


# Employer-origin connector registration is intentionally code-backed.
# Adding a connector here does not activate ingestion by itself; Bronze writes still require
# a separately reviewed active search profile / controlled activation migration.
def finanz_informatik_hannover_factory(source_name: str) -> FinanzInformatikConnector:
    return FinanzInformatikConnector()


def register_employer_origin_connectors(registry: ConnectorRegistry) -> None:
    registry.register_exact(
        "finanz_informatik:hannover",
        finanz_informatik_hannover_factory,
    )
