#!/usr/bin/env python3
"""Read-only governance drift guard for the job-application-pipeline project.

The guard is intentionally conservative:
- it does not modify files,
- it does not access the database,
- it does not call external services,
- it treats governance findings as reportable facts.

Default mode is advisory and exits with 0.
Use --strict in CI/PR validation to turn hard guardrail violations into a non-zero exit.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


BASELINE_AGENT_LIKE_SCRIPT_COUNT = 49
BASELINE_AGENT_LIKE_TEST_COUNT = 52

GOVERNANCE_REFERENCE_FILES = [
    Path("docs/reference/governance/agent_governance_registry.md"),
    Path("docs/reference/governance/agent_classification_catalog.md"),
    Path("docs/reference/governance/agent_classification_decision_rules.md"),
    Path("docs/reference/governance/agent_capability_audit_matrix.md"),
    Path("docs/reference/governance/agent_capability_gap_register.md"),
    Path("docs/reference/governance/agent_responsibility_model.md"),
    # Backward-compatible paths for tmp_path unit tests and pre-DOC-001L branches.
    Path("docs/governance/agent_governance_registry.md"),
    Path("docs/governance/agent_classification_catalog.md"),
    Path("docs/governance/agent_classification_decision_rules.md"),
    Path("docs/governance/agent_capability_audit_matrix.md"),
    Path("docs/governance/agent_capability_gap_register.md"),
    Path("docs/governance/agent_responsibility_model.md"),
]


AGENT_NAME_MARKERS = (
    "agent",
    "orchestrator",
    "gate",
    "queue",
)


@dataclass(frozen=True)
class GovernanceDriftFinding:
    severity: str
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class GovernanceDriftReport:
    agent_like_script_count: int
    agent_like_test_count: int
    unregistered_agent_like_scripts: list[str]
    docs_project_state_status_entries: list[str]
    findings: list[GovernanceDriftFinding]
    strict_failed: bool


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _run_git_status(root: Path) -> list[str]:
    try:
        output = subprocess.check_output(
            ["git", "status", "--short"],
            cwd=root,
            text=True,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        return []
    return [line for line in output.splitlines() if line.strip()]


def _is_agent_like(path: Path) -> bool:
    lower_name = path.name.lower()
    return any(marker in lower_name for marker in AGENT_NAME_MARKERS)


def _iter_py_files(root: Path, relative_dir: str) -> Iterable[Path]:
    base = root / relative_dir
    if not base.exists():
        return []
    return sorted(
        p
        for p in base.rglob("*.py")
        if ".venv" not in p.parts and "__pycache__" not in p.parts
    )


def _load_governance_reference_text(root: Path) -> str:
    return "\n".join(_read_text(root / path) for path in GOVERNANCE_REFERENCE_FILES).lower()


def collect_governance_drift(root: Path, *, strict: bool = False) -> GovernanceDriftReport:
    agent_like_scripts = [
        p.relative_to(root).as_posix()
        for p in _iter_py_files(root, "scripts")
        if _is_agent_like(p)
    ]
    agent_like_tests = [
        p.relative_to(root).as_posix()
        for p in _iter_py_files(root, "tests")
        if _is_agent_like(p)
    ]

    reference_text = _load_governance_reference_text(root)
    unregistered_agent_like_scripts = []
    for rel in agent_like_scripts:
        script_name = Path(rel).name.lower()
        module_stem = Path(rel).stem.lower()
        if script_name not in reference_text and module_stem not in reference_text:
            unregistered_agent_like_scripts.append(rel)

    status_entries = _run_git_status(root)
    docs_project_state_status_entries = [
        line for line in status_entries if "exports/project_state/" in line
    ]

    findings: list[GovernanceDriftFinding] = []

    if len(agent_like_scripts) > BASELINE_AGENT_LIKE_SCRIPT_COUNT:
        findings.append(
            GovernanceDriftFinding(
                severity="error",
                code="new_agent_like_script_count_exceeds_baseline",
                message=(
                    f"Agent-like script count is {len(agent_like_scripts)}, "
                    f"above GOV-001A baseline {BASELINE_AGENT_LIKE_SCRIPT_COUNT}. "
                    "New agent-like scripts must be classified in governance docs before merge."
                ),
            )
        )

    if len(agent_like_tests) < BASELINE_AGENT_LIKE_TEST_COUNT:
        findings.append(
            GovernanceDriftFinding(
                severity="warning",
                code="agent_like_test_count_below_baseline",
                message=(
                    f"Agent-like test count is {len(agent_like_tests)}, "
                    f"below GOV-001A baseline {BASELINE_AGENT_LIKE_TEST_COUNT}. "
                    "This may indicate test deletion or a changed naming/classification pattern."
                ),
            )
        )

    for rel in unregistered_agent_like_scripts:
        findings.append(
            GovernanceDriftFinding(
                severity="error",
                code="agent_like_script_missing_governance_reference",
                message=(
                    "Agent-like script is not mentioned in the governance registry, "
                    "classification catalog, capability matrix, gap register, or responsibility model."
                ),
                path=rel,
            )
        )

    for line in docs_project_state_status_entries:
        findings.append(
            GovernanceDriftFinding(
                severity="warning",
                code="project_state_handover_artifact_present",
                message=(
                    "docs/project_state appears in git status. Handover/state files are useful context "
                    "but should not accidentally become current architecture truth."
                ),
                path=line,
            )
        )

    strict_failed = strict and any(f.severity == "error" for f in findings)

    return GovernanceDriftReport(
        agent_like_script_count=len(agent_like_scripts),
        agent_like_test_count=len(agent_like_tests),
        unregistered_agent_like_scripts=unregistered_agent_like_scripts,
        docs_project_state_status_entries=docs_project_state_status_entries,
        findings=findings,
        strict_failed=strict_failed,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check governance drift guardrails.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on hard drift findings.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    args = parser.parse_args()

    report = collect_governance_drift(Path.cwd(), strict=args.strict)

    if args.json:
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    else:
        print("GOV-001E governance drift guard")
        print(f"agent_like_script_count={report.agent_like_script_count}")
        print(f"agent_like_test_count={report.agent_like_test_count}")
        print(f"unregistered_agent_like_scripts={len(report.unregistered_agent_like_scripts)}")
        print(f"docs_project_state_status_entries={len(report.docs_project_state_status_entries)}")
        if report.findings:
            print()
            print("Findings:")
            for finding in report.findings:
                path = f" [{finding.path}]" if finding.path else ""
                print(f"- {finding.severity.upper()} {finding.code}{path}: {finding.message}")
        else:
            print("status=pass")

    return 1 if report.strict_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
