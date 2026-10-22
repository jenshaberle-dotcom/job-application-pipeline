"""Complete Cloud Census ingress; no geographical filtering or connector activation."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def validate_export(export):
    if export.get("schema_version") != "jap.cloud_census_export.v1":
        raise ValueError("CENSUS_EXPORT_SCHEMA_REQUIRED")
    population = export["population"]
    if digest(population) != export.get("population_digest"):
        raise ValueError("CENSUS_DIGEST_MISMATCH")
    provenance = population["provenance"]
    if (population.get("schema_version") != "jap_cloud.fresh_connector_population.v1"
            or not re.fullmatch(r"[0-9a-f]{40}", provenance.get("cloud_repository_sha", ""))
            or not export.get("census_run")
            or export.get("sql_readback_verified") is not True):
        raise ValueError("CENSUS_PROVENANCE_REQUIRED")
    rows = population["candidates"]
    if (not rows or len(rows) != population["summary"]["employer_candidate_count"]
            or len({r["company_key"] for r in rows}) != len(rows)):
        raise ValueError("CENSUS_POPULATION_INCOMPLETE")
    for row in rows:
        if (not isinstance(row.get("company_key"), str) or not row["company_key"].strip()
                or not isinstance(row.get("company_name"), str) or not row["company_name"].strip()
                or not row.get("discovery_evidence_ids")):
            raise ValueError("CENSUS_COMPANY_LINEAGE_REQUIRED")
    return rows


def plan_import(export, existing):
    """Conservative identity matching; name-only matches require review, never overwrite."""
    rows = validate_export(export)
    existing = list(existing)
    plans = []
    for row in rows:
        name = row["company_name"].strip().casefold()
        key = row["company_key"]
        matches = [r for r in existing if r["company_key"] == key
                   or r["company_name"].strip().casefold() == name]
        exact = [r for r in matches if r["company_key"] == key
                 and r["company_name"].strip().casefold() == name]
        identity = "cloud-census-" + hashlib.sha256(key.encode()).hexdigest()
        generated = [r for r in existing if r["company_key"] == identity]
        if generated:
            matches += generated
            exact += [r for r in generated if r["company_name"].strip().casefold() == name]
        candidate_id = None
        if len(matches) == len(exact) == 1:
            disposition, candidate_id = "EXISTING", exact[0]["id"]
        elif matches:
            disposition = "IDENTITY_REVIEW"
        else:
            disposition = "CREATED_DISCOVERY"
            existing.append({"id": None, "company_key": identity, "company_name": row["company_name"]})
        plans.append({"cloud_company_key": key, "observation": row,
                      "classic_company_key": identity, "classic_candidate_id": candidate_id,
                      "disposition": disposition})
    return {"population_digest": export["population_digest"], "candidate_count": len(rows),
            "counts": dict(Counter(r["disposition"] for r in plans)), "candidates": plans,
            "geography_filter_applied": False, "sources_activated": 0}


def apply_import(conn, export):
    """One atomic transaction; same run cannot acquire different content."""
    from psycopg.types.json import Jsonb

    validate_export(export)
    with conn.transaction():
        # Serialize against candidate writers, not only other census imports.
        conn.execute("LOCK TABLE employer_origin_source_candidates IN SHARE ROW EXCLUSIVE MODE")
        conn.execute("LOCK TABLE bronze_cloud_census_imports IN SHARE ROW EXCLUSIVE MODE")
        prior = conn.execute(
            "SELECT population_digest,census_run FROM bronze_cloud_census_imports "
            "WHERE population_digest=%s OR census_run=%s",
            (export["population_digest"], export["census_run"])).fetchall()
        if prior:
            if len(prior) != 1 or prior[0] != (export["population_digest"], export["census_run"]):
                raise ValueError("CENSUS_RUN_CONTENT_CONFLICT")
            return {"status": "ALREADY_IMPORTED", "population_digest": export["population_digest"]}
        existing = [dict(zip(("id", "company_key", "company_name"), row)) for row in
                    conn.execute("SELECT id,company_key,company_name FROM employer_origin_source_candidates")]
        plan = plan_import(export, existing)
        conn.execute(
            "INSERT INTO bronze_cloud_census_imports "
            "(population_digest,census_run,source_revision,payload,candidate_count) "
            "VALUES (%s,%s,%s,%s,%s)",
            (export["population_digest"], export["census_run"],
             export["population"]["provenance"]["cloud_repository_sha"],
             Jsonb(export), plan["candidate_count"]))
        for item in plan["candidates"]:
            candidate_id = item["classic_candidate_id"]
            if item["disposition"] == "CREATED_DISCOVERY":
                candidate_id = conn.execute(
                    """INSERT INTO employer_origin_source_candidates
                    (company_key,company_name,candidate_url,source_name_candidate,
                     source_family_candidate,source_type_candidate,status,risk_level,notes)
                    VALUES (%s,%s,NULL,%s,'employer_origin','employer_origin_career_site',
                            'discovery','unknown',%s) RETURNING id""",
                    (item["classic_company_key"], item["observation"]["company_name"],
                     item["classic_company_key"],
                     "Cloud Census observation; websites retained in Bronze, not qualified career URLs. "
                     + export["population_digest"])).fetchone()[0]
            conn.execute(
                """INSERT INTO bronze_cloud_census_candidates
                (population_digest,cloud_company_key,observation,classic_candidate_id,disposition)
                VALUES (%s,%s,%s,%s,%s)""",
                (export["population_digest"], item["cloud_company_key"],
                 Jsonb(item["observation"]), candidate_id, item["disposition"]))
        return {k: v for k, v in plan.items() if k != "candidates"} | {"status": "CENSUS_IMPORTED"}
