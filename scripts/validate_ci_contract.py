from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATTERN = re.compile(r"(?P<number>\d{3})_[a-z0-9_]+\.sql")


class ContractError(RuntimeError):
    """Raised when a repository-level CI contract is violated."""


def _active_requirement_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


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
            first = seen_numbers[number].name
            raise ContractError(f"Duplicate migration number {number}: {first}, {path.name}")
        seen_numbers[number] = path

        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ContractError(f"Empty migration file: {path.name}")
        if any(marker in text for marker in ("<<<<<<<", "=======", ">>>>>>>")):
            raise ContractError(f"Merge conflict marker in migration: {path.name}")

    return len(migration_paths)


def validate_repository_boundaries() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required_statements = (
        "No commits on `main`.",
        "Reports and exports are outputs, not source-of-truth inputs.",
        "Dry-run before apply.",
    )
    missing = [statement for statement in required_statements if statement not in readme]
    if missing:
        raise ContractError(f"README governance boundary drift: missing={missing}")


def main() -> int:
    try:
        validate_development_tooling()
        migration_count = validate_database_migrations()
        validate_repository_boundaries()
    except (ContractError, OSError, tomllib.TOMLDecodeError) as exc:
        print(f"CI contract failed: {exc}", file=sys.stderr)
        return 1

    print("Pipeline CI contract passed")
    print(f"- Database migrations: {migration_count}")
    print("- Development tooling: pinned and policy-aligned")
    print("- Repository governance boundaries: present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
