from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import zipfile

SCHEMA_VERSION = "preflight.context_support.v1"
READ_ONLY_PREFIXES = ("select", "with", "show", "explain")
FORBIDDEN_SQL_TOKENS = (
    "insert ",
    "update ",
    "delete ",
    "drop ",
    "alter ",
    "truncate ",
    "create ",
    "grant ",
    "revoke ",
    "copy ",
)


@dataclass(frozen=True)
class ContextBundleResult:
    zip_path: Path
    manifest_path: Path
    included: tuple[str, ...]
    missing: tuple[str, ...]
    skipped_outside_repo: tuple[str, ...]


def create_context_bundle(
    *,
    repo_root: Path,
    output_dir: Path,
    include_paths: Iterable[Path],
    zip_name: str = "preflight_context_bundle.zip",
    manifest_name: str = "preflight_context_bundle_manifest.json",
    purpose: str = "patch_context_only_not_pipeline_input",
) -> ContextBundleResult:
    """Create a repo-relative context ZIP from absolute or relative paths.

    This helper intentionally resolves relative paths under ``repo_root`` before
    calling ``relative_to``. That avoids the common pathlib bug where a relative
    path is compared directly to an absolute repository root.
    """

    root = repo_root.resolve()
    out = _resolve_inside_repo(root, output_dir)
    if out is None:
        raise ValueError(f"output_dir must be inside repo_root: {output_dir}")
    out.mkdir(parents=True, exist_ok=True)

    zip_path = out / zip_name
    manifest_path = out / manifest_name
    included: list[str] = []
    missing: list[str] = []
    skipped_outside_repo: list[str] = []

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for raw_path in include_paths:
            resolved = _resolve_inside_repo(root, raw_path)
            if resolved is None:
                skipped_outside_repo.append(str(raw_path))
                continue
            if not resolved.exists():
                missing.append(str(raw_path))
                continue
            files = [resolved] if resolved.is_file() else sorted(path for path in resolved.rglob("*") if path.is_file())
            for file_path in files:
                arcname = file_path.relative_to(root).as_posix()
                archive.write(file_path, arcname)
                included.append(arcname)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "boundary": "context_bundle_only_not_pipeline_input",
        "purpose": purpose,
        "zip_path": str(zip_path),
        "included": included,
        "missing": missing,
        "skipped_outside_repo": skipped_outside_repo,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with zipfile.ZipFile(zip_path, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.write(manifest_path, manifest_path.relative_to(root).as_posix())

    return ContextBundleResult(
        zip_path=zip_path,
        manifest_path=manifest_path,
        included=tuple(included),
        missing=tuple(missing),
        skipped_outside_repo=tuple(skipped_outside_repo),
    )


def execute_read_only_query_specs(
    connection: Any,
    query_specs: Mapping[str, str],
    *,
    row_limit: int = 20,
) -> dict[str, dict[str, Any]]:
    """Execute read-only diagnostic queries and isolate failures per query.

    If one query fails, the function rolls back the transaction before
    continuing. This prevents the next query from failing only because the
    previous query left the transaction in an aborted state.
    """

    results: dict[str, dict[str, Any]] = {}
    for name, sql in query_specs.items():
        if not is_read_only_sql(sql):
            results[name] = {
                "status": "blocked_not_read_only",
                "row_count": 0,
                "rows": [],
            }
            continue
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = [_row_to_dict(row) for row in cursor.fetchall()]
            limited_rows = rows[:row_limit]
            results[name] = {
                "status": "ok",
                "row_count": len(rows),
                "columns": list(limited_rows[0].keys()) if limited_rows else [],
                "rows": limited_rows,
            }
        except Exception as exc:  # pragma: no cover - exact DB exceptions vary by driver.
            _rollback_safely(connection)
            results[name] = {
                "status": "error",
                "error": type(exc).__name__,
                "message": str(exc),
                "row_count": 0,
                "rows": [],
            }
    return results


def is_read_only_sql(sql: str) -> bool:
    normalized = " ".join(sql.strip().lower().split())
    if not normalized.startswith(READ_ONLY_PREFIXES):
        return False
    padded = f" {normalized} "
    return not any(token in padded for token in FORBIDDEN_SQL_TOKENS)


def _resolve_inside_repo(repo_root: Path, path: Path) -> Path | None:
    root = repo_root.resolve()
    candidate = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    if hasattr(row, "_asdict"):
        return dict(row._asdict())
    return {"value": row}


def _rollback_safely(connection: Any) -> None:
    rollback = getattr(connection, "rollback", None)
    if rollback is None:
        return
    try:
        rollback()
    except Exception:
        return
