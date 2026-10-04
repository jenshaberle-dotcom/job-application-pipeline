from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Iterable

from src.connectors.aggressive_factory import advance_candidate
from src.connectors.connector_factory import ConnectorFactoryCapability, capabilities_from_catalog


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

    # Compatibility projection over the single canonical Factory policy.
    row = advance_candidate(
        {
            "company_key": candidate.company_key,
            "origin_url": candidate.origin_url,
            "source_type": candidate.source_type,
            "fingerprint_tags": list(candidate.fingerprint_tags),
            "evidence_ids": list(candidate.evidence_ids),
            "market_sensor_only": False,
        },
        catalog_payload={
            "schema_version": "jap.connector_capability_catalog.v1",
            "capabilities": [
                {
                    **asdict(capability),
                    "roles": [role.value for role in capability.roles],
                    "reuse_tier": capability.reuse_tier.name,
                    "required_fingerprint_tags": list(capability.required_fingerprint_tags),
                }
                for capability in capabilities
            ],
        },
        census_digest=_digest(candidate.company_key),
    )
    disposition = row.pop("factory_disposition")
    reason = row.pop("reason")
    return {
        **base,
        **row,
        "disposition": "recipe_ready" if disposition == "qualified_inactive" else disposition,
        "blocker": "execution_evidence_required" if disposition == "qualified_inactive" else reason,
        "qualification_status": row.get("definition_status"),
    }


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
