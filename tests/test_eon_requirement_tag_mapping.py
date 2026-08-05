from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from src.search_intelligence.eon_flat_requirement_segmentation import (
    EXACT_PROFILE_STATEMENTS,
)
from src.search_intelligence.eon_requirement_inventory import (
    build_eon_requirement_inventory,
)
from src.search_intelligence.eon_requirement_tag_mapping import (
    OBLIGATION_STRENGTH_UNSPECIFIED,
    SOURCE_EXPECTATION_CLASS,
    TAG_MAP_KEY,
    build_eon_requirement_tag_map,
)


TITLE = "(Senior) Data Engineer Data & AI (f/m/d)"
RUNNER = Path("scripts/run_eon_requirement_tag_mapping.py").read_text(
    encoding="utf-8"
)

EXPECTED_TAGS = (
    (
        "experience.data_engineering.professional",
        "experience.consulting",
    ),
    ("capability.data_solution.end_to_end_delivery",),
    (
        "practice.software_development_best_practices",
        "practice.version_control",
        "practice.ci_cd",
        "practice.monitoring",
        "practice.automation",
        "practice.testing",
    ),
    (
        "technology.kubernetes",
        "technology.airflow",
        "technology.kafka",
        "technology.containerization",
        "technology.helm",
    ),
    (
        "cloud.microsoft_azure",
        "practice.infrastructure_as_code",
        "architecture.secure_cloud",
    ),
    (
        "technology.azure_data_factory",
        "technology.databricks",
        "technology.terraform",
        "technology.python",
        "technology.spark",
    ),
    (
        "capability.stakeholder_communication",
        "capability.audience_adaptation",
    ),
    (
        "language.english.fluent",
        "language.german.fluent",
    ),
)


def _inventory():
    profile = "".join(f"<p>{statement}</p>" for statement in EXACT_PROFILE_STATEMENTS)
    description = f"<h2>Your Profile</h2>{profile}<h2>What we offer</h2>"
    return build_eon_requirement_inventory(description=description, title=TITLE)


def test_maps_all_exact_statements_to_canonical_tags() -> None:
    tag_map = build_eon_requirement_tag_map(_inventory())

    assert tag_map.tag_map_key == TAG_MAP_KEY
    assert len(tag_map.mappings) == 8
    assert [mapping.tags for mapping in tag_map.mappings] == list(EXPECTED_TAGS)
    assert len(tag_map.unique_tags()) == 26
    assert tag_map.unique_tags() == tuple(sorted(tag_map.unique_tags()))


def test_preserves_statement_provenance_and_unspecified_obligation() -> None:
    inventory = _inventory()
    tag_map = build_eon_requirement_tag_map(inventory)

    for source, mapping in zip(
        inventory.statements,
        tag_map.mappings,
        strict=True,
    ):
        assert mapping.order == source.order
        assert mapping.statement_key == source.statement_key
        assert mapping.normalized_text_sha256 == source.normalized_text_sha256
        assert mapping.text == source.text
        assert mapping.source_expectation_class == SOURCE_EXPECTATION_CLASS
        assert mapping.obligation_strength == OBLIGATION_STRENGTH_UNSPECIFIED


def test_tag_map_hash_is_deterministic_and_source_bound() -> None:
    inventory = _inventory()

    first = build_eon_requirement_tag_map(inventory)
    second = build_eon_requirement_tag_map(inventory)
    changed_source = build_eon_requirement_tag_map(
        replace(inventory, description_sha256="f" * 64)
    )

    assert first.tag_map_sha256 == second.tag_map_sha256
    assert first.tag_map_sha256 != changed_source.tag_map_sha256


def test_fails_closed_on_statement_key_drift() -> None:
    inventory = _inventory()
    changed = replace(
        inventory.statements[0],
        statement_key="eon-req-0000000000000000",
    )

    with pytest.raises(ValueError, match="statement key mismatch"):
        build_eon_requirement_tag_map(
            replace(inventory, statements=(changed, *inventory.statements[1:]))
        )


def test_fails_closed_on_statement_text_drift() -> None:
    inventory = _inventory()
    changed = replace(
        inventory.statements[1],
        text=inventory.statements[1].text + " with inferred ownership",
    )

    with pytest.raises(ValueError, match="statement text mismatch"):
        build_eon_requirement_tag_map(
            replace(
                inventory,
                statements=(
                    inventory.statements[0],
                    changed,
                    *inventory.statements[2:],
                ),
            )
        )


def test_fails_closed_on_normalized_text_hash_drift() -> None:
    inventory = _inventory()
    changed = replace(
        inventory.statements[2],
        normalized_text_sha256="0" * 64,
    )

    with pytest.raises(ValueError, match="normalized text hash mismatch"):
        build_eon_requirement_tag_map(
            replace(
                inventory,
                statements=(
                    *inventory.statements[:2],
                    changed,
                    *inventory.statements[3:],
                ),
            )
        )


def test_fails_closed_on_reordered_statements() -> None:
    inventory = _inventory()
    reordered = (
        inventory.statements[1],
        inventory.statements[0],
        *inventory.statements[2:],
    )

    with pytest.raises(ValueError, match="statement order mismatch"):
        build_eon_requirement_tag_map(replace(inventory, statements=reordered))


def test_fails_closed_on_additional_statement() -> None:
    inventory = _inventory()

    with pytest.raises(ValueError, match="exactly eight statements"):
        build_eon_requirement_tag_map(
            replace(
                inventory,
                statements=(*inventory.statements, inventory.statements[-1]),
            )
        )


def test_runner_is_exact_read_only_and_has_no_fit_authority() -> None:
    assert "load_exact_eon_binding" in RUNNER
    assert "build_inventory_from_binding" in RUNNER
    assert 'cur.execute("SET TRANSACTION READ ONLY")' in RUNNER
    assert '"database_writes": 0' in RUNNER
    assert '"candidate_fact_reads": 0' in RUNNER
    assert '"candidate_fact_writes": 0' in RUNNER
    assert '"capability_fit_decision_created": False' in RUNNER
    assert '"assessment_mutation": False' in RUNNER
    assert '"readiness_mutation": False' in RUNNER
    assert '"ranking_scores_created": False' in RUNNER
    assert "INSERT INTO" not in RUNNER
    assert "UPDATE job_product_assessments" not in RUNNER
    assert "candidate_facts" not in RUNNER
