from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.market003b_manual_observation_backfill import (
    DEFAULT_MANUAL_OBSERVATION_BACKFILL_SEEDS,
    build_market003b_report,
    market003b_safety_boundary,
    seeds_to_insert,
)


def test_market003b_default_inventory_contains_reconstructed_manual_companies() -> None:
    names = {seed.company_name for seed in DEFAULT_MANUAL_OBSERVATION_BACKFILL_SEEDS}

    assert len(names) >= 60
    assert "Bahlsen GmbH" in names
    assert "HDI Group" in names
    assert "Dataciders GmbH" in names
    assert "GETEC ENERGIE" in names
    assert "MEDIFOX DAN" in names
    assert "Sopra Steria" in names
    assert "QUNIS" in names
    assert "VALUE AG" in names


def test_market003b_default_inventory_has_no_duplicate_company_keys() -> None:
    keys = [normalize_company_key(seed.company_name) for seed in DEFAULT_MANUAL_OBSERVATION_BACKFILL_SEEDS]

    assert len(keys) == len(set(keys))


def test_market003b_report_skips_existing_and_legacy_covered_rows() -> None:
    existing = [
        {
            "id": 1753,
            "normalized_company_key": "bahlsen",
            "company_name": "Bahlsen GmbH",
            "title": "Analytics Engineer",
        }
    ]
    legacy = [
        {
            "id": 1,
            "normalized_company_key": "hdi",
            "company_name": "HDI Group",
            "title": "Data & Analytics Engineer",
            "evidence_kind": "manual_aggregator_sighting",
            "input_mode": "manual_market_evidence",
        },
        {
            "id": 2,
            "normalized_company_key": "hdi",
            "company_name": "HDI Group",
            "title": "Data & Analytics Engineer",
            "evidence_kind": "manual_aggregator_sighting",
            "input_mode": "manual_market_evidence",
        },
    ]

    report = build_market003b_report(
        seeds=DEFAULT_MANUAL_OBSERVATION_BACKFILL_SEEDS,
        existing_manual_rows=existing,
        legacy_rows=legacy,
    )
    by_key = {item.company_key: item for item in report.items}

    assert by_key["bahlsen"].action == "skip_existing_manual_market_observation"
    assert by_key["hdi"].action == "skip_covered_by_legacy_manual_evidence_migration"
    assert by_key["dataciders"].action == "insert_manual_market_observation"
    assert report.existing_skip_count == 1
    assert by_key["hdi"].legacy_market_evidence_ids == (1, 2)
    assert report.legacy_cover_skip_count == 1
    assert report.insert_planned_count == len(DEFAULT_MANUAL_OBSERVATION_BACKFILL_SEEDS) - 2
    assert report.legacy_rows_found == 2
    assert report.as_dict()["next_action"] == "review_market003b_backfill_report_then_rerun_with_write_if_expected"


def test_market003b_seeds_to_insert_excludes_existing_and_legacy_rows() -> None:
    plans = seeds_to_insert(
        DEFAULT_MANUAL_OBSERVATION_BACKFILL_SEEDS,
        existing_manual_rows=[{"id": 1753, "normalized_company_key": "bahlsen", "title": "Analytics Engineer"}],
        legacy_rows=[{"id": 1, "normalized_company_key": "hdi", "title": "Data & Analytics Engineer"}],
    )
    keys = {plan.company_key for plan in plans}

    assert "bahlsen" not in keys
    assert "hdi" not in keys
    assert "dataciders" in keys


def test_market003b_write_report_flags_partial_insert_conflicts() -> None:
    report = build_market003b_report(
        seeds=DEFAULT_MANUAL_OBSERVATION_BACKFILL_SEEDS[:2],
        existing_manual_rows=[],
        legacy_rows=[],
        write=True,
        written_ids_by_company_key={DEFAULT_MANUAL_OBSERVATION_BACKFILL_SEEDS[0].company_key: 99},
        migrated_legacy_ids=[],
    )

    assert report.insert_planned_count == 2
    assert report.inserted_count == 1
    assert report.as_dict()["next_action"] == "review_duplicates_or_conflicts_before_interpreting_manual_recall_coverage"


def test_market003b_safety_boundary_excludes_pipeline_mutation_and_csv_inputs() -> None:
    boundary = market003b_safety_boundary()

    assert boundary["work_item_market003b_backfill"] is True
    assert boundary["database_write_requires_explicit_write_flag"] is True
    assert boundary["database_write_scope_market_evidence_only"] is True
    assert boundary["legacy_manual_evidence_update_scope_market_evidence_only"] is True
    assert boundary["delete_or_destructive_cleanup"] is False
    assert boundary["csv_or_export_as_pipeline_input"] is False
    assert boundary["candidate_creation"] is False
    assert boundary["gate_decision"] is False
    assert boundary["connector_build_or_registration"] is False
