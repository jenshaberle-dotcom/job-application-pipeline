from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.apply_db_migrations import (  # noqa: E402
    MigrationFile,
    apply_pending,
    checksum_mismatches,
    connect as migration_connect,
    discover_migration_files,
    load_tracked_migrations,
    pending_migrations,
    schema_migrations_exists,
)
from scripts.run_eon_controlled_pilot_ingestion import (  # noqa: E402
    PilotApplyResult,
    preflight_profile,
    run_apply,
    write_report,
)
from src.config import get_database_config  # noqa: E402
from src.ingestion.eon_controlled_pilot import (  # noqa: E402
    APPROVAL_TOKEN,
    EXPECTED_EXTERNAL_JOB_ID,
    PILOT_PROFILE_NAME,
    PILOT_SOURCE_NAME,
    PreviewApprovalEvidence,
    load_preview_approval_evidence,
)

REQUIRED_MIGRATIONS = (
    "084_create_eon_controlled_pilot_profile.sql",
    "085_create_validated_connector_autonomy_a1.sql",
)
EXECUTION_SCHEMA = "eon_private_runtime_execution.v1"
DEFAULT_REVIEWER = "connector_autonomy_a1"


@dataclass(frozen=True)
class RepositoryState:
    expected_sha: str
    head_sha: str
    clean_worktree: bool


@dataclass(frozen=True)
class MigrationState:
    table_exists: bool
    migration_file_count: int
    tracked_migration_count: int
    pending_names: tuple[str, ...]
    checksum_mismatch_names: tuple[str, ...]
    required_present: tuple[str, ...]
    required_tracked: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeVerification:
    raw_job_count: int
    raw_job_id: int
    silver_job_id: int
    canonical_source_type: str
    product_readiness_status: str
    profile_is_active: bool


def _run_git(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"git command failed: {' '.join(args)}") from exc
    return completed.stdout.strip()


def validate_expected_sha(value: str) -> str:
    normalized = value.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", normalized):
        raise ValueError("--expected-pipeline-sha must be an exact 40-character commit SHA")
    return normalized


def verify_repository_state(expected_sha: str) -> RepositoryState:
    normalized = validate_expected_sha(expected_sha)
    repo_root = Path(_run_git("rev-parse", "--show-toplevel")).resolve()
    if repo_root != ROOT.resolve():
        raise RuntimeError(f"unexpected repository root: {repo_root}")
    head_sha = _run_git("rev-parse", "HEAD").lower()
    if head_sha != normalized:
        raise RuntimeError(f"pipeline SHA mismatch: expected={normalized} actual={head_sha}")
    dirty = _run_git("status", "--porcelain", "--untracked-files=normal")
    if dirty:
        raise RuntimeError("private runtime worktree must be clean before pilot execution")
    return RepositoryState(
        expected_sha=normalized,
        head_sha=head_sha,
        clean_worktree=True,
    )


def _migration_state(
    migrations: list[MigrationFile],
    tracked: Mapping[str, object],
    *,
    table_exists: bool,
) -> MigrationState:
    mismatches = checksum_mismatches(migrations, tracked)
    pending = pending_migrations(migrations, tracked)
    available = {migration.filename for migration in migrations}
    tracked_names = set(tracked)
    return MigrationState(
        table_exists=table_exists,
        migration_file_count=len(migrations),
        tracked_migration_count=len(tracked),
        pending_names=tuple(migration.filename for migration in pending),
        checksum_mismatch_names=tuple(
            migration.filename for migration, _existing in mismatches
        ),
        required_present=tuple(name for name in REQUIRED_MIGRATIONS if name in available),
        required_tracked=tuple(name for name in REQUIRED_MIGRATIONS if name in tracked_names),
    )


def load_migration_state() -> tuple[list[MigrationFile], Mapping[str, object], MigrationState]:
    migrations = discover_migration_files()
    with migration_connect() as conn:
        table_exists = schema_migrations_exists(conn)
        tracked = load_tracked_migrations(conn)
    return migrations, tracked, _migration_state(
        migrations,
        tracked,
        table_exists=table_exists,
    )


def unexpected_pending_names(state: MigrationState) -> tuple[str, ...]:
    allowed = set(REQUIRED_MIGRATIONS)
    return tuple(name for name in state.pending_names if name not in allowed)


def validate_migration_state(state: MigrationState) -> None:
    if not state.table_exists:
        raise RuntimeError("schema_migrations tracking table is missing")
    missing_files = [name for name in REQUIRED_MIGRATIONS if name not in state.required_present]
    if missing_files:
        raise RuntimeError(f"required migration file(s) missing: {missing_files}")
    if state.checksum_mismatch_names:
        raise RuntimeError(
            f"migration checksum mismatch: {list(state.checksum_mismatch_names)}"
        )
    unexpected = unexpected_pending_names(state)
    if unexpected:
        raise RuntimeError(
            "unexpected pending migrations outside the E.ON execution slice: "
            f"{list(unexpected)}"
        )


def apply_required_migrations(*, applied_by: str) -> MigrationState:
    migrations, tracked, before = load_migration_state()
    validate_migration_state(before)
    if before.pending_names:
        apply_pending(
            migrations=migrations,
            tracked=tracked,
            applied_by=applied_by,
        )
    _migrations, _tracked, after = load_migration_state()
    validate_migration_state(after)
    still_pending = [name for name in REQUIRED_MIGRATIONS if name in after.pending_names]
    if still_pending:
        raise RuntimeError(f"required migration(s) remain pending: {still_pending}")
    return after


def run_dry_run_report(
    *,
    evidence: PreviewApprovalEvidence,
    reviewed_by: str,
    output_dir: Path,
) -> tuple[object, Path]:
    binding = preflight_profile()
    report_path = write_report(
        output_dir=output_dir,
        evidence=evidence,
        binding=binding,
        reviewed_by=reviewed_by,
        apply_result=None,
    )
    return binding, report_path


def verify_runtime_result(result: PilotApplyResult) -> RuntimeVerification:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) OVER () AS raw_job_count,
                    r.id AS raw_job_id,
                    s.id AS silver_job_id,
                    s.canonical_source_type,
                    g.product_readiness_status,
                    sp.is_active AS profile_is_active
                FROM raw_jobs r
                JOIN silver_jobs s
                  ON s.raw_job_id = r.id
                JOIN gold_product_v1_job_readiness g
                  ON g.silver_job_id = s.id
                JOIN search_profiles sp
                  ON sp.id = r.search_profile_id
                WHERE r.source_name = %s
                  AND r.external_job_id = %s
                """,
                (PILOT_SOURCE_NAME, EXPECTED_EXTERNAL_JOB_ID),
            )
            rows = cur.fetchall()
        conn.rollback()

    if len(rows) != 1:
        raise RuntimeError(
            "expected exactly one E.ON raw/Silver/readiness row, "
            f"found {len(rows)}"
        )
    row = rows[0]
    verification = RuntimeVerification(
        raw_job_count=int(row["raw_job_count"]),
        raw_job_id=int(row["raw_job_id"]),
        silver_job_id=int(row["silver_job_id"]),
        canonical_source_type=str(row["canonical_source_type"]),
        product_readiness_status=str(row["product_readiness_status"]),
        profile_is_active=bool(row["profile_is_active"]),
    )
    if verification.raw_job_count != 1:
        raise RuntimeError("E.ON pilot raw job is not unique")
    if verification.raw_job_id != result.raw_job_id:
        raise RuntimeError("verified raw job id differs from pilot result")
    if verification.silver_job_id != result.silver_job_id:
        raise RuntimeError("verified Silver job id differs from pilot result")
    if verification.canonical_source_type != "employer_origin_ats_backed_career_site":
        raise RuntimeError("unexpected E.ON canonical source type")
    if verification.profile_is_active:
        raise RuntimeError(f"pilot profile became active: {PILOT_PROFILE_NAME}")
    if verification.product_readiness_status != result.product_readiness_status:
        raise RuntimeError("verified Product-V1 readiness differs from pilot result")
    return verification


def write_execution_report(
    *,
    output_dir: Path,
    repository: RepositoryState,
    artifact: PreviewApprovalEvidence,
    migrations_before: MigrationState,
    migrations_after: MigrationState | None,
    reviewed_by: str,
    apply_requested: bool,
    dry_run_report: Path | None,
    apply_report: Path | None,
    apply_result: PilotApplyResult | None,
    verification: RuntimeVerification | None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"eon_private_runtime_execution_{stamp}.json"
    payload = {
        "schema_version": EXECUTION_SCHEMA,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "mode": "apply" if apply_requested else "plan_only",
        "reviewed_by": reviewed_by,
        "repository": asdict(repository),
        "preview_approval_evidence": asdict(artifact),
        "migrations_before": asdict(migrations_before),
        "migrations_after": asdict(migrations_after) if migrations_after else None,
        "dry_run_report": str(dry_run_report) if dry_run_report else None,
        "apply_report": str(apply_report) if apply_report else None,
        "apply_result": asdict(apply_result) if apply_result else None,
        "verification": asdict(verification) if verification else None,
        "review_output_only_not_pipeline_input": True,
        "boundary": {
            "plan_only_network_requests": 0,
            "plan_only_database_mutation": False,
            "apply_max_records": 1,
            "apply_max_http_requests": 2,
            "provider_requests": 0,
            "scheduler_changed": False,
            "recurring_ingestion_enabled": False,
            "pilot_profile_activated": False,
            "assessment_inserted": False,
            "score_invented": False,
            "top_jobs_forced": False,
            "application_action_performed": False,
            "bronze_silver_atomic_transaction": True,
        },
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the SHA-bound private E.ON migration, dry-run, apply and "
            "post-apply verification sequence."
        )
    )
    parser.add_argument("--expected-pipeline-sha", required=True)
    parser.add_argument("--preview-artifact", type=Path, required=True)
    parser.add_argument("--reviewed-by", default=DEFAULT_REVIEWER)
    parser.add_argument("--applied-by", default=DEFAULT_REVIEWER)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    reviewed_by = args.reviewed_by.strip()
    applied_by = args.applied_by.strip()
    if not reviewed_by:
        raise SystemExit("--reviewed-by must not be blank")
    if not applied_by:
        raise SystemExit("--applied-by must not be blank")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit(f"--apply requires --approval-token {APPROVAL_TOKEN}")
    if not args.apply and args.approval_token:
        raise SystemExit("--approval-token is accepted only together with --apply")

    try:
        repository = verify_repository_state(args.expected_pipeline_sha)
        evidence = load_preview_approval_evidence(args.preview_artifact)
        _migrations, _tracked, migrations_before = load_migration_state()
        validate_migration_state(migrations_before)

        migrations_after: MigrationState | None = None
        dry_run_report: Path | None = None
        apply_report: Path | None = None
        apply_result: PilotApplyResult | None = None
        verification: RuntimeVerification | None = None

        if args.apply:
            migrations_after = apply_required_migrations(applied_by=applied_by)
            binding, dry_run_report = run_dry_run_report(
                evidence=evidence,
                reviewed_by=reviewed_by,
                output_dir=args.output_dir,
            )
            apply_result = run_apply(
                evidence=evidence,
                binding=binding,
                reviewed_by=reviewed_by,
                approval_token=args.approval_token,
            )
            apply_report = write_report(
                output_dir=args.output_dir,
                evidence=evidence,
                binding=binding,
                reviewed_by=reviewed_by,
                apply_result=apply_result,
            )
            verification = verify_runtime_result(apply_result)

        execution_report = write_execution_report(
            output_dir=args.output_dir,
            repository=repository,
            artifact=evidence,
            migrations_before=migrations_before,
            migrations_after=migrations_after,
            reviewed_by=reviewed_by,
            apply_requested=args.apply,
            dry_run_report=dry_run_report,
            apply_report=apply_report,
            apply_result=apply_result,
            verification=verification,
        )
    except (OSError, ValueError, RuntimeError, psycopg.Error) as exc:
        raise SystemExit(str(exc)) from exc

    print("E.ON private runtime execution")
    print(f"mode: {'apply' if args.apply else 'plan_only'}")
    print(f"pipeline_sha: {repository.head_sha}")
    print(f"preview_artifact_sha256: {evidence.artifact_sha256}")
    print(f"pending_migrations_before: {len(migrations_before.pending_names)}")
    if migrations_after is not None:
        print(f"pending_migrations_after: {len(migrations_after.pending_names)}")
    if apply_result is not None:
        print(f"raw_job_id: {apply_result.raw_job_id}")
        print(f"silver_job_id: {apply_result.silver_job_id}")
        print(f"product_readiness_status: {apply_result.product_readiness_status}")
        if apply_result.product_readiness_status == "assessment_required":
            print("STOP: assessment_required; no assessment or score was created.")
    else:
        print("network_requests: 0")
        print("database_mutation: false")
    print(f"execution_report: {execution_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
