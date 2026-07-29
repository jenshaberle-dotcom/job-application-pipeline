from __future__ import annotations

import json
import re
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATTERN = re.compile(r"(?P<number>\d{3})_[a-z0-9_]+\.sql")
WORK_ITEM_PATTERN = re.compile(r"[A-Z]+-\d{3}")
CONTRADICTION_PATTERN = re.compile(r"CTR-\d{3}")
BACKLOG_ROOT = ROOT / "docs" / "planning" / "active"
BACKLOG_PATH = BACKLOG_ROOT / "backlog_catalog.json"

ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3", "P4"}
ALLOWED_RISK_ZONES = {"R0", "R1", "R2", "R3"}
ALLOWED_STATUSES = {
    "in_progress",
    "ready",
    "ready_after_truth_rebaseline",
    "ready_after_candidate_proof",
    "conditional_ready",
    "blocked",
    "blocked_by_operator",
    "operator_decision",
    "status_reconciliation",
    "planned",
    "parked_until_v1_inputs",
    "parked",
}
REQUIRED_LIST_FIELDS = (
    "dependencies",
    "evidence_paths",
    "boundaries",
    "acceptance_criteria",
    "validation",
    "operator_decisions",
)


class ContractError(RuntimeError):
    """Raised when a repository-level CI contract is violated."""


def _active_requirement_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _nonempty(value: Any, *, field: str, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{context}.{field} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, *, field: str, context: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ContractError(f"{context}.{field} must be a list of non-empty strings")
    return [item.strip() for item in value]


def _load_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ContractError(f"JSON root must be an object: {path.relative_to(ROOT)}")
    return payload


def validate_development_tooling() -> None:
    requirements = _active_requirement_lines(ROOT / "requirements-dev.txt")
    if "-r requirements.txt" not in requirements:
        raise ContractError("requirements-dev.txt must include requirements.txt")
    if not any(line.startswith("pytest==") for line in requirements):
        raise ContractError("pytest must remain pinned in requirements-dev.txt")
    if not any(line.startswith("ruff==") for line in requirements):
        raise ContractError("ruff must remain pinned in requirements-dev.txt")

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    ruff = pyproject.get("tool", {}).get("ruff", {})
    lint = ruff.get("lint", {})
    if ruff.get("target-version") != "py312":
        raise ContractError("Ruff target-version must remain py312")
    if set(lint.get("select", [])) != {"E4", "E7", "E9", "F"}:
        raise ContractError("Ruff correctness baseline changed without a policy update")

    excluded = set(ruff.get("extend-exclude", []))
    required_exclusions = {"exports", "runs", ".venv"}
    if not required_exclusions.issubset(excluded):
        raise ContractError("Generated/runtime paths must remain excluded from Ruff")


def validate_database_migrations() -> int:
    migration_paths = sorted((ROOT / "db" / "migrations").glob("*.sql"))
    if not migration_paths:
        raise ContractError("No database migrations found under db/migrations/")

    seen_numbers: dict[str, Path] = {}
    for path in migration_paths:
        match = MIGRATION_PATTERN.fullmatch(path.name)
        if match is None:
            raise ContractError(f"Invalid migration filename: {path.name}")
        number = match.group("number")
        if number in seen_numbers:
            raise ContractError(
                f"Duplicate migration number {number}: "
                f"{seen_numbers[number].name}, {path.name}"
            )
        seen_numbers[number] = path
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ContractError(f"Empty migration file: {path.name}")
        if any(marker in text for marker in ("<<<<<<<", "=======", ">>>>>>>")):
            raise ContractError(f"Merge conflict marker in migration: {path.name}")
    return len(migration_paths)


def validate_repository_boundaries() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required = (
        "No commits on `main`.",
        "Reports and exports are outputs, not source-of-truth inputs.",
        "Dry-run before apply.",
    )
    missing = [statement for statement in required if statement not in readme]
    if missing:
        raise ContractError(f"README governance boundary drift: missing={missing}")


def _validate_item(
    raw_item: Mapping[str, Any],
    *,
    context: str,
    expected_parent: str | None,
) -> tuple[str, list[str]]:
    item_id = _nonempty(raw_item.get("id"), field="id", context=context)
    if WORK_ITEM_PATTERN.fullmatch(item_id) is None:
        raise ContractError(f"Invalid backlog work item ID: {item_id}")
    _nonempty(raw_item.get("title"), field="title", context=context)
    _nonempty(raw_item.get("outcome"), field="outcome", context=context)

    status = _nonempty(raw_item.get("status"), field="status", context=context)
    if status not in ALLOWED_STATUSES:
        raise ContractError(f"Unsupported status for {item_id}: {status}")
    priority = _nonempty(raw_item.get("priority"), field="priority", context=context)
    if priority not in ALLOWED_PRIORITIES:
        raise ContractError(f"Unsupported priority for {item_id}: {priority}")
    risk = _nonempty(raw_item.get("risk_zone"), field="risk_zone", context=context)
    if risk not in ALLOWED_RISK_ZONES:
        raise ContractError(f"Unsupported risk zone for {item_id}: {risk}")

    lists = {
        field: _string_list(raw_item.get(field), field=field, context=context)
        for field in REQUIRED_LIST_FIELDS
    }
    for required_nonempty in (
        "evidence_paths",
        "boundaries",
        "acceptance_criteria",
        "validation",
    ):
        if not lists[required_nonempty]:
            raise ContractError(f"{context}.{required_nonempty} must not be empty")

    parent = raw_item.get("parent_capability")
    if expected_parent is None:
        if parent is not None:
            raise ContractError(f"Capability {item_id} must not declare a parent")
    elif parent != expected_parent:
        raise ContractError(
            f"Story {item_id} parent must be {expected_parent}, got {parent}"
        )
    return item_id, lists["dependencies"]


def validate_backlog_catalog(path: Path = BACKLOG_PATH) -> tuple[int, int]:
    catalog = _load_object(path)
    if catalog.get("schema_version") != "pipeline.backlog_catalog.v1":
        raise ContractError("Unexpected backlog catalog schema")
    if catalog.get("target_id") != "job-application-pipeline":
        raise ContractError("Backlog target_id does not match this repository")

    raw_files = catalog.get("capability_files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ContractError("capability_files must be a non-empty list")
    capability_files = _string_list(
        raw_files, field="capability_files", context="catalog"
    )
    if len(capability_files) != len(set(capability_files)):
        raise ContractError("Duplicate capability file path")

    item_ids: set[str] = set()
    capability_ids: set[str] = set()
    story_ids: set[str] = set()
    graph: dict[str, list[str]] = {}

    for relative in capability_files:
        file_path = BACKLOG_ROOT / relative
        if not file_path.is_file():
            raise ContractError(f"Missing capability file: {relative}")
        payload = _load_object(file_path)
        if payload.get("schema_version") != "pipeline.backlog_capability.v1":
            raise ContractError(f"Unexpected schema in {relative}")
        if payload.get("target_id") != "job-application-pipeline":
            raise ContractError(f"Wrong target_id in {relative}")

        capability = payload.get("capability")
        stories = payload.get("stories")
        if not isinstance(capability, Mapping):
            raise ContractError(f"{relative}.capability must be an object")
        if not isinstance(stories, list):
            raise ContractError(f"{relative}.stories must be a list")

        capability_id, dependencies = _validate_item(
            capability, context=f"{relative}.capability", expected_parent=None
        )
        if capability_id in item_ids:
            raise ContractError(f"Duplicate backlog ID: {capability_id}")
        item_ids.add(capability_id)
        capability_ids.add(capability_id)
        graph[capability_id] = dependencies

        for index, story in enumerate(stories):
            if not isinstance(story, Mapping):
                raise ContractError(f"{relative}.stories[{index}] must be an object")
            story_id, dependencies = _validate_item(
                story,
                context=f"{relative}.stories[{index}]",
                expected_parent=capability_id,
            )
            if story_id in item_ids:
                raise ContractError(f"Duplicate backlog ID: {story_id}")
            item_ids.add(story_id)
            story_ids.add(story_id)
            graph[story_id] = dependencies

    for item_id, dependencies in graph.items():
        unknown = sorted(set(dependencies) - item_ids)
        if unknown:
            raise ContractError(f"Unknown dependencies for {item_id}: {unknown}")
        if item_id in dependencies:
            raise ContractError(f"Work item {item_id} depends on itself")
    _validate_acyclic_dependencies(graph)

    active_sequence = catalog.get("active_sequence")
    if not isinstance(active_sequence, list) or not active_sequence:
        raise ContractError("active_sequence must be a non-empty list")
    seen_active: set[str] = set()
    for expected_order, step in enumerate(active_sequence, start=1):
        if not isinstance(step, Mapping):
            raise ContractError("Every active_sequence step must be an object")
        if step.get("order") != expected_order:
            raise ContractError("active_sequence order must be contiguous")
        item_id = _nonempty(
            step.get("item_id"), field="item_id", context="active_sequence"
        )
        if item_id not in story_ids:
            raise ContractError(f"Active sequence references non-story: {item_id}")
        if item_id in seen_active:
            raise ContractError(f"Duplicate active sequence item: {item_id}")
        seen_active.add(item_id)
        _nonempty(step.get("gate"), field="gate", context="active_sequence")

    contradictions = catalog.get("contradictions")
    if not isinstance(contradictions, list) or not contradictions:
        raise ContractError("contradictions must be a non-empty list")
    seen_contradictions: set[str] = set()
    for contradiction in contradictions:
        if not isinstance(contradiction, Mapping):
            raise ContractError("Every contradiction must be an object")
        contradiction_id = _nonempty(
            contradiction.get("id"), field="id", context="contradiction"
        )
        if CONTRADICTION_PATTERN.fullmatch(contradiction_id) is None:
            raise ContractError(f"Invalid contradiction ID: {contradiction_id}")
        if contradiction_id in seen_contradictions:
            raise ContractError(f"Duplicate contradiction ID: {contradiction_id}")
        seen_contradictions.add(contradiction_id)
        for field in ("severity", "statement_a", "statement_b", "classification"):
            _nonempty(contradiction.get(field), field=field, context="contradiction")
        resolution = _nonempty(
            contradiction.get("resolution_story"),
            field="resolution_story",
            context="contradiction",
        )
        if resolution not in story_ids:
            raise ContractError(
                f"Contradiction {contradiction_id} references unknown story {resolution}"
            )

    counts = catalog.get("counts")
    if counts != {
        "capabilities": len(capability_ids),
        "stories": len(story_ids),
        "contradictions": len(seen_contradictions),
    }:
        raise ContractError("Catalog counts do not match loaded backlog files")

    return len(capability_ids), len(story_ids)


def _validate_acyclic_dependencies(graph: Mapping[str, Sequence[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(item_id: str, path: list[str]) -> None:
        if item_id in visited:
            return
        if item_id in visiting:
            cycle_start = path.index(item_id)
            raise ContractError(
                "Backlog dependency cycle: "
                + " -> ".join(path[cycle_start:] + [item_id])
            )
        visiting.add(item_id)
        for dependency in graph[item_id]:
            visit(dependency, [*path, dependency])
        visiting.remove(item_id)
        visited.add(item_id)

    for item_id in graph:
        visit(item_id, [item_id])


def main() -> int:
    try:
        validate_development_tooling()
        migration_count = validate_database_migrations()
        validate_repository_boundaries()
        capability_count, story_count = validate_backlog_catalog()
    except (
        ContractError,
        json.JSONDecodeError,
        OSError,
        tomllib.TOMLDecodeError,
    ) as exc:
        print(f"CI contract failed: {exc}", file=sys.stderr)
        return 1

    print("Pipeline CI contract passed")
    print(f"- Database migrations: {migration_count}")
    print("- Development tooling: pinned and policy-aligned")
    print("- Repository governance boundaries: present")
    print(
        f"- Backlog catalog: {capability_count} capabilities, "
        f"{story_count} stories, valid dependency graph"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
