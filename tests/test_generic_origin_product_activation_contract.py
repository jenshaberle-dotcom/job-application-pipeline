from pathlib import Path


MIGRATION = Path(
    "db/migrations/107_create_generic_employer_origin_active_sources.sql"
)
ACTIVATION = Path("scripts/apply_generic_employer_origin_activation.py")
CONNECTOR = Path("src/connectors/generic_employer_origin.py")
QUALIFIER = Path("scripts/qualify_generic_employer_origin_connectors.py")
WORKFLOW = Path(".github/workflows/p1-generic-origin-product-activate.yml")


def test_generic_active_source_projection_accepts_only_canonical_pass_state() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "generic_employer_origin_active_sources" in sql
    assert "generic_evidence_driven_layer_model" in sql
    assert "origin_url TEXT NOT NULL" in sql
    assert "CHECK (proof_state = 'pass')" in sql
    assert "source_name = 'generic_origin:' || company_key" in sql
    assert "employer_origin_candidate_gate_reviews" not in sql


def test_activation_uses_proof_projection_and_nonsemantic_wildcard_trigger() -> None:
    source = ACTIVATION.read_text(encoding="utf-8")

    assert 'GENERIC_AUTHORITY = "generic_evidence_driven_layer_model"' in source
    assert 'NEUTRAL_TRIGGER_TERM = "*"' in source
    assert "generic_employer_origin_active_sources" in source
    assert "origin_url" in source
    assert "provider_free_origin_discovery" in source
    assert "_shape_to_https_url" in source
    assert "connector_validation_gate" not in source
    assert "final_approval_gate" not in source


def test_activation_retires_stale_generic_profiles_before_canonical_reprojection() -> None:
    source = ACTIVATION.read_text(encoding="utf-8")

    retire = source.index("WHERE source_name LIKE %s")
    canonical_profile = source.index('profile_name = f"{PROFILE_PREFIX}{company_key}"')
    canonical_upsert = source.index("INSERT INTO search_profiles", canonical_profile)

    assert retire < canonical_profile < canonical_upsert
    assert source.count("WHERE source_name LIKE %s") >= 2
    assert "recurring_ingestion_enabled = FALSE" in source[:canonical_profile]


def test_product_connector_prefers_materialized_proof_source_identity() -> None:
    source = CONNECTOR.read_text(encoding="utf-8")

    assert 'ACTIVE_SOURCE_RELATION = "generic_employer_origin_active_sources"' in source
    assert "active.candidate_id AS id" in source
    assert "active.origin_url AS candidate_url" in source
    assert "JOIN employer_origin_source_candidates AS candidate" in source


def test_preactivation_discovered_origin_is_not_misclassified_as_connector_failure() -> None:
    source = QUALIFIER.read_text(encoding="utf-8")

    assert "PREACTIVATION_MATERIALIZATION_PENDING" in source
    assert "proof_discovered_origin_not_yet_projected" in source
    assert "GENERIC_PREACTIVATION_MATERIALIZATION_PENDING" in source


def test_main_activation_is_automatic_not_a_demo_or_manual_effect_path() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "push:" in workflow
    assert "branches: [main]" in workflow
    assert "workflow_dispatch" not in workflow
    assert "demo" not in workflow.casefold()
    assert "scripts.run_generic_employer_origin_product" in workflow
    assert "scripts.qualify_generic_employer_origin_connectors" in workflow
    assert "scripts.apply_generic_employer_origin_activation" in workflow
    assert "--source generic_origin" in workflow
