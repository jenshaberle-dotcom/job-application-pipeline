#!/usr/bin/env python3
"""Fail-closed repository-identity guard for Pipeline re-entry."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any

IDENTITY_PATH = Path("docs/current/REPOSITORY-IDENTITY.json")
EXPECTED_SCHEMA = "reentry.repository_identity.v1"


class IdentityError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise IdentityError(f"{path} must contain a JSON object")
    return value


def validate_static(root: Path, identity: dict[str, Any]) -> None:
    if identity.get("schema") != EXPECTED_SCHEMA:
        raise IdentityError("REPOSITORY_IDENTITY_UNVERIFIED: unsupported identity schema")
    target = identity.get("execution_target")
    binding = identity.get("reentry_binding")
    relationships = identity.get("relationship_policy")
    if not all(isinstance(value, dict) for value in (target, binding, relationships)):
        raise IdentityError("REENTRY_CONTRACT_UNBOUND: required identity objects are missing")
    repository_id = target.get("repository_id")
    canonical_name = target.get("canonical_name")
    if not isinstance(repository_id, int) or repository_id <= 0:
        raise IdentityError("REPOSITORY_IDENTITY_UNVERIFIED: repository_id must be positive")
    if not isinstance(canonical_name, str) or "/" not in canonical_name:
        raise IdentityError("REPOSITORY_IDENTITY_UNVERIFIED: canonical_name must be owner/repository")
    if binding.get("bound_repository_id") != repository_id:
        raise IdentityError("REENTRY_CONTRACT_TARGET_MISMATCH: contract binding differs from target")
    contract_paths = binding.get("contract_paths")
    if not isinstance(contract_paths, list) or not contract_paths:
        raise IdentityError("REENTRY_CONTRACT_UNBOUND: contract_paths must be non-empty")
    root = root.resolve()
    for raw_path in contract_paths:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise IdentityError("REENTRY_CONTRACT_UNBOUND: invalid contract path")
        normalized = Path(raw_path).as_posix()
        candidate = (root / Path(normalized)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise IdentityError("REENTRY_CONTRACT_UNBOUND: contract path escapes repository") from exc
        if not candidate.is_file():
            raise IdentityError(f"REENTRY_CONTRACT_UNBOUND: missing contract path {normalized}")
    if relationships.get("execution_target_is_not_inferred_from_relationships") is not True:
        raise IdentityError("REENTRY_CONTRACT_UNBOUND: relationships may not select target")
    if relationships.get("authority_source_does_not_become_execution_target") is not True:
        raise IdentityError("REENTRY_CONTRACT_UNBOUND: authority-source separation missing")
    related = relationships.get("related_repositories")
    if not isinstance(related, list):
        raise IdentityError("REPOSITORY_IDENTITY_UNVERIFIED: related_repositories must be a list")
    for relation in related:
        if not isinstance(relation, dict) or not isinstance(relation.get("repository_id"), int):
            raise IdentityError("REPOSITORY_IDENTITY_UNVERIFIED: invalid related repository")
        if relation["repository_id"] == repository_id:
            raise IdentityError("REPOSITORY_IDENTITY_UNVERIFIED: target duplicated as related repository")
        if relation.get("may_supply_reentry_authority") is True or relation.get("may_be_mutation_target") is True:
            raise IdentityError("REENTRY_CONTRACT_UNBOUND: related repository crosses target boundary")


def classify_live(identity: dict[str, Any], live_repository_id: str | int | None, live_repository: str | None) -> str:
    target = identity["execution_target"]
    if live_repository_id is None or str(live_repository_id).strip() == "":
        raise IdentityError("REPOSITORY_IDENTITY_UNVERIFIED: live repository id is required")
    try:
        live_id = int(str(live_repository_id))
    except ValueError as exc:
        raise IdentityError("REPOSITORY_IDENTITY_UNVERIFIED: live repository id is not numeric") from exc
    if live_id != target["repository_id"]:
        related_ids = {item["repository_id"] for item in identity["relationship_policy"]["related_repositories"]}
        if live_id in related_ids:
            raise IdentityError("RELATED_REPOSITORY_NOT_EXECUTION_TARGET")
        raise IdentityError("REENTRY_CONTRACT_TARGET_MISMATCH")
    if live_repository and live_repository != target["canonical_name"]:
        return "REPOSITORY_NAME_DRIFT"
    return "IDENTITY_VERIFIED"


def run_self_test(root: Path, identity: dict[str, Any]) -> None:
    validate_static(root, identity)
    target = identity["execution_target"]
    assert classify_live(identity, target["repository_id"], target["canonical_name"]) == "IDENTITY_VERIFIED"
    assert classify_live(identity, target["repository_id"], "renamed/repository") == "REPOSITORY_NAME_DRIFT"
    wrong = copy.deepcopy(identity)
    wrong["reentry_binding"]["bound_repository_id"] = 999
    try:
        validate_static(root, wrong)
    except IdentityError as exc:
        assert "REENTRY_CONTRACT_TARGET_MISMATCH" in str(exc)
    else:
        raise AssertionError("wrong contract binding was accepted")
    related = identity["relationship_policy"]["related_repositories"][0]
    try:
        classify_live(identity, related["repository_id"], related["canonical_name"])
    except IdentityError as exc:
        assert str(exc) == "RELATED_REPOSITORY_NOT_EXECUTION_TARGET"
    else:
        raise AssertionError("related repository was accepted as execution target")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--live-repository-id", default=os.getenv("GITHUB_REPOSITORY_ID"))
    parser.add_argument("--live-repository", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    identity = load_json(root / IDENTITY_PATH)
    validate_static(root, identity)
    if args.self_test:
        run_self_test(root, identity)
    if args.static_only:
        print("REENTRY_IDENTITY_STATIC_OK")
        return 0
    print(classify_live(identity, args.live_repository_id, args.live_repository))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except IdentityError as exc:
        print(str(exc))
        raise SystemExit(1)
