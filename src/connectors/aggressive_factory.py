"""Aggressive Connector Factory policy for the Classic factory lab.

Aggressive means every evidence-bearing candidate is advanced deterministically as far
as possible. It does not mean guessing evidence, activating sources, or generating
employer-specific Python by default.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from src.connectors.connector_factory import (
    CandidateConnectorEvidence,
    ConnectorCapabilityRole,
    capabilities_from_catalog,
    compile_connector_recipe,
    connector_factory_evidence_records,
    qualify_connector_recipe,
)


def advance_candidate(
    source: dict[str, object],
    *,
    catalog_payload: dict[str, object],
    census_digest: str,
) -> dict[str, object]:
    """Advance one candidate to the strongest safe factory state."""
    key = str(source.get("company_key") or "").strip().casefold()
    if not key:
        raise ValueError("candidate_company_key_required")
    evidence_ids = source.get("evidence_ids")
    tags = source.get("fingerprint_tags")
    if not isinstance(evidence_ids, list) or not evidence_ids:
        return _gap(key, "evidence_gap", "candidate_evidence_required")
    if not isinstance(tags, list) or not tags:
        return _gap(key, "evidence_gap", "origin_fingerprint_required")

    evidence = CandidateConnectorEvidence(
        candidate_key=f"candidate:{key}",
        company_key=key,
        origin_url=str(source.get("origin_url") or ""),
        source_type=str(source.get("source_type") or ""),
        required_roles=(
            ConnectorCapabilityRole.ORIGIN_INVENTORY,
            ConnectorCapabilityRole.JOB_DETAIL,
        ),
        fingerprint_tags=tuple(str(v) for v in tags),
        evidence_ids=tuple(str(v) for v in evidence_ids) + (f"census:{census_digest}",),
        market_sensor_only=source.get("market_sensor_only") is not False,
    )
    capabilities = capabilities_from_catalog(catalog_payload)
    compiled = compile_connector_recipe(evidence, capabilities)
    result: dict[str, object] = {
        "company_key": key,
        "factory_disposition": compiled.disposition.value,
        "reason": compiled.reason,
        "missing_roles": [v.value for v in compiled.missing_roles],
        "fingerprint_tags": sorted(set(str(v) for v in tags)),
        "employer_specific_code_required": False,
        "runtime_admitted": False,
        "production_activated": False,
    }
    if compiled.recipe is None:
        result["engineering_gap"] = _engineering_gap(result)
        return result

    proof = qualify_connector_recipe(compiled.recipe, capabilities)
    result.update(
        recipe_id=compiled.recipe.recipe_id,
        capability_ids=sorted({v.capability_id for v in compiled.recipe.bindings}),
        definition_status=proof.status,
        qualification_proof_id=proof.proof_id,
    )
    if proof.status != "PASS":
        result.update(factory_disposition="qualification_gap", reason=",".join(proof.blockers))
        result["engineering_gap"] = _engineering_gap(result)
        return result

    result.update(
        factory_disposition="qualified_inactive",
        reason="definition_qualified_runtime_evidence_pending",
        persistable_definition=connector_factory_evidence_records(compiled.recipe, proof),
    )
    return result


def advance_population(
    sources: Iterable[dict[str, object]],
    *,
    catalog_payload: dict[str, object],
    census_digest: str,
) -> dict[str, object]:
    rows = [
        advance_candidate(source, catalog_payload=catalog_payload, census_digest=census_digest)
        for source in sources
    ]
    rows.sort(key=lambda row: str(row["company_key"]))
    counts: dict[str, int] = {}
    gaps: dict[str, dict[str, object]] = {}
    for row in rows:
        disposition = str(row["factory_disposition"])
        counts[disposition] = counts.get(disposition, 0) + 1
        gap = row.get("engineering_gap")
        if isinstance(gap, dict):
            fingerprint = str(gap["fingerprint"])
            group = gaps.setdefault(fingerprint, {**gap, "candidate_keys": []})
            group["candidate_keys"].append(row["company_key"])
    return {
        "schema_version": "jap.aggressive_connector_factory_run.v1",
        "policy": "ADVANCE_EVERY_EVIDENCED_CANDIDATE_TO_MAX_SAFE_STATE",
        "candidate_count": len(rows),
        "disposition_counts": dict(sorted(counts.items())),
        "engineering_gap_groups": dict(sorted(gaps.items())),
        "candidates": rows,
        "boundaries": {
            "guessing_evidence": False,
            "employer_specific_code_default": False,
            "runtime_activation": False,
            "production_activation": False,
        },
    }


def _gap(key: str, disposition: str, reason: str) -> dict[str, object]:
    row: dict[str, object] = {
        "company_key": key,
        "factory_disposition": disposition,
        "reason": reason,
        "employer_specific_code_required": False,
        "runtime_admitted": False,
        "production_activated": False,
    }
    row["engineering_gap"] = _engineering_gap(row)
    return row


def _engineering_gap(row: dict[str, object]) -> dict[str, object]:
    import hashlib
    import json

    signature = {
        "disposition": row.get("factory_disposition"),
        "reason": row.get("reason"),
        "missing_roles": row.get("missing_roles", []),
        "fingerprint_tags": row.get("fingerprint_tags", []),
        "capability_ids": row.get("capability_ids", []),
    }
    fingerprint = hashlib.sha256(
        json.dumps(signature, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {"fingerprint": fingerprint, **signature}
