from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_connector_build_readiness_agent import (
    GateReview,
    ReadinessRepository,
    SourceCandidate,
    evaluate_readiness,
)


PLAN_DIR = Path("docs/planning/active/source-candidates")


@dataclass(frozen=True)
class RegistrationPlan:
    candidate: SourceCandidate
    module_path: str
    test_path: str
    connector_class: str
    source_name: str
    source_type: str
    readiness_status: str
    readiness_reason: str
    required_manual_approval_token: str
    implementation_steps: tuple[str, ...]
    validation_steps: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    evidence: dict[str, Any]


def snake_case(value: str) -> str:
    import re

    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def pascal_case(value: str) -> str:
    return "".join(part.capitalize() for part in snake_case(value).split("_") if part)


def connector_spec(gates: dict[str, GateReview]) -> dict[str, Any]:
    gate = gates.get("connector_candidate_gate")
    if not gate:
        return {}
    evidence = gate.evidence or {}
    spec = evidence.get("connector_candidate_spec") or {}
    return spec if isinstance(spec, dict) else {}


def build_registration_plan(
    candidate: SourceCandidate,
    gates: dict[str, GateReview],
) -> RegistrationPlan:
    readiness = evaluate_readiness(candidate, gates)
    spec = connector_spec(gates)
    recommended = spec.get("recommended_connector") or {}

    module_name = snake_case(candidate.source_family_candidate or candidate.company_key)
    class_name = recommended.get("class_name") or f"{pascal_case(module_name)}Connector"

    return RegistrationPlan(
        candidate=candidate,
        module_path=str(recommended.get("module_path") or f"src/connectors/{module_name}.py"),
        test_path=str(recommended.get("test_path") or f"tests/test_{module_name}_connector.py"),
        connector_class=str(class_name),
        source_name=str(recommended.get("source_name") or candidate.source_name_candidate),
        source_type=str(recommended.get("source_type") or candidate.source_type_candidate),
        readiness_status=readiness.status,
        readiness_reason=readiness.reason,
        required_manual_approval_token="approve_connector_registration",
        implementation_steps=(
            "Generate or review connector candidate module from DB-backed gate evidence.",
            "Run connector-specific tests and full test suite.",
            "Review source scope, request limits and raw_data evidence fields.",
            "Only after manual approval: register connector in ingestion CLI/runner.",
            "Only after separate controlled activation: create/enable source target search profile.",
        ),
        validation_steps=(
            "python -m compileall src scripts tests",
            "pytest -q",
            "python -m scripts.run_employer_origin_connector_build_readiness_agent --company-key "
            f"{candidate.company_key}",
            "python -m scripts.run_employer_origin_agent_chain --company-key "
            f"{candidate.company_key} --reviewed-by jens --plan-only",
        ),
        forbidden_actions=(
            "Do not activate recurring ingestion in this plan.",
            "Do not write Bronze rows in this plan.",
            "Do not use CSV/Excel/generated exports as process inputs.",
            "Do not register the connector without the explicit approval token.",
            "Do not create a source activation migration in this plan.",
        ),
        evidence={
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "readiness_evidence": readiness.evidence,
            "connector_candidate_spec_present": bool(spec),
        },
    )


def render_markdown(plan: RegistrationPlan) -> str:
    return "\n".join(
        [
            f"# Connector Registration Plan — {plan.candidate.company_key}",
            "",
            "## Status",
            "",
            f"- readiness: `{plan.readiness_status}`",
            f"- reason: {plan.readiness_reason}",
            f"- required manual approval token: `{plan.required_manual_approval_token}`",
            "",
            "## Candidate",
            "",
            f"- company: {plan.candidate.company_name}",
            f"- source name: `{plan.source_name}`",
            f"- source type: `{plan.source_type}`",
            f"- connector class: `{plan.connector_class}`",
            f"- module path: `{plan.module_path}`",
            f"- test path: `{plan.test_path}`",
            "",
            "## Implementation Steps",
            "",
            *[f"- {step}" for step in plan.implementation_steps],
            "",
            "## Validation Steps",
            "",
            *[f"- `{step}`" for step in plan.validation_steps],
            "",
            "## Forbidden Actions",
            "",
            *[f"- {action}" for action in plan.forbidden_actions],
            "",
            "## Boundary",
            "",
            "This plan is a repository review artifact. It does not register, activate, ingest or schedule anything by itself.",
            "",
        ]
    )


def plan_path(candidate: SourceCandidate) -> Path:
    return PLAN_DIR / f"{snake_case(candidate.company_key)}_connector_registration_plan.md"


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(
        ReadinessRepository.__annotations__.get("unused", None) or _dsn_from_env()
    ) as conn:
        repo = ReadinessRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        gates = repo.load_gates(candidate.id)

    plan = build_registration_plan(candidate, gates)

    print(f"candidate_id: {candidate.id}")
    print(f"candidate: {candidate.company_key} | {candidate.source_name_candidate}")
    print(f"registration_plan_readiness: {plan.readiness_status}")
    print(f"reason: {plan.readiness_reason}")

    if plan.readiness_status != "ready":
        print("STOP: registration plan can be written for review, but connector registration is not allowed.")
    else:
        print("NEXT: final approval is required before connector registration.")

    if args.write:
        path = plan_path(candidate)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(plan), encoding="utf-8")
        print(f"wrote_plan: {path}")

    if args.print_json:
        print(json.dumps(plan.evidence, indent=2, ensure_ascii=False, default=str))

    return 0 if plan.readiness_status in {"ready", "not_applicable"} else 2


def _dsn_from_env() -> str:
    return (
        f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
        f"port={os.environ.get('POSTGRES_PORT', '5432')} "
        f"dbname={os.environ['POSTGRES_DB']} "
        f"user={os.environ['POSTGRES_USER']} "
        f"password={os.environ['POSTGRES_PASSWORD']}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare a reviewable connector registration plan from DB-backed gate evidence."
    )
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
