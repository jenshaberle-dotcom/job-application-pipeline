from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row


DB_ENV_KEYS = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)
ALLOWED_SOURCE_TYPES = {
    "employer_origin_career_site",
    "employer_origin_ats_backed_career_site",
}


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


def git_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.strip()


def valid_origin_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def existing_connector_class(path: Path) -> str | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return None
    connector_classes = [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name.endswith("Connector")
    ]
    return connector_classes[0] if connector_classes else None


def run_checked(command: list[str], *, cwd: Path, timeout: int = 300) -> tuple[bool, str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    return completed.returncode == 0, output[-1500:]


def cleanup_generated(paths: tuple[Path, Path, Path]) -> None:
    for path in paths:
        if path.is_file():
            path.unlink()


def synthetic_cluster0_spec(candidate: Any, paths: tuple[str, str, str]) -> dict[str, Any]:
    module_path, test_path, docs_path = paths
    return {
        "build_mode": "bottom_up_cluster0_connector_creation",
        "recommended_connector": {
            "module_path": module_path,
            "test_path": test_path,
            "docs_path": docs_path,
        },
        "origin_source": {
            "candidate_url": candidate.candidate_url,
            "company_key": candidate.company_key,
        },
        "detail_evidence": {
            "detail_urls": [],
            "cluster0_note": "detail evidence is intentionally deferred to higher bottom-up clusters",
        },
        "boundary": {
            "cluster": 0,
            "network_execution_allowed": False,
            "connector_registration_allowed": False,
            "source_activation_allowed": False,
            "bronze_persistence_allowed": False,
            "recurring_ingestion_allowed": False,
        },
    }


def result(
    candidate: Any,
    *,
    state: str,
    cause: str | None,
    module_path: str | None,
    test_path: str | None,
    docs_path: str | None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate.id,
        "company_key": candidate.company_key,
        "source_name_candidate": candidate.source_name_candidate,
        "source_family_candidate": candidate.source_family_candidate,
        "source_type_candidate": candidate.source_type_candidate,
        "state": state,
        "cause": cause,
        "paths": {
            "module": module_path,
            "test": test_path,
            "docs": docs_path,
        },
        "evidence": evidence or {},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bottom-up Cluster 0: create bounded connector artifacts for every employer-origin candidate that has no connector module."
    )
    parser.add_argument("--pipeline-root", required=True)
    parser.add_argument("--local-runtime-root", required=True)
    parser.add_argument("--requested-pipeline-sha", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    pipeline_root = Path(args.pipeline_root).resolve()
    local_runtime_root = Path(args.local_runtime_root).resolve()
    manifest_path = Path(args.manifest).resolve()

    observed_sha = git_head(pipeline_root)
    if observed_sha != args.requested_pipeline_sha:
        raise RuntimeError(
            f"Pipeline checkout drift: requested={args.requested_pipeline_sha} observed={observed_sha}"
        )

    sys.path.insert(0, str(pipeline_root))
    os.chdir(pipeline_root)

    from scripts.run_employer_origin_connector_artifact_generator import (  # noqa: PLC0415
        SourceCandidate,
        build_implementation,
        module_name_for,
        write_files,
    )

    db_env = parse_env_subset(local_runtime_root / ".env")
    candidates: list[Any] = []

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
            cur.execute(
                """
                select
                    id,
                    company_key,
                    company_name,
                    candidate_url,
                    source_name_candidate,
                    source_family_candidate,
                    source_target_candidate,
                    source_type_candidate,
                    status,
                    risk_level
                from employer_origin_source_candidates
                order by id
                """
            )
            rows = cur.fetchall()

        for row in rows:
            candidates.append(
                SourceCandidate(
                    id=int(row["id"]),
                    company_key=str(row["company_key"]),
                    company_name=str(row["company_name"]),
                    candidate_url=str(row["candidate_url"] or ""),
                    source_name_candidate=str(row["source_name_candidate"]),
                    source_family_candidate=str(row["source_family_candidate"] or row["company_key"]),
                    source_target_candidate=row.get("source_target_candidate"),
                    source_type_candidate=str(row["source_type_candidate"]),
                    status=str(row["status"]),
                    risk_level=str(row["risk_level"]),
                )
            )
        conn.rollback()

    desired_modules: dict[str, list[int]] = {}
    for candidate in candidates:
        module_name = module_name_for(candidate)
        module_path = f"src/connectors/{module_name}.py" if module_name else ""
        desired_modules.setdefault(module_path, []).append(candidate.id)

    outcomes: list[dict[str, Any]] = []
    generated_paths: list[str] = []
    ruff = Path(sys.executable).with_name("ruff")
    if not ruff.is_file():
        raise RuntimeError("Pipeline virtualenv Ruff executable is missing")

    for candidate in candidates:
        module_name = module_name_for(candidate)
        module_rel = f"src/connectors/{module_name}.py" if module_name else None
        test_rel = f"tests/test_{module_name}_connector.py" if module_name else None
        docs_rel = (
            f"docs/planning/active/source-candidates/{module_name}_connector_candidate.md"
            if module_name
            else None
        )

        if not module_name:
            outcomes.append(
                result(
                    candidate,
                    state="blocked",
                    cause="invalid_connector_identity",
                    module_path=module_rel,
                    test_path=test_rel,
                    docs_path=docs_rel,
                )
            )
            continue

        module_path = pipeline_root / module_rel
        test_path = pipeline_root / test_rel
        docs_path = pipeline_root / docs_rel

        if module_path.is_file():
            connector_class = existing_connector_class(module_path)
            if connector_class is None:
                outcomes.append(
                    result(
                        candidate,
                        state="blocked",
                        cause="existing_module_is_not_connector",
                        module_path=module_rel,
                        test_path=test_rel,
                        docs_path=docs_rel,
                    )
                )
            else:
                outcomes.append(
                    result(
                        candidate,
                        state="already_exists",
                        cause=None,
                        module_path=module_rel,
                        test_path=test_rel,
                        docs_path=docs_rel,
                        evidence={
                            "connector_class": connector_class,
                            "test_exists": test_path.is_file(),
                            "docs_exists": docs_path.is_file(),
                        },
                    )
                )
            continue

        if len(desired_modules.get(module_rel, [])) > 1:
            outcomes.append(
                result(
                    candidate,
                    state="blocked",
                    cause="shared_missing_connector_family",
                    module_path=module_rel,
                    test_path=test_rel,
                    docs_path=docs_rel,
                    evidence={"candidate_ids": desired_modules[module_rel]},
                )
            )
            continue

        if candidate.source_type_candidate not in ALLOWED_SOURCE_TYPES:
            outcomes.append(
                result(
                    candidate,
                    state="blocked",
                    cause="unsupported_source_type",
                    module_path=module_rel,
                    test_path=test_rel,
                    docs_path=docs_rel,
                )
            )
            continue

        if not valid_origin_url(candidate.candidate_url):
            outcomes.append(
                result(
                    candidate,
                    state="blocked",
                    cause="invalid_origin_url",
                    module_path=module_rel,
                    test_path=test_rel,
                    docs_path=docs_rel,
                    evidence={"candidate_url": candidate.candidate_url},
                )
            )
            continue

        support_collisions = [
            path
            for path in (test_path, docs_path)
            if path.exists()
        ]
        if support_collisions:
            outcomes.append(
                result(
                    candidate,
                    state="blocked",
                    cause="support_artifact_path_collision",
                    module_path=module_rel,
                    test_path=test_rel,
                    docs_path=docs_rel,
                    evidence={
                        "existing_paths": [str(path.relative_to(pipeline_root)) for path in support_collisions]
                    },
                )
            )
            continue

        paths = (module_rel, test_rel, docs_rel)
        spec = synthetic_cluster0_spec(candidate, paths)
        implementation = build_implementation(
            candidate,
            {"evidence": {"connector_candidate_spec": spec}},
        )
        generated = (
            pipeline_root / implementation.module_path,
            pipeline_root / implementation.test_path,
            pipeline_root / implementation.docs_path,
        )

        try:
            write_files(implementation, overwrite=False)
            checks = (
                ("py_compile", [sys.executable, "-m", "py_compile", module_rel]),
                ("generated_test", [sys.executable, "-m", "pytest", "-q", test_rel]),
                ("ruff", [str(ruff), "check", module_rel, test_rel]),
            )
            failed: tuple[str, str] | None = None
            for check_name, command in checks:
                ok, output = run_checked(command, cwd=pipeline_root)
                if not ok:
                    failed = (check_name, output)
                    break
            if failed is not None:
                cleanup_generated(generated)
                outcomes.append(
                    result(
                        candidate,
                        state="blocked",
                        cause="generated_validation_failure",
                        module_path=module_rel,
                        test_path=test_rel,
                        docs_path=docs_rel,
                        evidence={"check": failed[0], "output_tail": failed[1]},
                    )
                )
                continue
        except Exception as exc:  # candidate-level failure must become evidence, not stop the cohort
            cleanup_generated(generated)
            outcomes.append(
                result(
                    candidate,
                    state="blocked",
                    cause="generation_exception",
                    module_path=module_rel,
                    test_path=test_rel,
                    docs_path=docs_rel,
                    evidence={"exception": f"{type(exc).__name__}: {exc}"[:1500]},
                )
            )
            continue

        candidate_generated_paths = [module_rel, test_rel, docs_rel]
        generated_paths.extend(candidate_generated_paths)
        outcomes.append(
            result(
                candidate,
                state="created",
                cause=None,
                module_path=module_rel,
                test_path=test_rel,
                docs_path=docs_rel,
                evidence={
                    "validation": {
                        "py_compile": "passed",
                        "generated_test": "passed",
                        "ruff": "passed",
                    },
                    "network_execution": False,
                },
            )
        )

    counts = Counter(item["state"] for item in outcomes)
    blocked_causes = Counter(
        str(item["cause"])
        for item in outcomes
        if item["state"] == "blocked"
    )
    cluster0_closed = counts.get("blocked", 0) == 0

    manifest = {
        "schema": "pipeline.bottom_up_connector_cluster0.v1",
        "pipeline_sha": observed_sha,
        "candidate_count": len(candidates),
        "counts": dict(sorted(counts.items())),
        "blocked_causes": dict(sorted(blocked_causes.items())),
        "cluster0_closed": cluster0_closed,
        "generated_paths": generated_paths,
        "results": outcomes,
        "boundary": {
            "database_read_only": True,
            "database_mutation": False,
            "network_requests": 0,
            "connector_execution": False,
            "connector_registration": False,
            "source_activation": False,
            "bronze_persistence": False,
            "recurring_ingestion": False,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"pipeline_sha={observed_sha}")
    print(f"candidate_count={len(candidates)}")
    print("cluster0_counts=" + json.dumps(dict(sorted(counts.items())), sort_keys=True))
    print("cluster0_blocked_causes=" + json.dumps(dict(sorted(blocked_causes.items())), sort_keys=True))
    print(f"cluster0_closed={str(cluster0_closed).lower()}")
    for item in outcomes:
        print("cluster0_result=" + json.dumps(item, ensure_ascii=False, sort_keys=True))
    print("generated_paths=" + json.dumps(generated_paths, ensure_ascii=False))
    print("database_mutation=0")
    print("network_requests=0")
    print("connector_execution=0")
    print("connector_registration=0")
    print("source_activation=0")
    print("bronze_persistence=0")
    print("provider_requests=0")
    print("llm_requests=0")
    print("tavily_requests=0")
    print(f"manifest={manifest_path}")


if __name__ == "__main__":
    main()
