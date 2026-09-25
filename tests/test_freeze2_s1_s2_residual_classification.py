from __future__ import annotations

import pytest

from scripts.run_freeze2_s1_s2_residual_classification import build_report


def _layer() -> dict[str, object]:
    def row(key: str, failure: str | None, provider: str = "") -> dict[str, object]:
        layers = []
        for name in (
            "identity",
            "origin",
            "origin_reachability",
            "delegation",
            "provider",
            "inventory",
            "detail",
            "proof",
            "recipe",
        ):
            evidence = {"provider": provider} if name == "provider" and provider else {}
            layers.append({"layer": name, "evidence": evidence})
        return {
            "candidate_id": len(key),
            "company_key": key,
            "company_name": key.title(),
            "recipe_ready": failure is None,
            "first_failure_layer": failure,
            "first_failure_reason": (
                None if failure is None else f"{failure} reusable residual"
            ),
            "layers": layers,
        }

    return {
        "boundary": {
            "database_writes": False,
            "candidate_url_writes": False,
            "connector_materialization": False,
            "connector_registration": False,
            "source_activation": False,
            "bronze_write": False,
            "silver_write": False,
            "product_write": False,
        },
        "results": [
            row("ready", None),
            row("origin_a", "origin"),
            row("detail_a", "detail", "successfactors"),
            row("proof_a", "proof", "bite"),
        ],
    }


def _product() -> dict[str, object]:
    return {
        "boundary": {
            "database_writes": False,
            "connector_registration": False,
            "source_activation": False,
            "bronze_write": False,
        },
        "summary": {
            "candidate_count": 4,
            "proof_pass_count": 2,
        },
        "proof_pass_company_keys": ["ready", "proof_a"],
    }


def _origin() -> dict[str, object]:
    return {
        "boundary": {
            "database_writes": False,
            "connector_materialization": 0,
        },
        "summary": {
            "origin_failure_count": 1,
            "classification_counts": {"domain_family_monoculture": 1},
        },
        "results": [{"company_key": "origin_a"}],
    }


def _inventory() -> dict[str, object]:
    return {
        "boundary": {
            "database_writes": 0,
            "connector_materialization": 0,
        },
        "summary": {
            "inventory_failure_count": 0,
            "primary_classification_counts": {},
        },
        "results": [],
    }


def _bridge() -> dict[str, object]:
    return {
        "boundary": {
            "database_writes": 0,
            "connector_materialization": 0,
            "query_values_persisted": 0,
        },
        "summary": {"bridge_case_count": 0, "hypothesis_counts": {}},
        "results": [],
    }


def _detail() -> dict[str, object]:
    return {
        "boundary": {
            "database_writes": 0,
            "connector_materialization": 0,
            "query_values_persisted": 0,
        },
        "summary": {
            "detail_failure_count": 1,
            "classification_counts": {"client_rendered_route_surface": 1},
        },
        "results": [{"company_key": "detail_a"}],
    }


def test_build_report_separates_v6_residuals_from_canonical_product_proof() -> None:
    report = build_report(
        layer=_layer(),
        product=_product(),
        origin=_origin(),
        inventory=_inventory(),
        bridge=_bridge(),
        detail=_detail(),
    )

    assert report["mode"] == "read_only"
    assert report["current_generic_product"]["proof_pass_count"] == 2
    assert report["residual_cohorts"]["origin"]["count"] == 1
    assert report["residual_cohorts"]["detail"]["provider_hint_counts"] == {
        "successfactors": 1
    }

    remaining = report["remaining_after_canonical_generic_product_proof"]
    assert remaining == {
        "detail": ["detail_a"],
        "origin": ["origin_a"],
    }


def test_build_report_keeps_named_company_out_of_selection_authority() -> None:
    report = build_report(
        layer=_layer(),
        product=_product(),
        origin=_origin(),
        inventory=_inventory(),
        bridge=_bridge(),
        detail=_detail(),
    )

    assert "population lift" in report["selection_rule"]
    assert "named-employer convenience" in report["selection_rule"]
    assert report["authority"]["connector_materialization"] is False
    assert report["authority"]["source_activation"] is False


def test_build_report_fails_closed_on_mutating_child_boundary() -> None:
    layer = _layer()
    layer["boundary"]["database_writes"] = True

    with pytest.raises(RuntimeError, match="read-only boundary violation"):
        build_report(
            layer=layer,
            product=_product(),
            origin=_origin(),
            inventory=_inventory(),
            bridge=_bridge(),
            detail=_detail(),
        )
