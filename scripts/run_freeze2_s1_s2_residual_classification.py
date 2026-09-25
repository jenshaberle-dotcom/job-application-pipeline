"""Freeze-II S1/S2 read-only residual classification.

Replays the current deterministic connector layer model and composes the existing
Origin-plan, Inventory-surface/bridge, Detail-surface, and canonical generic
Employer-Origin product proofs into one cohort-selection artifact.

No connector is materialized or activated here.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "job_application_pipeline.freeze2_s1_s2_residual_classification.v1"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def _run(module: str, output: Path, *args: str) -> None:
    command = [sys.executable, "-m", module, *args, "--output", str(output)]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Freeze-II residual audit failed module={module} "
            f"exit={completed.returncode}"
        )
    if not output.is_file():
        raise RuntimeError(f"missing residual audit output: {output}")


def _layer_by_name(row: Mapping[str, Any], layer: str) -> Mapping[str, Any]:
    for item in _rows(row.get("layers")):
        if str(item.get("layer") or "") == layer:
            return item
    return {}


def _provider_hint(row: Mapping[str, Any]) -> str:
    provider = _mapping(_layer_by_name(row, "provider").get("evidence")).get(
        "provider"
    )
    if provider:
        return str(provider)
    delegated = _mapping(_layer_by_name(row, "delegation").get("evidence"))
    provider = delegated.get("provider")
    return str(provider or "unclassified")


def _cohort(layer_payload: Mapping[str, Any], failure: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in _rows(layer_payload.get("results")):
        if str(row.get("first_failure_layer") or "") != failure:
            continue
        result.append(
            {
                "candidate_id": row.get("candidate_id"),
                "company_key": row.get("company_key"),
                "company_name": row.get("company_name"),
                "first_failure_reason": row.get("first_failure_reason"),
                "provider_hint": _provider_hint(row),
            }
        )
    return result


def _group_reason(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        reason = " ".join(str(row.get("first_failure_reason") or "unknown").split())
        counts[reason] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _group_provider(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("provider_hint") or "unclassified") for row in rows)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _remaining_after_product_proof(
    *,
    layer_payload: Mapping[str, Any],
    product_payload: Mapping[str, Any],
) -> dict[str, list[str]]:
    proof_pass = {
        str(value)
        for value in product_payload.get("proof_pass_company_keys", [])
        if value
    }
    remaining: dict[str, list[str]] = defaultdict(list)
    for row in _rows(layer_payload.get("results")):
        failure = str(row.get("first_failure_layer") or "")
        key = str(row.get("company_key") or "")
        if not failure or not key or key in proof_pass:
            continue
        remaining[failure].append(key)
    return {
        layer: sorted(keys)
        for layer, keys in sorted(remaining.items())
    }


def _assert_zero_effects(*payloads: Mapping[str, Any]) -> None:
    forbidden_tokens = (
        "database_writes",
        "connector_materialization",
        "connector_registration",
        "source_activation",
        "bronze_write",
        "silver_write",
        "product_write",
        "query_values_persisted",
    )
    for payload in payloads:
        boundary = _mapping(payload.get("boundary"))
        for key, value in boundary.items():
            if str(key) in forbidden_tokens and value not in (0, False, None):
                raise RuntimeError(
                    f"read-only boundary violation {key}={value!r}"
                )


def build_report(
    *,
    layer: Mapping[str, Any],
    product: Mapping[str, Any],
    origin: Mapping[str, Any],
    inventory: Mapping[str, Any],
    bridge: Mapping[str, Any],
    detail: Mapping[str, Any],
) -> dict[str, Any]:
    _assert_zero_effects(layer, product, origin, inventory, bridge, detail)

    cohorts = {
        failure: _cohort(layer, failure)
        for failure in (
            "origin",
            "origin_reachability",
            "inventory",
            "detail",
            "proof",
        )
    }
    product_summary = _mapping(product.get("summary"))
    origin_summary = _mapping(origin.get("summary"))
    inventory_summary = _mapping(inventory.get("summary"))
    bridge_summary = _mapping(bridge.get("summary"))
    detail_summary = _mapping(detail.get("summary"))

    return {
        "schema": SCHEMA,
        "mode": "read_only",
        "campaign": "FREEZE-II Source Truth & Connector Reliability",
        "slice": "S1/S2 residual classification",
        "authority": {
            "connector_materialization": False,
            "source_activation": False,
            "product_coverage_change": False,
            "diagnostic_recipe_ready_is_product_coverage": False,
        },
        "current_generic_product": {
            "candidate_count": int(product_summary.get("candidate_count") or 0),
            "proof_pass_count": int(product_summary.get("proof_pass_count") or 0),
            "proof_pass_company_keys": sorted(
                str(value)
                for value in product.get("proof_pass_company_keys", [])
                if value
            ),
        },
        "residual_cohorts": {
            failure: {
                "count": len(rows),
                "reason_counts": _group_reason(rows),
                "provider_hint_counts": _group_provider(rows),
                "rows": rows,
            }
            for failure, rows in cohorts.items()
        },
        "origin_plan": {
            "summary": dict(origin_summary),
            "results": _rows(origin.get("results")),
        },
        "inventory_surface": {
            "summary": dict(inventory_summary),
            "results": _rows(inventory.get("results")),
        },
        "inventory_bridge": {
            "summary": dict(bridge_summary),
            "results": _rows(bridge.get("results")),
        },
        "detail_surface": {
            "summary": dict(detail_summary),
            "results": _rows(detail.get("results")),
        },
        "remaining_after_canonical_generic_product_proof": (
            _remaining_after_product_proof(
                layer_payload=layer,
                product_payload=product,
            )
        ),
        "selection_rule": (
            "Choose a reusable deterministic class by current population lift, "
            "evidence strength, source-family reuse and metadata benefit. "
            "Never choose by named-employer convenience."
        ),
        "boundaries": {
            "database_writes": 0,
            "connector_materialization": 0,
            "connector_registration": 0,
            "source_activation": 0,
            "bronze_writes": 0,
            "silver_writes": 0,
            "product_writes": 0,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/jap-freeze2-s1-s2"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    layer_path = root / "connector-v6.json"
    product_path = root / "generic-product.json"
    origin_path = root / "origin-plan.json"
    inventory_path = root / "inventory-surface.json"
    bridge_path = root / "inventory-bridge.json"
    detail_path = root / "detail-surface.json"

    _run(
        "scripts.run_deterministic_connector_builder_layer_audit_v6",
        layer_path,
        "--sleep-seconds",
        "0.01",
    )
    _run(
        "scripts.run_generic_employer_origin_product",
        product_path,
        "--sleep-seconds",
        "0.01",
    )
    _run(
        "scripts.run_deterministic_origin_plan_audit",
        origin_path,
        "--layer-audit",
        str(layer_path),
    )
    _run(
        "scripts.run_deterministic_inventory_surface_audit",
        inventory_path,
        "--layer-audit",
        str(layer_path),
    )
    _run(
        "scripts.run_deterministic_inventory_bridge_audit",
        bridge_path,
        "--layer-audit",
        str(layer_path),
        "--surface-audit",
        str(inventory_path),
    )
    _run(
        "scripts.run_deterministic_detail_surface_audit",
        detail_path,
        "--layer-audit",
        str(layer_path),
    )

    report = build_report(
        layer=_read(layer_path),
        product=_read(product_path),
        origin=_read(origin_path),
        inventory=_read(inventory_path),
        bridge=_read(bridge_path),
        detail=_read(detail_path),
    )
    output = (
        args.output or root / "freeze2-s1-s2-residual-classification.json"
    ).resolve()
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("============================================")
    print("FREEZE-II S1/S2 RESIDUAL CLASSIFICATION")
    print("============================================")
    product = report["current_generic_product"]
    print(f"CURRENT_CANDIDATES={product['candidate_count']}")
    print(f"CURRENT_GENERIC_PROOF_PASS={product['proof_pass_count']}")
    for failure, payload in report["residual_cohorts"].items():
        print(f"RESIDUAL_{failure.upper()}={payload['count']}")
        print(
            f"RESIDUAL_{failure.upper()}_REASONS="
            + json.dumps(payload["reason_counts"], sort_keys=True)
        )
        print(
            f"RESIDUAL_{failure.upper()}_PROVIDERS="
            + json.dumps(payload["provider_hint_counts"], sort_keys=True)
        )
    print(
        "ORIGIN_PLAN_CLASSIFICATIONS="
        + json.dumps(
            report["origin_plan"]["summary"].get("classification_counts", {}),
            sort_keys=True,
        )
    )
    print(
        "INVENTORY_CLASSIFICATIONS="
        + json.dumps(
            report["inventory_surface"]["summary"].get(
                "primary_classification_counts", {}
            ),
            sort_keys=True,
        )
    )
    print(
        "INVENTORY_BRIDGE_HYPOTHESES="
        + json.dumps(
            report["inventory_bridge"]["summary"].get("hypothesis_counts", {}),
            sort_keys=True,
        )
    )
    print(
        "DETAIL_CLASSIFICATIONS="
        + json.dumps(
            report["detail_surface"]["summary"].get("classification_counts", {}),
            sort_keys=True,
        )
    )
    print(
        "REMAINING_AFTER_PRODUCT_PROOF="
        + json.dumps(
            report["remaining_after_canonical_generic_product_proof"],
            sort_keys=True,
        )
    )
    print("DATABASE_WRITES=0")
    print("SOURCE_ACTIVATION=0")
    print("CONNECTOR_MATERIALIZATION=0")
    print(f"artifact={output}")
    print("FREEZE2_S1_S2_RESIDUAL_CLASSIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
