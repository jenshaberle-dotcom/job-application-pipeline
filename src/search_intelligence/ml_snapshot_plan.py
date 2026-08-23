from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Final


SNAPSHOT_PLAN_SCHEMA_VERSION: Final[str] = "ml-training-snapshot-plan/v1"
SNAPSHOT_SOURCE_RELATION: Final[str] = "silver_jobs"
SNAPSHOT_ISOLATION_LEVEL: Final[str] = "REPEATABLE READ"
SNAPSHOT_CUTOFF_PARAMETER: Final[str] = "evidence_cutoff"

COLUMN_ROLE_IDENTITY: Final[str] = "identity"
COLUMN_ROLE_PROVENANCE: Final[str] = "provenance"
COLUMN_ROLE_FEATURE_CANDIDATE: Final[str] = "feature_candidate"
COLUMN_ROLE_GROUPING_ONLY: Final[str] = "grouping_only"
COLUMN_ROLE_TIME_BOUNDARY: Final[str] = "time_boundary"
COLUMN_ROLES: Final[frozenset[str]] = frozenset(
    {
        COLUMN_ROLE_IDENTITY,
        COLUMN_ROLE_PROVENANCE,
        COLUMN_ROLE_FEATURE_CANDIDATE,
        COLUMN_ROLE_GROUPING_ONLY,
        COLUMN_ROLE_TIME_BOUNDARY,
    }
)


@dataclass(frozen=True)
class SnapshotColumn:
    name: str
    role: str


SILVER_SNAPSHOT_COLUMNS: Final[tuple[SnapshotColumn, ...]] = (
    SnapshotColumn("id", COLUMN_ROLE_IDENTITY),
    SnapshotColumn("raw_job_id", COLUMN_ROLE_IDENTITY),
    SnapshotColumn("source_name", COLUMN_ROLE_PROVENANCE),
    SnapshotColumn("external_job_id", COLUMN_ROLE_PROVENANCE),
    SnapshotColumn("source_url", COLUMN_ROLE_PROVENANCE),
    SnapshotColumn("title", COLUMN_ROLE_FEATURE_CANDIDATE),
    SnapshotColumn("company_name", COLUMN_ROLE_FEATURE_CANDIDATE),
    SnapshotColumn("city", COLUMN_ROLE_FEATURE_CANDIDATE),
    SnapshotColumn("postal_code", COLUMN_ROLE_FEATURE_CANDIDATE),
    SnapshotColumn("country", COLUMN_ROLE_FEATURE_CANDIDATE),
    SnapshotColumn("publication_date", COLUMN_ROLE_FEATURE_CANDIDATE),
    SnapshotColumn("normalized_title", COLUMN_ROLE_FEATURE_CANDIDATE),
    SnapshotColumn("normalized_company_name", COLUMN_ROLE_FEATURE_CANDIDATE),
    SnapshotColumn("normalized_location", COLUMN_ROLE_FEATURE_CANDIDATE),
    SnapshotColumn("canonical_status", COLUMN_ROLE_FEATURE_CANDIDATE),
    SnapshotColumn("canonical_source_type", COLUMN_ROLE_PROVENANCE),
    SnapshotColumn("canonical_key_candidate", COLUMN_ROLE_GROUPING_ONLY),
    SnapshotColumn("normalized_at", COLUMN_ROLE_TIME_BOUNDARY),
    SnapshotColumn("created_at", COLUMN_ROLE_TIME_BOUNDARY),
    SnapshotColumn("updated_at", COLUMN_ROLE_TIME_BOUNDARY),
)


@dataclass(frozen=True)
class DuplicateGroupingContract:
    primary_group_key: str = "canonical_key_candidate"
    fallback_group_key: tuple[str, ...] = (
        "normalized_company_name",
        "normalized_title",
        "normalized_location",
    )
    keep_group_together_across_splits: bool = True


@dataclass(frozen=True)
class LeakageBoundary:
    source_relation_only: bool = True
    labels_joined: bool = False
    future_outcomes_allowed: bool = False
    exclude_rows_changed_after_cutoff: bool = True
    duplicate_groups_split_together: bool = True


@dataclass(frozen=True)
class TrainingSnapshotPlan:
    selected_columns: tuple[SnapshotColumn, ...] = SILVER_SNAPSHOT_COLUMNS
    source_relation: str = SNAPSHOT_SOURCE_RELATION
    primary_key: str = "id"
    cutoff_parameter: str = SNAPSHOT_CUTOFF_PARAMETER
    isolation_level: str = SNAPSHOT_ISOLATION_LEVEL
    read_only: bool = True
    grouping: DuplicateGroupingContract = DuplicateGroupingContract()
    leakage: LeakageBoundary = LeakageBoundary()
    schema_version: str = SNAPSHOT_PLAN_SCHEMA_VERSION


_FORBIDDEN_SQL_TOKENS: Final[tuple[str, ...]] = (
    " insert ",
    " update ",
    " delete ",
    " alter ",
    " drop ",
    " create ",
    " truncate ",
    " merge ",
    " call ",
    " copy ",
)


def default_training_snapshot_plan() -> TrainingSnapshotPlan:
    return TrainingSnapshotPlan()


def snapshot_column_names(plan: TrainingSnapshotPlan) -> tuple[str, ...]:
    return tuple(column.name for column in plan.selected_columns)


def feature_candidate_columns(plan: TrainingSnapshotPlan) -> tuple[str, ...]:
    return tuple(
        column.name
        for column in plan.selected_columns
        if column.role == COLUMN_ROLE_FEATURE_CANDIDATE
    )


def provenance_columns(plan: TrainingSnapshotPlan) -> tuple[str, ...]:
    return tuple(
        column.name
        for column in plan.selected_columns
        if column.role
        in {
            COLUMN_ROLE_IDENTITY,
            COLUMN_ROLE_PROVENANCE,
            COLUMN_ROLE_GROUPING_ONLY,
            COLUMN_ROLE_TIME_BOUNDARY,
        }
    )


def validate_training_snapshot_plan(plan: TrainingSnapshotPlan) -> list[str]:
    violations: list[str] = []

    if plan.schema_version != SNAPSHOT_PLAN_SCHEMA_VERSION:
        violations.append(
            "schema_version must be "
            f"{SNAPSHOT_PLAN_SCHEMA_VERSION!r}; got {plan.schema_version!r}."
        )
    if plan.source_relation != SNAPSHOT_SOURCE_RELATION:
        violations.append(
            "source_relation must be the canonical Silver relation "
            f"{SNAPSHOT_SOURCE_RELATION!r}."
        )
    if plan.isolation_level != SNAPSHOT_ISOLATION_LEVEL:
        violations.append(
            f"isolation_level must be {SNAPSHOT_ISOLATION_LEVEL!r}."
        )
    if not plan.read_only:
        violations.append("training snapshot planning must remain read-only.")

    names = snapshot_column_names(plan)
    if len(names) != len(set(names)):
        violations.append("selected snapshot column names must be unique.")
    if not names:
        violations.append("selected snapshot columns must not be empty.")

    for column in plan.selected_columns:
        if not column.name.strip():
            violations.append("snapshot column names must be non-empty.")
        if column.role not in COLUMN_ROLES:
            violations.append(
                f"snapshot column {column.name!r} has unsupported role {column.role!r}."
            )

    required_columns = {
        plan.primary_key,
        plan.grouping.primary_group_key,
        *plan.grouping.fallback_group_key,
        "normalized_at",
        "created_at",
        "updated_at",
    }
    missing_required = sorted(required_columns - set(names))
    if missing_required:
        violations.append(
            f"snapshot plan is missing required columns {missing_required}."
        )

    if not plan.grouping.keep_group_together_across_splits:
        violations.append("duplicate groups must stay together across dataset splits.")
    if not plan.leakage.source_relation_only:
        violations.append("MLF-003 snapshot planning must use one canonical source relation.")
    if plan.leakage.labels_joined:
        violations.append("labels may not be joined in the MLF-003 evidence snapshot.")
    if plan.leakage.future_outcomes_allowed:
        violations.append("future outcome fields are forbidden in the MLF-003 snapshot.")
    if not plan.leakage.exclude_rows_changed_after_cutoff:
        violations.append("rows changed after the evidence cutoff must be excluded.")
    if not plan.leakage.duplicate_groups_split_together:
        violations.append("leakage boundary must keep duplicate groups together.")

    if not plan.cutoff_parameter.strip():
        violations.append("cutoff_parameter must be non-empty.")

    return violations


def build_training_snapshot_sql(plan: TrainingSnapshotPlan) -> str:
    violations = validate_training_snapshot_plan(plan)
    if violations:
        raise ValueError("; ".join(violations))

    selected = ",\n    ".join(snapshot_column_names(plan))
    cutoff = f"%({plan.cutoff_parameter})s"
    sql = (
        "SELECT\n"
        f"    {selected}\n"
        f"FROM {plan.source_relation}\n"
        f"WHERE normalized_at <= {cutoff}\n"
        f"  AND created_at <= {cutoff}\n"
        f"  AND updated_at <= {cutoff}\n"
        f"ORDER BY {plan.primary_key};"
    )

    normalized = f" {sql.lower().replace(chr(10), ' ')} "
    forbidden = [token.strip() for token in _FORBIDDEN_SQL_TOKENS if token in normalized]
    if forbidden:
        raise ValueError(f"Snapshot SQL contains forbidden write-capable tokens: {forbidden}.")
    return sql


def read_only_transaction_preamble(plan: TrainingSnapshotPlan) -> str:
    violations = validate_training_snapshot_plan(plan)
    if violations:
        raise ValueError("; ".join(violations))
    return (
        "BEGIN TRANSACTION ISOLATION LEVEL "
        f"{plan.isolation_level} READ ONLY;"
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def fingerprint_training_snapshot_plan(plan: TrainingSnapshotPlan) -> str:
    violations = validate_training_snapshot_plan(plan)
    if violations:
        raise ValueError("; ".join(violations))
    payload = _canonical_json(asdict(plan)).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"
