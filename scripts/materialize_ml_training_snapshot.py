"""Materialize and CPU-validate one read-only Silver ML evidence package.

The command is deliberately local-only. It reads PostgreSQL through an explicit
REPEATABLE READ / READ ONLY transaction, writes derived artifacts below the
ignored .runtime tree by default, and never invokes Kaggle or another provider.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Final

import psycopg
from psycopg.rows import dict_row

from src.config import PROJECT_ROOT, get_database_config
from src.search_intelligence.ml_experiment_transport import (
    fingerprint_training_package_manifest,
)
from src.search_intelligence.ml_snapshot_materializer import (
    SnapshotMaterializationSpec,
    materialize_training_package_from_database,
    write_materialized_training_package,
)
from src.search_intelligence.ml_snapshot_plan import (
    SNAPSHOT_PLAN_SCHEMA_VERSION,
    default_training_snapshot_plan,
    fingerprint_training_snapshot_plan,
)


DEFAULT_OUTPUT_ROOT: Final[Path] = PROJECT_ROOT / ".runtime" / "ml-training-packages"
PRODUCT_CONTRACT_PATH: Final[Path] = (
    PROJECT_ROOT / "docs" / "reference" / "product-contract" / "PRD.md"
)


def _parse_utc_cutoff(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("evidence cutoff must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("evidence cutoff must include a timezone")
    return parsed.astimezone(UTC)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _verified_code_commit() -> str:
    toplevel = Path(_run_git("rev-parse", "--show-toplevel")).resolve()
    if toplevel != PROJECT_ROOT.resolve():
        raise RuntimeError("git worktree does not resolve to the canonical project root")
    dirty = _run_git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError(
            "tracked worktree changes are present; commit them before materialization"
        )
    return _run_git("rev-parse", "HEAD")


def _feature_contract_version() -> str:
    plan = default_training_snapshot_plan()
    fingerprint = fingerprint_training_snapshot_plan(plan)
    return f"{SNAPSHOT_PLAN_SCHEMA_VERSION}:{fingerprint}"


def _product_contract_version() -> str:
    if not PRODUCT_CONTRACT_PATH.is_file():
        raise RuntimeError(f"product contract is unavailable: {PRODUCT_CONTRACT_PATH}")
    return f"prd:sha256:{_sha256_file(PRODUCT_CONTRACT_PATH)}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize one local read-only Silver ML evidence package."
    )
    parser.add_argument(
        "--evidence-cutoff",
        required=True,
        type=_parse_utc_cutoff,
        help="Timezone-aware ISO-8601 cutoff, for example 2026-08-23T16:00:00Z.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Local derived-artifact root; defaults below ignored .runtime/.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    plan = default_training_snapshot_plan()
    spec = SnapshotMaterializationSpec(
        feature_contract_version=_feature_contract_version(),
        product_contract_version=_product_contract_version(),
        code_commit=_verified_code_commit(),
    )

    database_config = get_database_config()
    existing_options = str(database_config.get("options") or "").strip()
    read_only_option = "-c default_transaction_read_only=on"
    database_config["options"] = " ".join(
        value for value in (existing_options, read_only_option) if value
    )
    database_config.setdefault("application_name", "mlf005_snapshot_materializer")

    with psycopg.connect(
        **database_config,
        row_factory=dict_row,
        autocommit=True,
    ) as connection:
        package = materialize_training_package_from_database(
            connection,
            evidence_cutoff=args.evidence_cutoff,
            spec=spec,
            plan=plan,
        )

    target = write_materialized_training_package(
        package,
        output_root=args.output_root,
    )
    summary = {
        "schema_version": "mlf005-local-materialization-receipt/v1",
        "package_id": package.package_manifest.package_id,
        "package_fingerprint": fingerprint_training_package_manifest(
            package.package_manifest
        ),
        "source_snapshot": package.package_manifest.source_snapshot,
        "dataset_manifest_fingerprint": (
            package.package_manifest.dataset_manifest_fingerprint
        ),
        "snapshot_plan_fingerprint": package.package_manifest.snapshot_plan_fingerprint,
        "row_count": package.snapshot_metadata["row_count"],
        "evidence_cutoff_utc": package.snapshot_metadata["evidence_cutoff_utc"],
        "compute_class": package.cpu_validation.compute_class,
        "external_execution": package.cpu_validation.external_execution,
        "product_authority": package.cpu_validation.product_authority,
        "output_directory": str(target),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
