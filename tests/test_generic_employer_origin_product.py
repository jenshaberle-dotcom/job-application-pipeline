from __future__ import annotations

from pathlib import Path

from src.search_intelligence.deterministic_connector_builder import (
    ConnectorBuilderAssessment,
    LayerState,
    passed,
    skipped,
)
from scripts.run_generic_employer_origin_product import proof_passed


def test_product_entrypoint_does_not_import_versioned_or_demo_truth() -> None:
    source = Path("scripts/run_generic_employer_origin_product.py").read_text(encoding="utf-8")
    forbidden = (
        "run_deterministic_connector_builder_layer_audit_v2",
        "run_deterministic_connector_builder_layer_audit_v3",
        "run_deterministic_connector_builder_layer_audit_v4",
        "run_deterministic_connector_builder_layer_audit_v5",
        "run_deterministic_connector_builder_layer_audit_v6",
        "run_demo_",
        "demo_strict_proven",
    )
    assert not any(item in source for item in forbidden)


def test_proof_pass_is_the_source_validity_gate() -> None:
    assessment = ConnectorBuilderAssessment(
        1,
        "example",
        "Example GmbH",
        (
            passed("identity", "ok"),
            passed("origin", "ok"),
            passed("origin_reachability", "ok"),
            skipped("delegation", "not required"),
            skipped("provider", "not required"),
            passed("inventory", "ok"),
            passed("detail", "ok"),
            passed("proof", "genuine job found"),
            passed("recipe", "generic recipe ready"),
        ),
    )
    assert assessment.layers[7].state == LayerState.PASS
    assert proof_passed(assessment) is True
