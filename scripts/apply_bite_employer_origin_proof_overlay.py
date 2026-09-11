from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlparse

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.connectors.employer_origin_bite_product import prove_one_bite_source
from src.search_intelligence.deterministic_connector_builder import LAYER_ORDER, LayerState, passed

GENERIC_AUTHORITY = "generic_evidence_driven_layer_model"
OVERLAY_SCHEMA = "job_application_pipeline.bite_proof_overlay.v1"


def _url_shape(value: str) -> dict[str, object]:
    parsed = urlparse(value)
    return {
        "scheme": parsed.scheme.casefold(),
        "host": (parsed.hostname or "").casefold(),
        "path": parsed.path or "/",
        "query_keys": sorted({key for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}),
    }


def _layer(row: dict[str, Any], name: str) -> dict[str, Any] | None:
    for item in row.get("layers", []):
        if isinstance(item, dict) and item.get("layer") == name:
            return item
    return None


def _load_persisted_origin(candidate_id: int) -> str:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT candidate_url FROM employer_origin_source_candidates WHERE id = %s",
                (candidate_id,),
            )
            row = cur.fetchone()
    if row is None:
        raise ValueError(f"candidate {candidate_id} is missing")
    value = str(row.get("candidate_url") or "").strip()
    parsed = urlparse(value)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise ValueError(f"candidate {candidate_id} has no valid persisted HTTPS origin")
    return value


def _origin_matches_product(row: dict[str, Any], origin_url: str) -> bool:
    origin = _layer(row, "origin")
    if origin is None or origin.get("state") != "pass":
        return False
    evidence = origin.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("source") != "persisted_candidate_url":
        return False
    shape = evidence.get("candidate_url")
    return isinstance(shape, dict) and shape == _url_shape(origin_url)


def _recompute_summary(payload: dict[str, Any]) -> None:
    results = [item for item in payload.get("results", []) if isinstance(item, dict)]
    first_failures: dict[str, int] = {}
    layer_states: dict[str, dict[str, int]] = {
        layer: {state.value: 0 for state in LayerState} for layer in LAYER_ORDER
    }
    ready = 0
    proof_keys: list[str] = []

    for row in results:
        failure_layer: str | None = None
        proof_pass = False
        recipe_pass = False
        for item in row.get("layers", []):
            if not isinstance(item, dict):
                continue
            layer = str(item.get("layer") or "")
            state = str(item.get("state") or "")
            if layer in layer_states and state in layer_states[layer]:
                layer_states[layer][state] += 1
            if state == "fail" and failure_layer is None:
                failure_layer = layer
            if layer == "proof" and state == "pass":
                proof_pass = True
            if layer == "recipe" and state == "pass":
                recipe_pass = True
        row["first_failure_layer"] = failure_layer
        failure = _layer(row, failure_layer) if failure_layer else None
        row["first_failure_reason"] = failure.get("reason") if failure else None
        row["recipe_ready"] = recipe_pass
        if recipe_pass:
            ready += 1
        if failure_layer:
            first_failures[failure_layer] = first_failures.get(failure_layer, 0) + 1
        if proof_pass:
            proof_keys.append(str(row.get("company_key") or ""))

    total = len(results)
    summary = payload.setdefault("summary", {})
    if not isinstance(summary, dict):
        summary = {}
        payload["summary"] = summary
    summary.update(
        {
            "candidate_count": total,
            "recipe_ready_count": ready,
            "recipe_ready_rate": round(ready / total, 4) if total else 0.0,
            "first_failure_counts": dict(sorted(first_failures.items())),
            "layer_state_counts": layer_states,
            "proof_pass_count": len(proof_keys),
        }
    )
    payload["proof_pass_company_keys"] = proof_keys


def apply_bite_proof_overlay(
    payload: dict[str, Any],
    *,
    origin_loader: Callable[[int], str] = _load_persisted_origin,
    prover=prove_one_bite_source,
) -> list[str]:
    authority = payload.get("authority")
    if not isinstance(authority, dict):
        raise ValueError("generic product authority is missing")
    if authority.get("sole_connector_truth") != GENERIC_AUTHORITY:
        raise ValueError("input is not the canonical generic layer product")
    if authority.get("source_validity_gate") != "proof=PASS":
        raise ValueError("input does not use proof=PASS as source validity gate")

    promoted: list[str] = []
    overlay_results: list[dict[str, object]] = []
    for row in payload.get("results", []):
        if not isinstance(row, dict) or row.get("first_failure_layer") != "proof":
            continue
        candidate_id = int(row["candidate_id"])
        origin_url = origin_loader(candidate_id)
        if not _origin_matches_product(row, origin_url):
            overlay_results.append(
                {
                    "candidate_id": candidate_id,
                    "company_key": row.get("company_key"),
                    "status": "origin_mismatch",
                }
            )
            continue

        proof = prover(origin_url=origin_url)
        if proof is None:
            overlay_results.append(
                {
                    "candidate_id": candidate_id,
                    "company_key": row.get("company_key"),
                    "status": "not_proven",
                }
            )
            continue
        proven_job, inventory = proof

        proof_layer = passed(
            "proof",
            "employer-declared B-ITE tenant inventory yielded a current detail that passes unchanged strict genuine-job proof",
            carrier="employer_declared_bite_tenant",
            provider="bite",
            inventory_count=len(inventory.postings),
            employer_page=_url_shape(inventory.employer_page_url),
            public_detail=_url_shape(proven_job.job.final_url),
            proof_kind=proven_job.job.proof_kind,
        ).to_json()
        recipe_layer = passed(
            "recipe",
            "all evidence-required generic layers passed with bounded B-ITE provider mechanics",
            capability="bite_finite_inventory_raw_detail",
            provider="bite",
        ).to_json()

        layers = row.get("layers")
        if not isinstance(layers, list):
            raise ValueError(f"candidate {candidate_id} has invalid layer payload")
        names = [item.get("layer") if isinstance(item, dict) else None for item in layers]
        if tuple(names) != LAYER_ORDER:
            raise ValueError(f"candidate {candidate_id} layer order mismatch")
        proof_index = LAYER_ORDER.index("proof")
        recipe_index = LAYER_ORDER.index("recipe")
        if layers[proof_index].get("state") != "fail":
            raise ValueError(f"candidate {candidate_id} no longer has proof=FAIL")
        layers[proof_index] = proof_layer
        layers[recipe_index] = recipe_layer
        promoted.append(str(row["company_key"]))
        overlay_results.append(
            {
                "candidate_id": candidate_id,
                "company_key": row.get("company_key"),
                "status": "proof_pass",
                "provider": "bite",
                "inventory_count": len(inventory.postings),
                "public_detail": _url_shape(proven_job.job.final_url),
            }
        )

    _recompute_summary(payload)
    payload["deterministic_proof_overlays"] = {
        "schema": OVERLAY_SCHEMA,
        "authority_unchanged": True,
        "source_validity_gate_unchanged": True,
        "proof_gate": "unchanged_genuine_job_detail_proof",
        "results": overlay_results,
    }
    return promoted


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply strict employer-backed B-ITE proof as a bounded residual inside the canonical generic source product."
    )
    parser.add_argument("--proof-json", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.proof_json.read_text(encoding="utf-8"))
    promoted = apply_bite_proof_overlay(payload)
    args.proof_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"BITE_PROOF_PROMOTED={len(promoted)}")
    for key in promoted:
        print(f"BITE_PROOF_SOURCE={key}")
    print("BITE_PROOF_AUTHORITY=generic_evidence_driven_layer_model")
    print("BITE_PROOF_GATE=unchanged_genuine_job_detail_proof")
    print("DATABASE_WRITES=0")
    print("BITE_PROOF_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
