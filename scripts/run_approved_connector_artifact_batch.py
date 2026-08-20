from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


DB_ENV_KEYS = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)
EXPECTED_BUILD_MODE = "connector_candidate_from_gate_evidence"


def parse_env_subset(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError("host-local Pipeline .env is missing")
    parsed: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in DB_ENV_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        parsed[key] = value
    missing = [key for key in DB_ENV_KEYS if not parsed.get(key)]
    if missing:
        raise RuntimeError("host-local DB configuration incomplete: " + ", ".join(missing))
    return parsed


def parse_candidate_ids(value: str) -> tuple[int, ...]:
    raw = [part.strip() for part in value.split(",") if part.strip()]
    if not raw:
        raise ValueError("candidate list is empty")
    candidate_ids = tuple(int(part) for part in raw)
    if any(candidate_id <= 0 for candidate_id in candidate_ids):
        raise ValueError("candidate ids must be positive")
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("candidate ids must be unique")
    return candidate_ids


def git_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.strip()


def checked(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command)}")


def path_tuple(request: Any) -> tuple[str, str, str]:
    return (
        request.paths.module_path,
        request.paths.test_path,
        request.paths.docs_path,
    )


def validate_artifact_paths(paths: tuple[str, str, str]) -> None:
    module_path, test_path, docs_path = paths
    if not module_path.startswith("src/connectors/") or not module_path.endswith(".py"):
        raise RuntimeError(f"unexpected connector module path: {module_path}")
    if not test_path.startswith("tests/test_") or not test_path.endswith("_connector.py"):
        raise RuntimeError(f"unexpected connector test path: {test_path}")
    if not docs_path.startswith("docs/planning/active/source-candidates/") or not docs_path.endswith(
        "_connector_candidate.md"
    ):
        raise RuntimeError(f"unexpected connector docs path: {docs_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-root", required=True)
    parser.add_argument("--local-runtime-root", required=True)
    parser.add_argument("--requested-pipeline-sha", required=True)
    parser.add_argument("--candidate-ids", required=True)
    parser.add_argument("--reviewed-by", default="pipeline_522_connector_artifact_batch")
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    pipeline_root = Path(args.pipeline_root).resolve()
    local_runtime_root = Path(args.local_runtime_root).resolve()
    manifest_path = Path(args.manifest).resolve()
    candidate_ids = parse_candidate_ids(args.candidate_ids)

    observed_sha = git_head(pipeline_root)
    if observed_sha != args.requested_pipeline_sha:
        raise RuntimeError(
            f"Pipeline checkout drift: requested={args.requested_pipeline_sha} observed={observed_sha}"
        )

    sys.path.insert(0, str(pipeline_root))
    os.chdir(pipeline_root)

    from scripts.run_approval_gated_connector_build_agent import (  # noqa: PLC0415
        ApprovalGatedConnectorBuildRepository,
        artifact_files_exist,
        write_connector_artifacts,
    )
    from src.search_intelligence.approval_gated_connector_build import (  # noqa: PLC0415
        evaluate_connector_build_request,
    )

    db_env = parse_env_subset(local_runtime_root / ".env")
    prepared: list[dict[str, Any]] = []
    all_paths: list[str] = []

    with psycopg.connect(
        host=db_env["POSTGRES_HOST"],
        port=int(db_env["POSTGRES_PORT"]),
        dbname=db_env["POSTGRES_DB"],
        user=db_env["POSTGRES_USER"],
        password=db_env["POSTGRES_PASSWORD"],
        connect_timeout=10,
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT current_setting('transaction_read_only') AS read_only")
            if str(cur.fetchone()["read_only"]).lower() not in {"on", "true"}:
                raise RuntimeError("transaction_read_only is not on")

        repo = ApprovalGatedConnectorBuildRepository(conn)
        for candidate_id in candidate_ids:
            candidate = repo.load_candidate(candidate_id=candidate_id, company_key=None)
            gates = repo.load_gates(candidate.candidate_id)
            generation_plan = repo.load_generation_plan(candidate.candidate_id)
            learning_pressure = repo.load_learning_pressure(candidate.candidate_id)
            build_queue_evidence = repo.load_build_queue_evidence(candidate.candidate_id)

            preliminary = evaluate_connector_build_request(
                candidate=candidate,
                gates=gates,
                generation_plan=generation_plan,
                learning_pressure=learning_pressure,
                artifact_files_exist=False,
                approval_provided=True,
                reviewed_by=args.reviewed_by,
                build_queue_evidence=build_queue_evidence,
            )
            if artifact_files_exist(preliminary):
                raise RuntimeError(
                    f"candidate {candidate_id} artifact paths already exist; refusing overwrite"
                )

            request = evaluate_connector_build_request(
                candidate=candidate,
                gates=gates,
                generation_plan=generation_plan,
                learning_pressure=learning_pressure,
                artifact_files_exist=False,
                approval_provided=True,
                reviewed_by=args.reviewed_by,
                build_queue_evidence=build_queue_evidence,
            )
            if request.build_status != "artifact_generation_allowed":
                raise RuntimeError(
                    f"candidate {candidate_id} is not approved for artifact generation: "
                    f"{request.build_status} / {request.reason}"
                )
            if request.artifact_generation_allowed is not True:
                raise RuntimeError(f"candidate {candidate_id} artifact_generation_allowed is false")
            if request.build_mode != EXPECTED_BUILD_MODE:
                raise RuntimeError(
                    f"candidate {candidate_id} unexpected build mode: {request.build_mode}"
                )
            if any(
                bool(request.boundary.get(key))
                for key in (
                    "connector_registration_allowed",
                    "source_activation_allowed",
                    "bronze_persistence_allowed",
                    "recurring_ingestion_allowed",
                    "scheduler_change_allowed",
                    "auto_pr_allowed",
                )
            ):
                raise RuntimeError(f"candidate {candidate_id} build boundary widened unexpectedly")

            paths = path_tuple(request)
            validate_artifact_paths(paths)
            prepared.append(
                {
                    "candidate_id": candidate_id,
                    "company_key": candidate.company_key,
                    "source_name_candidate": candidate.source_name_candidate,
                    "request": request,
                    "gates": gates,
                    "paths": paths,
                }
            )
            all_paths.extend(paths)

        conn.rollback()

    if len(set(all_paths)) != len(all_paths):
        raise RuntimeError("generated artifact path collision detected inside approved batch")

    for item in prepared:
        write_connector_artifacts(item["request"], item["gates"], overwrite=False)

    module_paths = [str(item["paths"][0]) for item in prepared]
    test_paths = [str(item["paths"][1]) for item in prepared]
    for module_path in module_paths:
        checked([sys.executable, "-m", "py_compile", module_path], cwd=pipeline_root)
    checked([sys.executable, "-m", "pytest", "-q", *test_paths], cwd=pipeline_root)

    ruff = Path(sys.executable).with_name("ruff")
    if not ruff.is_file():
        raise RuntimeError("Pipeline virtualenv Ruff executable is missing")
    checked([str(ruff), "check", *module_paths, *test_paths], cwd=pipeline_root)

    manifest = {
        "schema": "pipeline.connector_artifact_batch.v1",
        "pipeline_sha": observed_sha,
        "candidate_ids": list(candidate_ids),
        "candidate_count": len(prepared),
        "generated_paths": all_paths,
        "results": [
            {
                "candidate_id": item["candidate_id"],
                "company_key": item["company_key"],
                "source_name_candidate": item["source_name_candidate"],
                "build_mode": item["request"].build_mode,
                "paths": list(item["paths"]),
            }
            for item in prepared
        ],
        "boundary": {
            "database_read_only": True,
            "database_mutation": False,
            "connector_registration": False,
            "source_activation": False,
            "bronze_persistence": False,
            "recurring_ingestion": False,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
        },
        "validation": {
            "py_compile": "passed",
            "generated_tests": "passed",
            "ruff": "passed",
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"pipeline_sha={observed_sha}")
    print(f"candidate_count={len(prepared)}")
    print("candidate_ids=" + ",".join(str(candidate_id) for candidate_id in candidate_ids))
    print("generated_paths=" + json.dumps(all_paths, ensure_ascii=False))
    print("validation=py_compile:passed,generated_tests:passed,ruff:passed")
    print("database_mutation=0")
    print("connector_registration=0")
    print("source_activation=0")
    print("bronze_persistence=0")
    print("provider_requests=0")
    print("llm_requests=0")
    print("tavily_requests=0")
    print(f"manifest={manifest_path}")


if __name__ == "__main__":
    main()
