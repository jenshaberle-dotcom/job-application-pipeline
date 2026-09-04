from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.run_cand001_validated_origin_url_persistence_gate import (
    run as run_origin_url_persistence,
)
from scripts.run_employer_origin_agent_chain import (
    ChainDecision,
    active_controlled_source_completed,
    connector_artifacts_exist,
    load_candidate as load_chain_candidate,
    load_gate_reviews,
    next_decision,
)
from src.config import get_database_config


CAMPAIGN_CONTRACT_VERSION = "TRUSTED-LOCAL-PRODUCT-CAMPAIGN.v1"
MODE_DB_ONLY = "db_only"

AUTO_DB_ACTION_MODULES = {
    "run_preconnector_precondition_recovery": (
        "scripts.run_employer_origin_preconnector_precondition_agent"
    ),
    "run_detail_evidence_repair": (
        "scripts.run_employer_origin_detail_evidence_repair_agent"
    ),
    "run_connector_candidate_gate": (
        "scripts.run_employer_origin_connector_candidate_agent"
    ),
    "run_connector_build_readiness_agent": (
        "scripts.run_employer_origin_connector_build_readiness_agent"
    ),
}

EXPECTED_BOUNDARY_ACTIONS = {
    "run_connector_artifact_generator": "repo_mutation_required",
    "run_connector_validation_agent": "repo_artifacts_required",
    "run_final_approval_gate_agent": "explicit_human_approval_required",
    "run_registration_execution_plan_agent": "registration_boundary_reached",
}

COMPANY_KEY_RE = re.compile(r"^[a-z0-9_]{1,80}$")
TARGET_LOCATION_RE = re.compile(r"^[A-Za-z0-9ÄÖÜäöüß ._\-/]{1,100}$")


@dataclass(frozen=True)
class CandidateSnapshot:
    candidate_id: int
    company_key: str
    company_name: str
    status: str
    candidate_url: str | None
    source_name_candidate: str
    source_family_candidate: str
    risk_level: str


@dataclass(frozen=True)
class ExecutionPolicy:
    executable: bool
    expected_module: str | None
    boundary: str | None
    reason: str


@dataclass(frozen=True)
class StepReceipt:
    sequence: int
    action: str
    module: str | None
    result: str
    return_code: int | None
    reason: str


def validate_inputs(
    *,
    company_key: str,
    candidate_id: int,
    target_location: str,
    max_steps: int,
    mode: str,
) -> None:
    if COMPANY_KEY_RE.fullmatch(company_key) is None:
        raise ValueError("company_key must be canonical lowercase [a-z0-9_]")
    if candidate_id < 1:
        raise ValueError("candidate_id must be positive")
    if TARGET_LOCATION_RE.fullmatch(target_location) is None:
        raise ValueError("target_location contains unsupported characters")
    if max_steps < 1 or max_steps > 20:
        raise ValueError("max_steps must be between 1 and 20")
    if mode != MODE_DB_ONLY:
        raise ValueError(f"unsupported campaign mode: {mode!r}")


def decision_execution_policy(decision: ChainDecision, *, mode: str) -> ExecutionPolicy:
    if mode != MODE_DB_ONLY:
        return ExecutionPolicy(False, None, "unsupported_mode", f"unsupported mode {mode!r}")

    expected = AUTO_DB_ACTION_MODULES.get(decision.action)
    if expected is not None:
        if decision.module != expected:
            return ExecutionPolicy(
                False,
                expected,
                "decision_module_mismatch",
                f"action {decision.action!r} must route to {expected!r}, got {decision.module!r}",
            )
        return ExecutionPolicy(True, expected, None, "bounded DB/gate action is allowlisted")

    if decision.action.startswith("stop_"):
        return ExecutionPolicy(False, None, decision.action, decision.reason)

    boundary = EXPECTED_BOUNDARY_ACTIONS.get(decision.action)
    if boundary is not None:
        return ExecutionPolicy(False, decision.module, boundary, decision.reason)

    return ExecutionPolicy(
        False,
        decision.module,
        "unrecognized_chain_action",
        f"chain action {decision.action!r} is not allowlisted for trusted DB-only execution",
    )


def _connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def load_exact_candidate(
    conn: psycopg.Connection[Any],
    *,
    company_key: str,
    candidate_id: int,
) -> CandidateSnapshot:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                id,
                company_key,
                company_name,
                status,
                candidate_url,
                source_name_candidate,
                source_family_candidate,
                risk_level
            FROM employer_origin_source_candidates
            WHERE id = %s
            """,
            (candidate_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"candidate_id={candidate_id} does not exist")
        if str(row["company_key"]) != company_key:
            raise RuntimeError(
                "exact candidate identity mismatch: "
                f"candidate_id={candidate_id} company_key={row['company_key']!r} "
                f"expected={company_key!r}"
            )

        cur.execute(
            """
            SELECT id
            FROM employer_origin_source_candidates
            WHERE company_key = %s
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (company_key,),
        )
        latest = cur.fetchone()
        if latest is None or int(latest["id"]) != candidate_id:
            raise RuntimeError(
                "exact candidate is no longer latest for company_key; refusing company-key child execution"
            )

    return CandidateSnapshot(
        candidate_id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        status=str(row["status"]),
        candidate_url=(str(row["candidate_url"]) if row["candidate_url"] else None),
        source_name_candidate=str(row["source_name_candidate"]),
        source_family_candidate=str(row["source_family_candidate"]),
        risk_level=str(row["risk_level"]),
    )


def _origin_persistence_args(
    *,
    snapshot: CandidateSnapshot,
    target_location: str,
    reviewed_by: str,
    output_dir: Path,
) -> argparse.Namespace:
    label = (
        "trusted_local_product_campaign_"
        f"{snapshot.company_key}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    )
    return SimpleNamespace(
        benchmark_label=label,
        company_key=[snapshot.company_key],
        target_location=target_location,
        target_locale="de",
        reviewed_by=reviewed_by,
        apply=True,
        include_active_controlled=False,
        timeout_seconds=5.0,
        max_url_candidates=12,
        market_evidence_limit=30,
        search_provider=["none"],
        search_query_limit=4,
        search_max_results=5,
        search_timeout_seconds=8.0,
        search_depth="advanced",
        search_results_json=None,
        max_evidence_candidates=4,
        max_evidence_http_requests=12,
        evidence_timeout_seconds=8.0,
        max_response_bytes=750_000,
        llm_model="gpt-5.4-mini",
        llm_reasoning_effort="low",
        llm_max_output_tokens=600,
        llm_reserved_input_tokens=5000,
        llm_timeout_seconds=60.0,
        max_estimated_llm_cost_usd_per_company=0.0,
        disable_tavily=True,
        disable_llm=True,
        no_probe=False,
        single_pass_diagnostic=True,
        candidate_id_by_company_key={snapshot.company_key: snapshot.candidate_id},
        output_json=output_dir / "origin_url_persistence.json",
        output_markdown=output_dir / "origin_url_persistence.md",
    )


def _write_receipt(
    *,
    output_path: Path,
    args: argparse.Namespace,
    initial: CandidateSnapshot,
    final: CandidateSnapshot,
    status: str,
    next_action: str,
    steps: list[StepReceipt],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract_version": CAMPAIGN_CONTRACT_VERSION,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "mode": args.mode,
        "company_key": args.company_key,
        "candidate_id": args.candidate_id,
        "target_location": args.target_location,
        "reviewed_by": args.reviewed_by,
        "campaign_status": status,
        "next_action": next_action,
        "initial_candidate": asdict(initial),
        "final_candidate": asdict(final),
        "steps": [asdict(step) for step in steps],
        "boundary": {
            "trusted_main_code_only": True,
            "exact_candidate_identity_required": True,
            "db_gate_actions_allowlisted": True,
            "repo_artifact_generation": False,
            "connector_registration": False,
            "source_activation": False,
            "final_approval": False,
            "uac_interaction": False,
        },
    }
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _execute_child(decision: ChainDecision, *, project_root: Path) -> int:
    assert decision.module is not None
    command = [sys.executable, "-m", decision.module, *decision.args]
    print("EXEC:", " ".join(command))
    completed = subprocess.run(
        command,
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="" if completed.stderr.endswith("\n") else "\n")
    return int(completed.returncode)


def run_campaign(args: argparse.Namespace) -> int:
    validate_inputs(
        company_key=args.company_key,
        candidate_id=args.candidate_id,
        target_location=args.target_location,
        max_steps=args.max_steps,
        mode=args.mode,
    )

    project_root = Path(__file__).resolve().parents[1]
    output_path = Path(args.output_json)
    output_dir = output_path.parent / f"{args.company_key}-{args.candidate_id}"
    steps: list[StepReceipt] = []

    with _connect() as conn:
        initial = load_exact_candidate(
            conn,
            company_key=args.company_key,
            candidate_id=args.candidate_id,
        )

    print("Trusted Local Product Campaign")
    print(f"contract: {CAMPAIGN_CONTRACT_VERSION}")
    print(f"mode: {args.mode}")
    print(f"candidate: {initial.candidate_id} | {initial.company_key} | {initial.status}")
    print(f"candidate_url: {initial.candidate_url or '<unresolved>'}")

    if not initial.candidate_url:
        print("STEP: deterministic exact-candidate Employer-Origin persistence")
        try:
            run_origin_url_persistence(
                _origin_persistence_args(
                    snapshot=initial,
                    target_location=args.target_location,
                    reviewed_by=args.reviewed_by,
                    output_dir=output_dir,
                )
            )
            rc = 0
            reason = "deterministic CAND-001 origin persistence completed"
        except (SystemExit, ValueError, RuntimeError) as exc:
            rc = int(exc.code) if isinstance(exc, SystemExit) and isinstance(exc.code, int) else 2
            reason = str(exc)
        steps.append(
            StepReceipt(
                sequence=len(steps) + 1,
                action="persist_validated_origin_url",
                module="scripts.run_cand001_validated_origin_url_persistence_gate",
                result="completed" if rc == 0 else "stopped",
                return_code=rc,
                reason=reason,
            )
        )

        with _connect() as conn:
            after_origin = load_exact_candidate(
                conn,
                company_key=args.company_key,
                candidate_id=args.candidate_id,
            )
        if not after_origin.candidate_url:
            _write_receipt(
                output_path=output_path,
                args=args,
                initial=initial,
                final=after_origin,
                status="expected_stop",
                next_action="origin_url_not_auto_persisted",
                steps=steps,
            )
            print("CAMPAIGN_STATUS=expected_stop")
            print("NEXT_ACTION=origin_url_not_auto_persisted")
            print(f"RECEIPT={output_path}")
            return 0

    for _ in range(args.max_steps):
        with _connect() as conn:
            snapshot = load_exact_candidate(
                conn,
                company_key=args.company_key,
                candidate_id=args.candidate_id,
            )
            chain_candidate = load_chain_candidate(conn, args.company_key)
            gates = load_gate_reviews(conn, snapshot.candidate_id)

        if active_controlled_source_completed(chain_candidate, gates):
            _write_receipt(
                output_path=output_path,
                args=args,
                initial=initial,
                final=snapshot,
                status="completed",
                next_action="monitor_source_lifecycle",
                steps=steps,
            )
            print("CAMPAIGN_STATUS=completed")
            print("NEXT_ACTION=monitor_source_lifecycle")
            print(f"RECEIPT={output_path}")
            return 0

        decision = next_decision(
            gates,
            company_key=args.company_key,
            target_location=args.target_location,
            reviewed_by=args.reviewed_by,
            attempt_repair=True,
            write_connector=False,
            artifacts_exist=connector_artifacts_exist(snapshot.source_family_candidate),
            approval_token=None,
            write_registration_plan=False,
        )
        policy = decision_execution_policy(decision, mode=args.mode)
        print(f"DECISION: {decision.action} | {decision.reason}")

        if not policy.executable:
            steps.append(
                StepReceipt(
                    sequence=len(steps) + 1,
                    action=decision.action,
                    module=decision.module,
                    result="boundary_stop",
                    return_code=None,
                    reason=policy.reason,
                )
            )
            with _connect() as conn:
                final = load_exact_candidate(
                    conn,
                    company_key=args.company_key,
                    candidate_id=args.candidate_id,
                )
            _write_receipt(
                output_path=output_path,
                args=args,
                initial=initial,
                final=final,
                status="expected_stop",
                next_action=policy.boundary or decision.action,
                steps=steps,
            )
            print("CAMPAIGN_STATUS=expected_stop")
            print(f"NEXT_ACTION={policy.boundary or decision.action}")
            print(f"RECEIPT={output_path}")
            return 0

        return_code = _execute_child(decision, project_root=project_root)
        result = "completed" if return_code == 0 else "manual_stop" if return_code == 2 else "failed"
        steps.append(
            StepReceipt(
                sequence=len(steps) + 1,
                action=decision.action,
                module=decision.module,
                result=result,
                return_code=return_code,
                reason=decision.reason,
            )
        )

        if return_code == 2:
            with _connect() as conn:
                final = load_exact_candidate(
                    conn,
                    company_key=args.company_key,
                    candidate_id=args.candidate_id,
                )
            _write_receipt(
                output_path=output_path,
                args=args,
                initial=initial,
                final=final,
                status="expected_stop",
                next_action="manual_review_required",
                steps=steps,
            )
            print("CAMPAIGN_STATUS=expected_stop")
            print("NEXT_ACTION=manual_review_required")
            print(f"RECEIPT={output_path}")
            return 0
        if return_code != 0:
            with _connect() as conn:
                final = load_exact_candidate(
                    conn,
                    company_key=args.company_key,
                    candidate_id=args.candidate_id,
                )
            _write_receipt(
                output_path=output_path,
                args=args,
                initial=initial,
                final=final,
                status="failed",
                next_action=f"inspect_failed_action:{decision.action}",
                steps=steps,
            )
            print("CAMPAIGN_STATUS=failed")
            print(f"NEXT_ACTION=inspect_failed_action:{decision.action}")
            print(f"RECEIPT={output_path}")
            return 3

    with _connect() as conn:
        final = load_exact_candidate(
            conn,
            company_key=args.company_key,
            candidate_id=args.candidate_id,
        )
    _write_receipt(
        output_path=output_path,
        args=args,
        initial=initial,
        final=final,
        status="expected_stop",
        next_action="bounded_max_steps_reached",
        steps=steps,
    )
    print("CAMPAIGN_STATUS=expected_stop")
    print("NEXT_ACTION=bounded_max_steps_reached")
    print(f"RECEIPT={output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute only deterministic allowlisted Product E2E DB/gate transitions on a trusted local runner."
        )
    )
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--candidate-id", type=int, required=True)
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--reviewed-by", default="trusted-local-ci")
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--mode", default=MODE_DB_ONLY, choices=(MODE_DB_ONLY,))
    parser.add_argument("--output-json", type=Path, required=True)
    return parser


def main() -> None:
    raise SystemExit(run_campaign(build_parser().parse_args()))


if __name__ == "__main__":
    main()
