from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any, Final

from src.search_intelligence.eon_requirement_inventory import (
    INVENTORY_KEY,
    EonRequirementInventory,
)


TAG_MAP_KEY: Final = "EON-REQUIREMENT-TAG-MAP-001"
REPORT_SCHEMA: Final = "eon_requirement_tag_map.v1"
SOURCE_EXPECTATION_CLASS: Final = "profile_statement"
OBLIGATION_STRENGTH_UNSPECIFIED: Final = "unspecified"

_TAG_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


@dataclass(frozen=True)
class _RequirementTagSpec:
    statement_key: str
    text: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class EonRequirementTagMapping:
    order: int
    statement_key: str
    normalized_text_sha256: str
    text: str
    source_expectation_class: str
    obligation_strength: str
    tags: tuple[str, ...]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "statement_key": self.statement_key,
            "normalized_text_sha256": self.normalized_text_sha256,
            "text": self.text,
            "source_expectation_class": self.source_expectation_class,
            "obligation_strength": self.obligation_strength,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class EonRequirementTagMap:
    tag_map_key: str
    inventory_key: str
    description_sha256: str
    section_sha256: str
    tag_map_sha256: str
    mappings: tuple[EonRequirementTagMapping, ...]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "tag_map_key": self.tag_map_key,
            "inventory_key": self.inventory_key,
            "description_sha256": self.description_sha256,
            "section_sha256": self.section_sha256,
            "tag_map_sha256": self.tag_map_sha256,
            "mappings": [mapping.canonical_payload() for mapping in self.mappings],
        }

    def unique_tags(self) -> tuple[str, ...]:
        return tuple(sorted({tag for mapping in self.mappings for tag in mapping.tags}))


_EXACT_SPECS: Final[tuple[_RequirementTagSpec, ...]] = (
    _RequirementTagSpec(
        statement_key="eon-req-0530ca76d323450e",
        text=(
            "Extensive professional experience in data engineering positions and a "
            "consulting background"
        ),
        tags=(
            "experience.data_engineering.professional",
            "experience.consulting",
        ),
    ),
    _RequirementTagSpec(
        statement_key="eon-req-83b2ec5dabefbc95",
        text="Hands-on experience in building end-to-end data solutions",
        tags=("capability.data_solution.end_to_end_delivery",),
    ),
    _RequirementTagSpec(
        statement_key="eon-req-c9b118500dadb8a5",
        text=(
            "Experience with software development best practices, including version "
            "control, continuous integration and continuous deployment (CI/CD), "
            "monitoring, automation and testing"
        ),
        tags=(
            "practice.software_development_best_practices",
            "practice.version_control",
            "practice.ci_cd",
            "practice.monitoring",
            "practice.automation",
            "practice.testing",
        ),
    ),
    _RequirementTagSpec(
        statement_key="eon-req-0d5675364368eb96",
        text=(
            "Expertise in Kubernetes, Airflow, Kafka, Containerization and Helm Charts"
        ),
        tags=(
            "technology.kubernetes",
            "technology.airflow",
            "technology.kafka",
            "technology.containerization",
            "technology.helm",
        ),
    ),
    _RequirementTagSpec(
        statement_key="eon-req-2713fa3b49a55b7e",
        text=(
            "Experience in Microsoft Azure, Infrastructure-as-a-Code as well as building "
            "secure cloud architecture"
        ),
        tags=(
            "cloud.microsoft_azure",
            "practice.infrastructure_as_code",
            "architecture.secure_cloud",
        ),
    ),
    _RequirementTagSpec(
        statement_key="eon-req-339148dc4c77c2fe",
        text=(
            "Experience with our technology stack which includes Azure Data Factory, "
            "Databricks, Terraform, Python, Spark"
        ),
        tags=(
            "technology.azure_data_factory",
            "technology.databricks",
            "technology.terraform",
            "technology.python",
            "technology.spark",
        ),
    ),
    _RequirementTagSpec(
        statement_key="eon-req-cf2a82167a40bdf9",
        text=(
            "Excellent communication skills engaging various stakeholders matching the "
            "audience"
        ),
        tags=(
            "capability.stakeholder_communication",
            "capability.audience_adaptation",
        ),
    ),
    _RequirementTagSpec(
        statement_key="eon-req-07ac7c640b8105d6",
        text="Fluent in English and German",
        tags=(
            "language.english.fluent",
            "language.german.fluent",
        ),
    ),
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _normalized_text_sha256(text: str) -> str:
    normalized = " ".join(text.split()).casefold()
    return sha256(normalized.encode("utf-8")).hexdigest()


def build_eon_requirement_tag_map(
    inventory: EonRequirementInventory,
) -> EonRequirementTagMap:
    _require(
        inventory.inventory_key == INVENTORY_KEY,
        "E.ON requirement inventory key mismatch",
    )
    _require(
        len(inventory.statements) == len(_EXACT_SPECS),
        "E.ON requirement tag map expects exactly eight statements",
    )

    mappings: list[EonRequirementTagMapping] = []
    for expected_order, (statement, spec) in enumerate(
        zip(inventory.statements, _EXACT_SPECS, strict=True),
        start=1,
    ):
        _require(
            statement.order == expected_order,
            "E.ON requirement statement order mismatch",
        )
        _require(
            statement.statement_key == spec.statement_key,
            "E.ON requirement statement key mismatch",
        )
        _require(
            statement.text == spec.text,
            "E.ON requirement statement text mismatch",
        )
        expected_text_sha256 = _normalized_text_sha256(spec.text)
        _require(
            statement.normalized_text_sha256 == expected_text_sha256,
            "E.ON requirement normalized text hash mismatch",
        )
        _require(bool(spec.tags), "E.ON requirement statement has no canonical tags")
        _require(
            len(spec.tags) == len(set(spec.tags)),
            "E.ON requirement statement contains duplicate canonical tags",
        )
        _require(
            all(_TAG_RE.fullmatch(tag) is not None for tag in spec.tags),
            "E.ON requirement statement contains an invalid canonical tag",
        )

        mappings.append(
            EonRequirementTagMapping(
                order=expected_order,
                statement_key=statement.statement_key,
                normalized_text_sha256=statement.normalized_text_sha256,
                text=statement.text,
                source_expectation_class=SOURCE_EXPECTATION_CLASS,
                obligation_strength=OBLIGATION_STRENGTH_UNSPECIFIED,
                tags=spec.tags,
            )
        )

    map_material = "\n".join(
        (
            f"{mapping.order}|{mapping.statement_key}|"
            f"{mapping.normalized_text_sha256}|"
            f"{mapping.source_expectation_class}|"
            f"{mapping.obligation_strength}|{','.join(mapping.tags)}"
        )
        for mapping in mappings
    )
    tag_map_sha256 = sha256(
        "\n".join(
            (
                TAG_MAP_KEY,
                inventory.inventory_key,
                inventory.description_sha256,
                inventory.section_sha256,
                map_material,
            )
        ).encode("utf-8")
    ).hexdigest()

    return EonRequirementTagMap(
        tag_map_key=TAG_MAP_KEY,
        inventory_key=inventory.inventory_key,
        description_sha256=inventory.description_sha256,
        section_sha256=inventory.section_sha256,
        tag_map_sha256=tag_map_sha256,
        mappings=tuple(mappings),
    )
