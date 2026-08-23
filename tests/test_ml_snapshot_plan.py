from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from src.search_intelligence.ml_snapshot_plan import (
    COLUMN_ROLE_FEATURE_CANDIDATE,
    DuplicateGroupingContract,
    LeakageBoundary,
    SnapshotColumn,
    build_training_snapshot_sql,
    default_training_snapshot_plan,
    feature_candidate_columns,
    fingerprint_training_snapshot_plan,
    provenance_columns,
    read_only_transaction_preamble,
    snapshot_column_names,
    validate_training_snapshot_plan,
)


def test_default_snapshot_plan_is_read_only_and_valid() -> None:
    plan = default_training_snapshot_plan()

    assert validate_training_snapshot_plan(plan) == []
    assert plan.source_relation == "silver_jobs"
    assert plan.read_only is True
    assert plan.leakage.labels_joined is False
    assert plan.leakage.future_outcomes_allowed is False
    assert plan.grouping.keep_group_together_across_splits is True


def test_snapshot_columns_are_explicit_and_match_current_silver_schema() -> None:
    plan = default_training_snapshot_plan()
    names = snapshot_column_names(plan)

    migration_text = (
        Path("db/migrations/003_silver_jobs_model.sql").read_text(encoding="utf-8")
        + "\n"
        + Path("db/migrations/014_extend_silver_jobs_for_canonicalization.sql").read_text(
            encoding="utf-8"
        )
    )

    assert names == (
        "id",
        "raw_job_id",
        "source_name",
        "external_job_id",
        "source_url",
        "title",
        "company_name",
        "city",
        "postal_code",
        "country",
        "publication_date",
        "normalized_title",
        "normalized_company_name",
        "normalized_location",
        "canonical_status",
        "canonical_source_type",
        "canonical_key_candidate",
        "normalized_at",
        "created_at",
        "updated_at",
    )
    for column_name in names:
        assert column_name in migration_text


def test_feature_candidates_are_separate_from_identity_and_provenance() -> None:
    plan = default_training_snapshot_plan()

    features = feature_candidate_columns(plan)
    provenance = provenance_columns(plan)

    assert features == (
        "title",
        "company_name",
        "city",
        "postal_code",
        "country",
        "publication_date",
        "normalized_title",
        "normalized_company_name",
        "normalized_location",
        "canonical_status",
    )
    assert "id" not in features
    assert "raw_job_id" not in features
    assert "external_job_id" not in features
    assert "source_url" not in features
    assert "canonical_key_candidate" not in features
    assert "canonical_key_candidate" in provenance


def test_snapshot_sql_is_deterministic_parameterized_and_read_only() -> None:
    plan = default_training_snapshot_plan()

    sql = build_training_snapshot_sql(plan)

    assert sql == (
        "SELECT\n"
        "    id,\n"
        "    raw_job_id,\n"
        "    source_name,\n"
        "    external_job_id,\n"
        "    source_url,\n"
        "    title,\n"
        "    company_name,\n"
        "    city,\n"
        "    postal_code,\n"
        "    country,\n"
        "    publication_date,\n"
        "    normalized_title,\n"
        "    normalized_company_name,\n"
        "    normalized_location,\n"
        "    canonical_status,\n"
        "    canonical_source_type,\n"
        "    canonical_key_candidate,\n"
        "    normalized_at,\n"
        "    created_at,\n"
        "    updated_at\n"
        "FROM silver_jobs\n"
        "WHERE normalized_at <= %(evidence_cutoff)s\n"
        "  AND created_at <= %(evidence_cutoff)s\n"
        "  AND updated_at <= %(evidence_cutoff)s\n"
        "ORDER BY id;"
    )
    lowered = f" {sql.lower()} "
    assert " insert " not in lowered
    assert " update " not in lowered
    assert " delete " not in lowered
    assert " copy " not in lowered
    assert sql.count("%(evidence_cutoff)s") == 3


def test_snapshot_transaction_preamble_is_repeatable_read_and_read_only() -> None:
    plan = default_training_snapshot_plan()

    assert read_only_transaction_preamble(plan) == (
        "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;"
    )


def test_duplicate_grouping_contract_prevents_naive_cross_split_leakage() -> None:
    plan = default_training_snapshot_plan()

    assert plan.grouping.primary_group_key == "canonical_key_candidate"
    assert plan.grouping.fallback_group_key == (
        "normalized_company_name",
        "normalized_title",
        "normalized_location",
    )
    assert plan.grouping.keep_group_together_across_splits is True
    assert plan.leakage.duplicate_groups_split_together is True


def test_mlf003_snapshot_has_no_outcome_or_operator_label_columns() -> None:
    names = snapshot_column_names(default_training_snapshot_plan())
    forbidden_outcome_markers = (
        "operator_interest",
        "application_decision",
        "applied",
        "interview",
        "offer",
        "rejected_after_application",
    )

    for marker in forbidden_outcome_markers:
        assert marker not in names


def test_snapshot_plan_fingerprint_is_stable_and_changes_with_contract() -> None:
    plan = default_training_snapshot_plan()

    first = fingerprint_training_snapshot_plan(plan)
    second = fingerprint_training_snapshot_plan(plan)
    changed = fingerprint_training_snapshot_plan(
        replace(plan, cutoff_parameter="training_cutoff")
    )

    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == len("sha256:") + 64
    assert changed != first


def test_snapshot_plan_rejects_non_silver_or_write_capable_boundaries() -> None:
    plan = default_training_snapshot_plan()
    invalid = replace(
        plan,
        source_relation="raw_jobs",
        read_only=False,
        leakage=LeakageBoundary(
            source_relation_only=False,
            labels_joined=True,
            future_outcomes_allowed=True,
            exclude_rows_changed_after_cutoff=False,
            duplicate_groups_split_together=False,
        ),
        grouping=DuplicateGroupingContract(keep_group_together_across_splits=False),
    )

    violations = validate_training_snapshot_plan(invalid)

    assert "source_relation must be the canonical Silver relation 'silver_jobs'." in violations
    assert "training snapshot planning must remain read-only." in violations
    assert "labels may not be joined in the MLF-003 evidence snapshot." in violations
    assert "future outcome fields are forbidden in the MLF-003 snapshot." in violations
    assert "rows changed after the evidence cutoff must be excluded." in violations
    assert "duplicate groups must stay together across dataset splits." in violations


def test_snapshot_plan_rejects_missing_grouping_and_unknown_column_role() -> None:
    plan = default_training_snapshot_plan()
    columns = tuple(
        column
        for column in plan.selected_columns
        if column.name != "canonical_key_candidate"
    ) + (SnapshotColumn("experimental_field", "unknown_role"),)
    invalid = replace(plan, selected_columns=columns)

    violations = validate_training_snapshot_plan(invalid)

    assert any("canonical_key_candidate" in violation for violation in violations)
    assert any("unsupported role" in violation for violation in violations)


def test_snapshot_plan_rejects_duplicate_column_names() -> None:
    plan = default_training_snapshot_plan()
    invalid = replace(
        plan,
        selected_columns=plan.selected_columns
        + (SnapshotColumn("title", COLUMN_ROLE_FEATURE_CANDIDATE),),
    )

    with pytest.raises(ValueError, match="selected snapshot column names must be unique"):
        build_training_snapshot_sql(invalid)
