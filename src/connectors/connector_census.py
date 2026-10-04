"""Evaluate a fresh or historical population without effects or source activation."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict

from src.connectors.connector_extraction import (
    AcquisitionResponse,
    ExtractedJob,
    ExtractionPlan,
    digest,
    fingerprint_saved_responses,
    qualify_extraction,
)
from src.connectors.connector_factory import (
    CandidateConnectorEvidence,
    ConnectorCapabilityRole,
    capabilities_from_catalog,
    compile_connector_recipe,
    connector_factory_evidence_records,
    qualify_connector_recipe,
)

CENSUS_SCHEMA = "jap.current_employer_connector_census.v1"
FRESH_POPULATION_SCHEMA = "jap_cloud.fresh_connector_population.v1"
EVIDENCE_SCHEMA = "jap.connector_candidate_evidence.v1"


def _key(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("candidate_company_key_required")
    return " ".join(value.split()).casefold()


def _plan(payload: dict, recipe_id: str) -> ExtractionPlan:
    value = dict(payload)
    if "recipe_id" in value and value["recipe_id"] != recipe_id:
        raise ValueError("execution_recipe_binding_mismatch")
    value["recipe_id"] = recipe_id
    for field in (
        "authorized_origins",
        "records_path",
        "id_path",
        "title_path",
        "url_path",
        "description_path",
        "locations_path",
    ):
        if field in value:
            if not isinstance(value[field], list) or any(
                not isinstance(item, str) for item in value[field]
            ):
                raise ValueError("execution_plan_list_invalid")
            value[field] = tuple(value[field])
    if "html_fields" in value:
        value["html_fields"] = tuple(tuple(item) for item in value["html_fields"])
    return ExtractionPlan(**value)


def evaluate_connector_census(
    census: dict, catalog_payload: dict, evidence_bundle: dict | None = None
) -> dict:
    fresh = census.get("schema_version") == FRESH_POPULATION_SCHEMA
    if not fresh and census.get("schema_version") != CENSUS_SCHEMA:
        raise ValueError("current_employer_census_required")
    population_authority = (
        "fresh_profile_driven_discovery_by_company_key"
        if fresh else "latest_distinct_employer_origin_source_candidates_by_company_key"
    )
    if (
        census.get("summary", {}).get("candidate_population_authority")
        != population_authority
        or census.get("boundaries", {}).get("market_sensors_excluded") is not True
    ):
        raise ValueError("employer_candidate_population_authority_required")
    population = census.get("candidates")
    if not isinstance(population, list):
        raise TypeError("candidate_population_required")
    keys = [_key(row.get("company_key")) for row in population]
    if len(set(keys)) != len(keys):
        raise ValueError("candidate_population_duplicate_identity")
    if census.get("summary", {}).get("employer_candidate_count") != len(keys):
        raise ValueError("candidate_population_count_mismatch")
    source_sha = None if fresh else census.get("provenance", {}).get("classic_repository_sha", "")
    if fresh:
        _validate_fresh_population(census)
    elif (
        not isinstance(source_sha, str)
        or len(source_sha) != 40
        or any(char not in "0123456789abcdef" for char in source_sha)
    ):
        raise ValueError("exact_classic_source_required")
    snapshot_digest = digest(census)
    evidence_by_key = {}
    if evidence_bundle is not None:
        if evidence_bundle.get("schema_version") != EVIDENCE_SCHEMA:
            raise ValueError("candidate_evidence_schema_invalid")
        if evidence_bundle.get("census_digest") != snapshot_digest:
            raise ValueError("candidate_evidence_snapshot_mismatch")
        admitted_kind = "FRESH_CLOUD_SNAPSHOT" if fresh else "CLASSIC_SNAPSHOT"
        if evidence_bundle.get("data_kind") not in {admitted_kind, "TEST_FIXTURE"}:
            raise ValueError("evidence_data_kind_required")
        for item in evidence_bundle.get("sources", []):
            key = _key(item.get("company_key"))
            if key not in keys or key in evidence_by_key:
                raise ValueError("evidence_population_unknown_or_duplicate")
            evidence_by_key[key] = item
    capabilities = capabilities_from_catalog(catalog_payload)
    rows = []
    records = []
    for candidate in sorted(population, key=lambda row: _key(row["company_key"])):
        key = _key(candidate["company_key"])
        row = {
            "company_key": key,
            "company_name": candidate.get("company_name", ""),
            "input_disposition": candidate.get("disposition", "NOT_MEASURED"),
            "disposition": "evidence_gap",
            "blocker": "verified_origin_evidence_required",
            "runtime_admitted": False,
        }
        if not fresh:
            row["classic_disposition"] = row["input_disposition"]
        source = evidence_by_key.get(key)
        if source is not None:
            try:
                if source.get("origin_verified") is not True:
                    raise ValueError("verified_origin_evidence_required")
                tags = source.get("fingerprint_tags")
                if tags is None and source.get("execution_plan") and source.get("responses"):
                    provisional = _plan(source["execution_plan"], "a" * 64)
                    if provisional.origin_url != source["origin_url"]:
                        raise ValueError("execution_origin_binding_mismatch")
                    tags = list(
                        fingerprint_saved_responses(
                            provisional,
                            tuple(AcquisitionResponse(**v) for v in source["responses"]),
                        )
                    )
                    row["fingerprint_origin"] = "SAVED_RESPONSE_DETECTION"
                lineage = source.get("evidence_ids")
                if not isinstance(tags, list) or any(not isinstance(v, str) for v in tags):
                    raise ValueError("fingerprint_tags_invalid")
                if (
                    not isinstance(lineage, list)
                    or not lineage
                    or any(not isinstance(v, str) or not v.strip() for v in lineage)
                ):
                    raise ValueError("source_lineage_required")
                evidence = CandidateConnectorEvidence(
                    candidate_key=f"candidate:{key}",
                    company_key=key,
                    origin_url=source["origin_url"],
                    source_type=source["source_type"],
                    required_roles=(
                        ConnectorCapabilityRole.ORIGIN_INVENTORY,
                        ConnectorCapabilityRole.JOB_DETAIL,
                    ),
                    fingerprint_tags=tuple(tags),
                    evidence_ids=tuple(lineage)
                    + (f"snapshot:{snapshot_digest}", f"source-evidence:{digest(source)}"),
                    market_sensor_only=source.get("market_sensor_only") is not False,
                )
                compiled = compile_connector_recipe(evidence, capabilities)
                row["fingerprint_tags"] = sorted(set(tags))
                row.update(
                    disposition=compiled.disposition.value,
                    blocker=compiled.reason,
                    missing_roles=[item.value for item in compiled.missing_roles],
                )
                if compiled.recipe is not None:
                    recipe = compiled.recipe
                    proof = qualify_connector_recipe(recipe, capabilities)
                    row.update(
                        recipe_id=recipe.recipe_id,
                        capability_ids=sorted({b.capability_id for b in recipe.bindings}),
                        definition_status=proof.status,
                        definition_proof_id=proof.proof_id,
                    )
                    if proof.status != "PASS":
                        row.update(
                            disposition="qualification_gap", blocker=",".join(proof.blockers)
                        )
                    elif not source.get("execution_plan"):
                        row.update(
                            disposition="recipe_ready", blocker="execution_plan_evidence_required"
                        )
                    else:
                        plan = _plan(source["execution_plan"], recipe.recipe_id)
                        if plan.origin_url != recipe.origin_url:
                            raise ValueError("execution_origin_binding_mismatch")
                        required_strategy = {
                            "json": "JSON_API",
                            "jsonld": "JSONLD",
                            "html": "HTML_DETAIL",
                        }.get(plan.extractor)
                        strategies = {
                            item.runtime_strategy
                            for item in capabilities
                            if (item.capability_id, item.version)
                            in {(b.capability_id, b.capability_version) for b in recipe.bindings}
                        }
                        if strategies != {required_strategy}:
                            row.update(
                                disposition="runtime_gap",
                                blocker="selected_capability_execution_not_implemented",
                            )
                            rows.append(row)
                            continue
                        responses = tuple(AcquisitionResponse(**v) for v in source["responses"])
                        expected = tuple(
                            ExtractedJob(**{**v, "locations": tuple(v["locations"])})
                            for v in source["expected_jobs"]
                        )
                        extraction_proof = qualify_extraction(plan, responses, expected)
                        row.update(
                            disposition="qualified_inactive",
                            blocker="live_admission_and_recurring_execution_pending",
                            extraction_proof_id=extraction_proof["proof_id"],
                            replay_job_count=extraction_proof["job_count"],
                        )
                        records.append(
                            {
                                "company_key": key,
                                "definition": connector_factory_evidence_records(recipe, proof),
                                "execution_plan": asdict(plan),
                                "extraction_proof": extraction_proof,
                            }
                        )
            except (ValueError, TypeError, KeyError) as error:
                row.update(
                    disposition="qualification_gap" if "recipe_id" in row else "evidence_gap",
                    blocker=str(error),
                )
        rows.append(row)
    counts = dict(sorted(Counter(row["disposition"] for row in rows).items()))
    gap_groups: dict[str, list[str]] = {}
    engineering_groups: dict[str, dict] = {}
    for row in rows:
        if row["disposition"] == "capability_gap":
            gap_groups.setdefault(",".join(row.get("missing_roles", [])), []).append(
                row["company_key"]
            )
        if row["disposition"] in {"capability_gap", "runtime_gap"}:
            signature = {
                "disposition": row["disposition"],
                "fingerprint_tags": row.get("fingerprint_tags", []),
                "missing_roles": row.get("missing_roles", []),
                "capability_ids": row.get("capability_ids", []),
            }
            group = engineering_groups.setdefault(
                digest(signature),
                {**signature, "candidate_keys": [], "wbaa_mission_created": False},
            )
            group["candidate_keys"].append(row["company_key"])
    return {
        "schema_version": "jap.connector_census_evaluation.v1",
        "census_digest": snapshot_digest,
        "classic_repository_sha": source_sha,
        "population_authority": population_authority,
        "measurement_scope": "COLD_START" if fresh else "CLASSIC_RETROSPECTIVE",
        "profile_snapshot_digest": census.get("provenance", {}).get("profile_snapshot_digest"),
        "catalog_digest": digest(catalog_payload),
        "evidence_digest": digest(evidence_bundle) if evidence_bundle is not None else None,
        "data_kind": evidence_bundle.get("data_kind") if evidence_bundle else "CENSUS_ONLY",
        "candidate_count": len(rows),
        "disposition_counts": counts,
        "provider_calls": 0,
        "external_requests": 0,
        "database_writes": 0,
        "runtime_activations": 0,
        "current_live_health_measured": False,
        "capability_gap_groups": gap_groups,
        "engineering_gap_groups": engineering_groups,
        "candidates": rows,
        "persistable_evidence": records,
    }


def _validate_fresh_population(population: dict) -> None:
    """Cold-start observations, never Classic source/connector-state imports.

    Provenance is a supplied declaration with content binding, not independent
    proof of when or how a source was discovered. Acquisition needs a live carrier.
    """
    provenance = population.get("provenance", {})
    boundaries = population.get("boundaries", {})
    if (
        provenance.get("discovery_kind") != "FRESH_PROFILE_DRIVEN"
        or "classic_repository_sha" in provenance
        or boundaries.get("classic_enrichment_applied") is not False
        or boundaries.get("imported_connector_state") is not False
    ):
        raise ValueError("cold_start_without_classic_enrichment_required")
    for field, length in (("cloud_repository_sha", 40), ("profile_snapshot_digest", 64)):
        value = provenance.get(field)
        if not isinstance(value, str) or len(value) != length or any(
            char not in "0123456789abcdef" for char in value
        ):
            raise ValueError(f"fresh_population_{field}_required")
    if not isinstance(provenance.get("discovery_run_id"), str) or not provenance[
        "discovery_run_id"
    ].strip():
        raise ValueError("fresh_discovery_run_required")
    for row in population["candidates"]:
        ids = row.get("discovery_evidence_ids")
        if (
            row.get("candidate_origin") != "FRESH_DISCOVERY"
            or not isinstance(ids, list)
            or not ids
            or any(not isinstance(value, str) or not value.strip() for value in ids)
        ):
            raise ValueError("fresh_candidate_discovery_lineage_required")
