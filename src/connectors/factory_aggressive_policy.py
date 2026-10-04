from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Iterable

from src.connectors.factory_core import (
    CandidateConnectorEvidence,
    ConnectorCapabilityRole,
    ConnectorFactoryCapability,
    capabilities_from_catalog,
    compile_connector_recipe,
    qualify_connector_recipe,
)

POLICY_SCHEMA_VERSION = "jap.connector_factory_aggressive_policy.v1"


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class FactoryCandidate:
    company_key: str
    company_name: str
    cohort: str
    origin_url: str | None
    source_type: str | None
    fingerprint_tags: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    origin_verified: bool = False


def evaluate_candidate(
    candidate: FactoryCandidate,
    capabilities: tuple[ConnectorFactoryCapability, ...],
) -> dict[str, object]:
    base = {
        "company_key": candidate.company_key,
        "company_name": candidate.company_name,
        "cohort": candidate.cohort,
        "fingerprint_tags": sorted(set(candidate.fingerprint_tags)),
        "disposition": "evidence_gap",
        "blocker": "verified_employer_origin_required",
        "creation_policy": "AGGRESSIVE_GENERIC_FIRST",
    }
    if not candidate.origin_verified or not candidate.origin_url or not candidate.source_type:
        return base

    evidence = CandidateConnectorEvidence(
        candidate_key=f"candidate:{candidate.company_key}",
        company_key=candidate.company_key,
        origin_url=candidate.origin_url,
        source_type=candidate.source_type,
        required_roles=(
            ConnectorCapabilityRole.ORIGIN_INVENTORY,
            ConnectorCapabilityRole.JOB_DETAIL,
        ),
        fingerprint_tags=candidate.fingerprint_tags,
        evidence_ids=candidate.evidence_ids,
        market_sensor_only=False,
    )
    result = compile_connector_recipe(evidence, capabilities)
    row = {
        **base,
        "disposition": result.disposition.value,
        "blocker": result.reason,
        "missing_roles": [role.value for role in result.missing_roles],
    }
    if result.recipe is None:
        return row

    proof = qualify_connector_recipe(result.recipe, capabilities)
    row.update(
        recipe_id=result.recipe.recipe_id,
        capability_ids=sorted({b.capability_id for b in result.recipe.bindings}),
        qualification_status=proof.status,
        qualification_proof_id=proof.proof_id,
    )
    if proof.status != "PASS":
        row.update(disposition="qualification_gap", blocker=",".join(proof.blockers))
    else:
        row.update(disposition="recipe_ready", blocker="execution_evidence_required")
    return row


def evaluate_population(
    candidates: Iterable[FactoryCandidate],
    catalog_payload: dict[str, object],
) -> dict[str, object]:
    capabilities = capabilities_from_catalog(catalog_payload)
    rows = [evaluate_candidate(item, capabilities) for item in candidates]
    rows.sort(key=lambda item: str(item["company_key"]))

    counts = dict(sorted(Counter(str(row["disposition"]) for row in rows).items()))
    groups: dict[str, dict[str, object]] = {}
    for row in rows:
        if row["disposition"] not in {"evidence_gap", "capability_gap", "qualification_gap"}:
            continue
        signature = {
            "disposition": row["disposition"],
            "blocker": row["blocker"],
            "fingerprint_tags": row.get("fingerprint_tags", []),
            "missing_roles": row.get("missing_roles", []),
        }
        group_id = _digest(signature)
        group = groups.setdefault(
            group_id,
            {
                "group_id": group_id,
                **signature,
                "candidate_keys": [],
                "population_impact": 0,
                "next_action": (
                    "ACQUIRE_ORIGIN_EVIDENCE"
                    if row["disposition"] == "evidence_gap"
                    else "BUILD_OR_EXTEND_GENERIC_CAPABILITY"
                    if row["disposition"] == "capability_gap"
                    else "REPAIR_GENERIC_QUALIFICATION"
                ),
                "employer_specific_code_allowed": False,
            },
        )
        group["candidate_keys"].append(row["company_key"])
        group["population_impact"] = int(group["population_impact"]) + 1

    engineering_queue = sorted(
        groups.values(),
        key=lambda item: (-int(item["population_impact"]), str(item["group_id"])),
    )
    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "policy": {
            "mode": "AGGRESSIVE_GENERIC_FIRST",
            "process_every_candidate": True,
            "silent_drop_allowed": False,
            "auto_recipe_when_representable": True,
            "auto_engineering_candidate_on_gap": True,
            "employer_specific_code_default": "FORBIDDEN",
            "priority": "POPULATION_IMPACT_THEN_STABLE_FINGERPRINT",
        },
        "candidate_count": len(rows),
        "disposition_counts": counts,
        "engineering_queue": engineering_queue,
        "candidates": rows,
        "population_digest": _digest(rows),
    }
