from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from src.connectors.base import JobSourceConnector
from src.connectors.bundesagentur import BundesagenturConnector
from src.connectors.greenhouse import GreenhouseConnector
from src.connectors.personio import PersonioConnector
from src.connectors.stepstone import StepStoneConnector
from src.connectors.successfactors import SuccessFactorsConnector


class ConnectorFactory(Protocol):
    def __call__(self, source_name: str) -> JobSourceConnector: ...


class SourceRole(StrEnum):
    """Operational role of one registered acquisition source.

    Sensors discover or observe the market but are not employer-origin activity
    authority. Employer-origin sources are the only connector role allowed to
    establish authoritative positive job freshness through normal ingestion.
    """

    SENSOR = "sensor"
    EMPLOYER_ORIGIN = "employer_origin"


@dataclass
class ConnectorRegistry:
    """Code-backed connector registry for ingestion-time connector creation.

    The registry keeps CLI/runner connector lookup separate from source activation.
    Registering a connector factory here only teaches the ingestion code how to
    instantiate a connector for a source name. A source still needs an active DB
    search profile before ingestion can run and write Bronze rows.

    Source role is separate metadata on the same registration. This keeps sensor
    and employer-origin failure domains explicit without maintaining a second
    company/source allowlist in the scheduler.
    """

    exact_factories: dict[str, ConnectorFactory] = field(default_factory=dict)
    family_factories: dict[str, ConnectorFactory] = field(default_factory=dict)
    exact_roles: dict[str, SourceRole] = field(default_factory=dict)
    family_roles: dict[str, SourceRole] = field(default_factory=dict)

    def register_exact(
        self,
        source_name: str,
        factory: ConnectorFactory,
        *,
        role: SourceRole | str | None = None,
        replace: bool = False,
    ) -> None:
        if not source_name or source_name.startswith(":") or source_name.endswith(":"):
            raise ValueError("source_name must be a non-empty exact source name")
        self._register(self.exact_factories, source_name, factory, replace=replace)
        self._register_role(self.exact_roles, source_name, role, replace=replace)

    def register_family(
        self,
        source_family: str,
        factory: ConnectorFactory,
        *,
        role: SourceRole | str | None = None,
        replace: bool = False,
    ) -> None:
        if not source_family or ":" in source_family:
            raise ValueError("source_family must be a non-empty family key without ':'")
        self._register(
            self.family_factories,
            source_family,
            factory,
            replace=replace,
        )
        self._register_role(
            self.family_roles,
            source_family,
            role,
            replace=replace,
        )

    def create(self, source_name: str) -> JobSourceConnector:
        factory = self.exact_factories.get(source_name)
        if factory is not None:
            return factory(source_name)

        family = source_family(source_name)
        factory = self.family_factories.get(family)
        if factory is not None:
            return factory(source_name)

        raise ValueError(f"No connector configured for source: {source_name}")

    def role_for(self, source_name: str) -> SourceRole:
        role = self.exact_roles.get(source_name)
        if role is not None:
            return role

        role = self.family_roles.get(source_family(source_name))
        if role is not None:
            return role

        raise ValueError(f"No source role configured for source: {source_name}")

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

    @staticmethod
    def _register_role(
        target: dict[str, SourceRole],
        key: str,
        role: SourceRole | str | None,
        *,
        replace: bool,
    ) -> None:
        if role is None:
            return
        normalized = SourceRole(role)
        if key in target and target[key] != normalized and not replace:
            raise ValueError(f"Source role already registered for {key!r}.")
        target[key] = normalized


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


def successfactors_factory(source_name: str) -> JobSourceConnector:
    return SuccessFactorsConnector(target_key=source_target(source_name))


def build_default_connector_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register_exact(
        "bundesagentur_fuer_arbeit",
        bundesagentur_factory,
        role=SourceRole.SENSOR,
    )
    registry.register_family(
        "greenhouse",
        greenhouse_factory,
        role=SourceRole.EMPLOYER_ORIGIN,
    )
    registry.register_family(
        "personio",
        personio_factory,
        role=SourceRole.EMPLOYER_ORIGIN,
    )
    registry.register_exact(
        "stepstone",
        stepstone_factory,
        role=SourceRole.SENSOR,
    )
    registry.register_family(
        "successfactors",
        successfactors_factory,
        role=SourceRole.EMPLOYER_ORIGIN,
    )

    from src.connectors.employer_origin_registry import register_employer_origin_connectors

    register_employer_origin_connectors(registry)
    return registry


DEFAULT_CONNECTOR_REGISTRY = build_default_connector_registry()


def create_connector(source_name: str) -> JobSourceConnector:
    return DEFAULT_CONNECTOR_REGISTRY.create(source_name)


def source_role(source_name: str) -> SourceRole:
    return DEFAULT_CONNECTOR_REGISTRY.role_for(source_name)
