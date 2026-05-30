from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from src.connectors.base import JobSourceConnector
from src.connectors.bundesagentur import BundesagenturConnector
from src.connectors.greenhouse import GreenhouseConnector
from src.connectors.personio import PersonioConnector
from src.connectors.stepstone import StepStoneConnector


class ConnectorFactory(Protocol):
    def __call__(self, source_name: str) -> JobSourceConnector: ...


@dataclass
class ConnectorRegistry:
    """Code-backed connector registry for ingestion-time connector creation.

    The registry keeps CLI/runner connector lookup separate from source activation.
    Registering a connector factory here only teaches the ingestion code how to instantiate
    a connector for a source name. A source still needs an active DB search profile before
    ingestion can run and write Bronze rows.
    """

    exact_factories: dict[str, ConnectorFactory] = field(default_factory=dict)
    family_factories: dict[str, ConnectorFactory] = field(default_factory=dict)

    def register_exact(self, source_name: str, factory: ConnectorFactory, *, replace: bool = False) -> None:
        if not source_name or source_name.startswith(":") or source_name.endswith(":"):
            raise ValueError("source_name must be a non-empty exact source name")
        self._register(self.exact_factories, source_name, factory, replace=replace)

    def register_family(self, source_family: str, factory: ConnectorFactory, *, replace: bool = False) -> None:
        if not source_family or ":" in source_family:
            raise ValueError("source_family must be a non-empty family key without ':'")
        self._register(self.family_factories, source_family, factory, replace=replace)

    def create(self, source_name: str) -> JobSourceConnector:
        factory = self.exact_factories.get(source_name)
        if factory is not None:
            return factory(source_name)

        family = source_family(source_name)
        factory = self.family_factories.get(family)
        if factory is not None:
            return factory(source_name)

        raise ValueError(f"No connector configured for source: {source_name}")

    @staticmethod
    def _register(
        target: dict[str, ConnectorFactory],
        key: str,
        factory: ConnectorFactory,
        *,
        replace: bool,
    ) -> None:
        if key in target and not replace:
            raise ValueError(f"Connector factory already registered for {key!r}.")
        target[key] = factory


def source_family(source_name: str) -> str:
    return source_name.split(":", 1)[0]


def source_target(source_name: str) -> str:
    if ":" not in source_name:
        raise ValueError(f"Source name {source_name!r} does not contain a source target.")
    family, target = source_name.split(":", 1)
    if not family or not target:
        raise ValueError(f"Source name {source_name!r} must use '<family>:<target>'.")
    return target


def bundesagentur_factory(source_name: str) -> JobSourceConnector:
    return BundesagenturConnector()


def greenhouse_factory(source_name: str) -> JobSourceConnector:
    return GreenhouseConnector(board_token=source_target(source_name))


def personio_factory(source_name: str) -> JobSourceConnector:
    return PersonioConnector(target_key=source_target(source_name))


def stepstone_factory(source_name: str) -> JobSourceConnector:
    return StepStoneConnector()


def build_default_connector_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register_exact("bundesagentur_fuer_arbeit", bundesagentur_factory)
    registry.register_family("greenhouse", greenhouse_factory)
    registry.register_family("personio", personio_factory)
    registry.register_exact("stepstone", stepstone_factory)

    from src.connectors.employer_origin_registry import register_employer_origin_connectors

    register_employer_origin_connectors(registry)
    return registry


DEFAULT_CONNECTOR_REGISTRY = build_default_connector_registry()


def create_connector(source_name: str) -> JobSourceConnector:
    return DEFAULT_CONNECTOR_REGISTRY.create(source_name)
