from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.market_sensor_catalog import CORE_SENSORS

MANIFEST_SCHEMA = "jap_cloud.classic_vnext_export_manifest.v1"
RECYCLE_CONTRACT_VERSION = "jap_cloud.classic_recycle_contract.v1"
FINGERPRINT_SCHEMA = "jap_classic.generic_origin_projection_fingerprint.v1"

REQUIRED_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("companies", "companies.ndjson"),
    ("employer_candidates", "employer_candidates.ndjson"),
    ("employer_sources", "employer_sources.ndjson"),
    ("current_vacancies", "current_vacancies.ndjson"),
)
OPTIONAL_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("current_vacancy_facts", "current_vacancy_facts.ndjson"),
)


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _is_sha256(value: object) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _repository_sha() -> str:
    value = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
    ).strip()
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("invalid_classic_repository_sha")
    return value


def _relation_exists(cur: Any, relation: str) -> bool:
    cur.execute(
        "SELECT to_regclass(%s) AS relation_name",
        (f"public.{relation}",),
    )
    row = cur.fetchone()
    return bool(row and row.get("relation_name") is not None)


def _rows(cur: Any, query: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    cur.execute(query, params)
    return [dict(row) for row in cur.fetchall()]


def _sensor_name(value: object) -> str | None:
    name = str(value or "").strip().casefold()
    catalog = {item.casefold(): item for item in CORE_SENSORS}
    return catalog.get(name)


def _evidence_timestamp(row: Mapping[str, Any], *fields: str) -> str | None:
    for field in fields:
        value = row.get(field)
        if value is not None:
            return str(value)
    return None


def _is_manual_job_observation(
    row: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> bool:
    markers = {
        str(row.get("evidence_kind") or "").strip().casefold(),
        str(row.get("evidence_source") or "").strip().casefold(),
        str(payload.get("input_mode") or "").strip().casefold(),
        str(payload.get("observation_origin") or "").strip().casefold(),
    }
    return bool(
        {
            "manual_market_observation",
            "manual_market_observation_backfill",
            "manual_market_evidence",
            "external_market_observation",
            "manual_aggregator_sighting",
        }
        & markers
    )


def _candidate_evidence_index(
    *,
    promotion_rows: Sequence[Mapping[str, Any]] = (),
    market_rows: Sequence[Mapping[str, Any]] = (),
    detail_rows: Sequence[Mapping[str, Any]] = (),
    silver_rows: Sequence[Mapping[str, Any]] = (),
) -> dict[int, dict[str, Any]]:
    evidence: dict[int, dict[str, Any]] = {}

    for row in promotion_rows:
        candidate_id = int(row["candidate_id"])
        if candidate_id in evidence:
            continue
        payload = dict(row.get("evidence") or {})
        sample_titles = payload.get("sample_titles")
        if isinstance(sample_titles, (list, tuple)):
            titles = [
                str(value).strip()
                for value in sample_titles
                if str(value).strip()
            ]
        else:
            fallback_title = str(
                payload.get("job_title") or payload.get("title") or ""
            ).strip()
            titles = [fallback_title] if fallback_title else []
        if not titles:
            continue
        source_name = str(row.get("source_name") or "").strip()
        sensor = _sensor_name(source_name)
        manual = _is_manual_job_observation(row, payload)
        evidence[candidate_id] = {
            "origin_kind": (
                "LEGACY_MANUAL_JOB_OBSERVATION"
                if manual or sensor is None
                else "CANDIDATE_PROMOTION_JOB_EVIDENCE"
            ),
            "classic_relation": "candidate_promotion_review_items",
            "classic_row_id": int(row["evidence_id"]),
            "source_name": source_name,
            "sensor_key": sensor,
            "discovery_channel": source_name or None,
            "automatic_sensor_authority": sensor is not None and not manual,
            "observed_job_titles": titles,
            "evidence": payload,
            "observed_at": _evidence_timestamp(
                row,
                "latest_job_observed_at",
                "created_at",
            ),
        }

    for row in market_rows:
        candidate_id = int(row["candidate_id"])
        if candidate_id in evidence:
            continue
        title = str(row.get("title") or "").strip()
        evidence_url = str(row.get("evidence_url") or "").strip()
        if not title:
            continue
        source_name = str(row.get("source_name") or "").strip()
        payload = dict(row.get("evidence") or {})
        sensor = _sensor_name(source_name)
        manual = _is_manual_job_observation(row, payload)
        evidence[candidate_id] = {
            "origin_kind": (
                "LEGACY_MANUAL_JOB_OBSERVATION"
                if manual or sensor is None
                else "MARKET_JOB_EVIDENCE"
            ),
            "classic_relation": "market_evidence",
            "classic_row_id": int(row["evidence_id"]),
            "source_name": source_name,
            "sensor_key": sensor,
            "discovery_channel": source_name or None,
            "automatic_sensor_authority": sensor is not None and not manual,
            "title": title,
            "evidence_url": evidence_url or None,
            "evidence": payload,
            "observed_at": _evidence_timestamp(
                row,
                "source_seen_at",
                "observed_at",
            ),
        }

    for row in detail_rows:
        candidate_id = int(row["candidate_id"])
        if candidate_id in evidence:
            continue
        source_url = str(row.get("source_url") or "").strip()
        payload = dict(row.get("evidence") or {})
        title = str(
            row.get("page_title")
            or payload.get("title")
            or payload.get("job_title")
            or ""
        ).strip()
        if not source_url or not title:
            continue
        evidence[candidate_id] = {
            "origin_kind": "EMPLOYER_ORIGIN_JOB_DETAIL_EVIDENCE",
            "classic_relation": "employer_origin_job_detail_evidence",
            "classic_row_id": int(row["evidence_id"]),
            "source_url": source_url,
            "title": title,
            "status_code": row.get("status_code"),
            "confidence": (
                None
                if row.get("confidence") is None
                else str(row.get("confidence"))
            ),
            "evidence": payload,
            "observed_at": _evidence_timestamp(row, "updated_at", "created_at"),
        }

    for row in silver_rows:
        candidate_id = int(row["candidate_id"])
        if candidate_id in evidence:
            continue
        title = str(row.get("title") or "").strip()
        source_url = str(row.get("source_url") or "").strip()
        if not title or not source_url:
            continue
        evidence[candidate_id] = {
            "origin_kind": "EMPLOYER_ORIGIN_SILVER_JOB_EVIDENCE",
            "classic_relation": "silver_jobs",
            "classic_row_id": int(row["silver_job_id"]),
            "source_name": str(row.get("source_name") or ""),
            "title": title,
            "source_url": source_url,
            "observed_at": _evidence_timestamp(
                row,
                "last_seen_at",
                "updated_at",
                "created_at",
            ),
        }

    return evidence


def build_candidate_artifacts(
    *,
    candidates: Sequence[Mapping[str, Any]],
    evidence_index: Mapping[int, Mapping[str, Any]],
    classic_sha: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    companies: list[dict[str, Any]] = []
    candidate_exports: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    seen_company_keys: set[str] = set()
    for row in candidates:
        candidate_id = int(row["id"])
        company_key = str(row.get("company_key") or "").strip().casefold()
        company_name = str(row.get("company_name") or "").strip()
        if not company_key or not company_name:
            raise ValueError(f"candidate_identity_incomplete:{candidate_id}")

        source_name_candidate = str(row.get("source_name_candidate") or "").strip()
        if _sensor_name(source_name_candidate):
            # This row is still an Employer Candidate. The sensor may only be
            # discovery provenance and must never become Employer Source truth.
            sensor_relation = "DISCOVERY_PROVENANCE_ONLY"
        else:
            sensor_relation = "NOT_SENSOR_IDENTITY"

        evidence = evidence_index.get(candidate_id)
        if evidence is None:
            observed_at = str(row.get("created_at") or "")
            if not observed_at:
                raise ValueError(
                    f"candidate_legacy_coverage_timestamp_missing:{candidate_id}"
                )
            evidence = {
                "origin_kind": "LEGACY_CLASSIC_CANDIDATE",
                "classic_relation": "employer_origin_source_candidates",
                "classic_row_id": candidate_id,
                "source_name_candidate": source_name_candidate or None,
                "classic_status": str(row.get("status") or ""),
                "observed_at": observed_at,
                "migration_note": (
                    "Current Classic Employer Candidate preserved as accepted "
                    "coverage intent; no historical job observation is invented."
                ),
            }
            admission_reason = "LEGACY_CLASSIC_COVERAGE"
            gaps.append(
                {
                    "candidate_id": candidate_id,
                    "company_key": company_key,
                    "company_name": company_name,
                    "diagnostic": "LEGACY_CLASSIC_COVERAGE_USED",
                    "classic_status": str(row.get("status") or ""),
                    "source_name_candidate": source_name_candidate,
                }
            )
        else:
            observed_at = str(
                evidence.get("observed_at") or row.get("created_at") or ""
            )
            if not observed_at:
                raise ValueError(
                    f"candidate_evidence_timestamp_missing:{candidate_id}"
                )
            admission_reason = "REAL_JOB_OBSERVED"

        if company_key not in seen_company_keys:
            seen_company_keys.add(company_key)
            companies.append(
                {
                    "company_key": company_key,
                    "canonical_name": company_name,
                    "provenance": {
                        "classic_repository_sha": classic_sha,
                        "classic_candidate_id": candidate_id,
                        "classic_status": str(row.get("status") or ""),
                        "source_name_candidate": source_name_candidate,
                    },
                }
            )

        admission_evidence = dict(evidence)
        admission_evidence["classic_repository_sha"] = classic_sha
        admission_evidence["sensor_identity_boundary"] = sensor_relation
        candidate_exports.append(
            {
                "company_key": company_key,
                "admission_reason": admission_reason,
                "first_evidence_at": observed_at,
                "latest_evidence_at": observed_at,
                "admission_evidence": admission_evidence,
            }
        )

    companies.sort(key=lambda row: row["company_key"])
    candidate_exports.sort(key=lambda row: row["company_key"])
    gaps.sort(key=lambda row: row["company_key"])
    return companies, candidate_exports, gaps


def build_source_artifacts(
    rows: Sequence[Mapping[str, Any]],
    *,
    classic_sha: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        company_key = str(row.get("company_key") or "").strip().casefold()
        source_name = str(row.get("source_name") or "").strip()
        origin_url = str(row.get("origin_url") or "").strip()
        proof_state = str(row.get("proof_state") or "").strip().casefold()
        if not source_name.startswith("generic_origin:"):
            raise ValueError(f"non_generic_source_in_active_projection:{source_name}")
        if source_name != f"generic_origin:{company_key}":
            raise ValueError(f"generic_source_identity_mismatch:{source_name}")
        if proof_state != "pass":
            raise ValueError(f"active_source_without_proof_pass:{source_name}")
        if not origin_url.startswith("https://"):
            raise ValueError(f"active_source_origin_not_https:{source_name}")

        proof_evidence = dict(row.get("proof_evidence") or {})
        fingerprint = {
            "schema_version": FINGERPRINT_SCHEMA,
            "source_name": source_name,
            "canonical_origin_url": origin_url,
            "classic_authority": str(row.get("authority") or ""),
            "proof_state": proof_state,
            "proof_evidence": proof_evidence,
        }
        source_type = str(row.get("source_type_candidate") or "")
        source_kind = (
            "ATS_DELEGATED"
            if source_type == "employer_origin_ats_backed_career_site"
            else "FIRST_PARTY"
        )
        result.append(
            {
                "source_key": source_name,
                "company_key": company_key,
                "canonical_origin_url": origin_url,
                "source_kind": source_kind,
                "proof_state": "pass",
                "fingerprint_schema_version": FINGERPRINT_SCHEMA,
                "fingerprint_sha256": _sha256(fingerprint),
                "fingerprint": fingerprint,
                "provenance": {
                    "classic_repository_sha": classic_sha,
                    "classic_candidate_id": int(row["candidate_id"]),
                    "authority": str(row.get("authority") or ""),
                    "activated_at": str(row.get("activated_at") or ""),
                    "updated_at": str(row.get("updated_at") or ""),
                },
            }
        )
    return sorted(result, key=lambda row: row["source_key"])


def _proven_identity(row: Mapping[str, Any]) -> str:
    external_job_id = str(row.get("external_job_id") or "").strip()
    if external_job_id:
        return f"external:{external_job_id}"
    source_url = str(
        row.get("exact_observed_origin_url")
        or row.get("source_url")
        or ""
    ).strip()
    if source_url:
        return f"url:{source_url}"
    raise ValueError(f"vacancy_identity_missing:silver_job_id={row.get('silver_job_id')}")


def build_vacancy_artifacts(
    rows: Sequence[Mapping[str, Any]],
    *,
    locations_by_silver_id: Mapping[int, Sequence[Mapping[str, Any]]],
    classic_sha: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        source_name = str(row.get("source_name") or "").strip()
        company_key = str(row.get("company_key") or "").strip().casefold()
        source_url = str(row.get("source_url") or "").strip()
        title = str(row.get("title") or "").strip()
        canonical_key = str(row.get("canonical_vacancy_key") or "").strip()
        if not source_name.startswith("generic_origin:"):
            raise ValueError(f"vacancy_not_employer_origin:{source_name}")
        if not source_url or not title or not canonical_key:
            raise ValueError(f"vacancy_current_fields_missing:{row.get('silver_job_id')}")

        proven_identity = _proven_identity(row)
        source_vacancy_key = f"{source_name}|{proven_identity}"
        raw_payload = row.get("raw_data")
        raw_hash = str(row.get("content_hash") or "").strip().casefold()
        content_sha256 = (
            raw_hash
            if _is_sha256(raw_hash)
            else _sha256(
                {
                    "raw_data": raw_payload,
                    "source_url": source_url,
                    "title": title,
                    "company_name": row.get("company_name"),
                    "city": row.get("city"),
                    "country": row.get("country"),
                    "publication_date": row.get("publication_date"),
                }
            )
        )

        locations = [
            {
                "city": str(item.get("city") or "").strip(),
                "country_code": str(item.get("country_code") or "").strip(),
                "is_primary": bool(item.get("is_primary")),
                "evidence_source": str(item.get("evidence_source") or ""),
                "evidence_text": str(item.get("evidence_text") or ""),
            }
            for item in locations_by_silver_id.get(int(row["silver_job_id"]), ())
            if str(item.get("city") or "").strip()
        ]
        first_seen = str(
            row.get("first_seen_at")
            or row.get("raw_created_at")
            or row.get("silver_created_at")
            or ""
        )
        last_seen = str(
            row.get("last_seen_at")
            or row.get("latest_seen_at")
            or row.get("silver_updated_at")
            or ""
        )
        if not first_seen or not last_seen:
            raise ValueError(f"vacancy_observation_time_missing:{row.get('silver_job_id')}")

        result.append(
            {
                "source_vacancy_key": source_vacancy_key,
                "source_key": source_name,
                "company_key": company_key,
                "proven_identity_key": proven_identity,
                "canonical_identity_key": canonical_key,
                "source_url": source_url,
                "title": title,
                "location_text": str(row.get("normalized_location") or row.get("city") or ""),
                "locations": locations,
                "posted_at": (
                    None
                    if row.get("publication_date") is None
                    else str(row.get("publication_date"))
                ),
                "availability_state": "OPEN",
                "content_sha256": content_sha256,
                "first_seen_at": first_seen,
                "last_seen_at": last_seen,
                "provenance": {
                    "classic_repository_sha": classic_sha,
                    "silver_job_id": int(row["silver_job_id"]),
                    "raw_job_id": int(row["raw_job_id"]),
                    "identity_kind": str(row.get("identity_kind") or ""),
                    "lifecycle_status": "active_confirmed",
                },
            }
        )
    return sorted(result, key=lambda row: row["source_vacancy_key"])


def build_fact_artifacts(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_vacancy_key_by_silver_id: Mapping[int, str],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        silver_job_id = int(row["silver_job_id"])
        source_vacancy_key = source_vacancy_key_by_silver_id.get(silver_job_id)
        if source_vacancy_key is None:
            continue
        value = dict(row.get("evidence_payload") or {})
        evidence_hash = str(row.get("evidence_hash") or "").strip().casefold()
        result.append(
            {
                "source_vacancy_key": source_vacancy_key,
                "fact_kind": "requirements",
                "value": value,
                "evidence_ref": (
                    f"classic:silver_job_requirement_evidence:{silver_job_id}"
                ),
                "evidence_sha256": (
                    evidence_hash if _is_sha256(evidence_hash) else _sha256(value)
                ),
                "extractor_revision": (
                    f"{str(row.get('parser_family') or 'unknown')}:"
                    f"{str(row.get('evidence_schema') or 'unknown')}"
                ),
                "observed_at": str(row.get("updated_at") or row.get("created_at") or ""),
            }
        )
    return sorted(
        result,
        key=lambda row: (row["source_vacancy_key"], row["fact_kind"]),
    )


def _write_ndjson(path: Path, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    payload = b"".join(_canonical_json(dict(row)) for row in rows)
    path.write_bytes(payload)
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "row_count": len(rows),
    }


def write_export_bundle(
    output_dir: Path,
    *,
    classic_sha: str,
    companies: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
    vacancies: Sequence[Mapping[str, Any]],
    facts: Sequence[Mapping[str, Any]] = (),
    extracted_at: str | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, Sequence[Mapping[str, Any]]] = {
        "companies": companies,
        "employer_candidates": candidates,
        "employer_sources": sources,
        "current_vacancies": vacancies,
        "current_vacancy_facts": facts,
    }
    artifacts: list[dict[str, Any]] = []
    required_names = {name for name, _ in REQUIRED_ARTIFACTS}
    ordered = REQUIRED_ARTIFACTS + OPTIONAL_ARTIFACTS
    for logical_name, filename in ordered:
        rows = payloads[logical_name]
        if logical_name not in required_names and not rows:
            continue
        metadata = _write_ndjson(output_dir / filename, rows)
        artifacts.append(
            {
                "logical_name": logical_name,
                "path": filename,
                "required": logical_name in required_names,
                **metadata,
            }
        )

    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA,
        "contract_version": RECYCLE_CONTRACT_VERSION,
        "classic_repository_sha": classic_sha,
        "extracted_at": extracted_at or datetime.now(UTC).isoformat(),
        "artifacts": artifacts,
    }
    manifest["manifest_sha256"] = hashlib.sha256(_canonical_json(manifest)).hexdigest()
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _load_live_export_inputs(conn: Any) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cur:
        candidates = _rows(
            cur,
            """
            SELECT DISTINCT ON (company_key)
                id,
                company_key,
                company_name,
                candidate_url,
                source_name_candidate,
                source_family_candidate,
                source_type_candidate,
                status,
                risk_level,
                created_at,
                updated_at
            FROM employer_origin_source_candidates
            ORDER BY company_key, updated_at DESC, id DESC
            """,
        )
        candidate_ids = [int(row["id"]) for row in candidates]

        promotion_rows: list[dict[str, Any]] = []
        if _relation_exists(cur, "candidate_promotion_review_items"):
            promotion_rows = _rows(
                cur,
                """
                SELECT DISTINCT ON (promotion.created_candidate_id)
                    promotion.created_candidate_id AS candidate_id,
                    promotion.id AS evidence_id,
                    promotion.source_name,
                    promotion.evidence_count,
                    promotion.evidence,
                    expansion.latest_observed_at AS latest_job_observed_at,
                    promotion.created_at
                FROM candidate_promotion_review_items promotion
                JOIN candidate_expansion_review_items expansion
                  ON expansion.id = promotion.candidate_expansion_item_id
                WHERE promotion.created_candidate_id = ANY(%s)
                  AND promotion.promotion_decision = 'promotion_recommended'
                ORDER BY
                    promotion.created_candidate_id,
                    expansion.latest_observed_at DESC NULLS LAST,
                    promotion.created_at DESC,
                    promotion.id DESC
                """,
                (candidate_ids,),
            )

        market_rows: list[dict[str, Any]] = []
        if _relation_exists(cur, "market_evidence"):
            market_rows = _rows(
                cur,
                """
                SELECT DISTINCT ON (candidate.id)
                    candidate.id AS candidate_id,
                    evidence.id AS evidence_id,
                    evidence.evidence_kind,
                    evidence.evidence_source,
                    evidence.source_name,
                    evidence.title,
                    evidence.evidence_url,
                    evidence.source_seen_at,
                    evidence.observed_at,
                    evidence.evidence
                FROM employer_origin_source_candidates candidate
                JOIN market_evidence evidence
                  ON evidence.normalized_company_key = candidate.company_key
                WHERE candidate.id = ANY(%s)
                  AND NULLIF(btrim(evidence.title), '') IS NOT NULL
                ORDER BY
                    candidate.id,
                    coalesce(
                        evidence.source_seen_at,
                        evidence.observed_at
                    ) DESC,
                    evidence.id DESC
                """,
                (candidate_ids,),
            )

        detail_rows: list[dict[str, Any]] = []
        if _relation_exists(cur, "employer_origin_job_detail_evidence"):
            detail_rows = _rows(
                cur,
                """
                SELECT DISTINCT ON (candidate_id)
                    candidate_id,
                    id AS evidence_id,
                    coalesce(final_url, source_url) AS source_url,
                    page_title,
                    status_code,
                    confidence,
                    evidence,
                    created_at,
                    updated_at
                FROM employer_origin_job_detail_evidence
                WHERE candidate_id = ANY(%s)
                  AND relevance_decision = 'relevant'
                  AND NULLIF(
                        btrim(coalesce(final_url, source_url)),
                        ''
                      ) IS NOT NULL
                  AND NULLIF(
                        btrim(
                            coalesce(
                                page_title,
                                evidence ->> 'title',
                                evidence ->> 'job_title'
                            )
                        ),
                        ''
                      ) IS NOT NULL
                ORDER BY
                    candidate_id,
                    updated_at DESC,
                    created_at DESC,
                    id DESC
                """,
                (candidate_ids,),
            )

        active_sources = _rows(
            cur,
            """
            SELECT
                active.candidate_id,
                active.company_key,
                active.source_name,
                active.origin_url,
                active.authority,
                active.proof_state,
                active.proof_evidence,
                active.activated_at,
                active.updated_at,
                candidate.source_type_candidate
            FROM generic_employer_origin_active_sources active
            JOIN employer_origin_source_candidates candidate
              ON candidate.id = active.candidate_id
            ORDER BY active.company_key
            """,
        )

        silver_evidence_rows: list[dict[str, Any]] = []
        if active_sources:
            silver_evidence_rows = _rows(
                cur,
                """
                SELECT DISTINCT ON (active.candidate_id)
                    active.candidate_id,
                    silver.id AS silver_job_id,
                    silver.source_name,
                    silver.title,
                    silver.source_url,
                    silver.created_at,
                    silver.updated_at,
                    lifecycle.last_seen_at
                FROM generic_employer_origin_active_sources active
                JOIN silver_jobs silver
                  ON silver.source_name = active.source_name
                LEFT JOIN job_lifecycle lifecycle
                  ON lifecycle.source_name = silver.source_name
                 AND lifecycle.external_job_id = silver.external_job_id
                WHERE NULLIF(btrim(silver.title), '') IS NOT NULL
                  AND NULLIF(btrim(silver.source_url), '') IS NOT NULL
                ORDER BY
                    active.candidate_id,
                    coalesce(lifecycle.last_seen_at, silver.updated_at) DESC,
                    silver.id DESC
                """,
            )

        vacancy_rows = _rows(
            cur,
            """
            SELECT
                current.id AS silver_job_id,
                current.raw_job_id,
                current.source_name,
                current.external_job_id,
                current.source_url,
                current.title,
                current.company_name,
                current.city,
                current.country,
                current.publication_date,
                current.normalized_location,
                current.created_at AS silver_created_at,
                current.updated_at AS silver_updated_at,
                active.company_key,
                identity.canonical_vacancy_key,
                identity.identity_kind,
                identity.latest_seen_at,
                identity.exact_observed_origin_url,
                raw.raw_data,
                raw.content_hash,
                raw.created_at AS raw_created_at,
                observations.first_seen_at,
                observations.last_seen_at
            FROM gold_current_job_opportunities current
            JOIN generic_employer_origin_active_sources active
              ON active.source_name = current.source_name
            JOIN gold_vacancy_identity identity
              ON identity.silver_job_id = current.id
             AND identity.is_representative
            JOIN raw_jobs raw
              ON raw.id = current.raw_job_id
            LEFT JOIN LATERAL (
                SELECT
                    min(observed_at) AS first_seen_at,
                    max(observed_at) AS last_seen_at
                FROM job_observations
                WHERE raw_job_id = current.raw_job_id
                  AND is_seen = TRUE
            ) observations ON TRUE
            ORDER BY current.source_name, current.id
            """,
        )

        locations_by_silver_id: dict[int, list[dict[str, Any]]] = {}
        vacancy_ids = [int(row["silver_job_id"]) for row in vacancy_rows]
        if vacancy_ids and _relation_exists(cur, "silver_job_locations"):
            location_rows = _rows(
                cur,
                """
                SELECT
                    silver_job_id,
                    city,
                    country_code,
                    is_primary,
                    evidence_source,
                    evidence_text
                FROM silver_job_locations
                WHERE silver_job_id = ANY(%s)
                ORDER BY silver_job_id, is_primary DESC, city, country_code
                """,
                (vacancy_ids,),
            )
            for row in location_rows:
                locations_by_silver_id.setdefault(
                    int(row["silver_job_id"]),
                    [],
                ).append(row)

        fact_rows: list[dict[str, Any]] = []
        if vacancy_ids and _relation_exists(cur, "silver_job_requirement_evidence"):
            fact_rows = _rows(
                cur,
                """
                SELECT
                    silver_job_id,
                    evidence_schema,
                    parser_family,
                    evidence_hash,
                    evidence_payload,
                    created_at,
                    updated_at
                FROM silver_job_requirement_evidence
                WHERE silver_job_id = ANY(%s)
                ORDER BY silver_job_id
                """,
                (vacancy_ids,),
            )

    return {
        "candidates": candidates,
        "promotion_rows": promotion_rows,
        "market_rows": market_rows,
        "detail_rows": detail_rows,
        "silver_evidence_rows": silver_evidence_rows,
        "active_sources": active_sources,
        "vacancy_rows": vacancy_rows,
        "locations_by_silver_id": locations_by_silver_id,
        "fact_rows": fact_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create the bounded read-only JAP Classic -> JAP Cloud vNext "
            "recycling export."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    classic_sha = _repository_sha()
    with psycopg.connect(**get_database_config()) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        inputs = _load_live_export_inputs(conn)
        conn.rollback()

    evidence = _candidate_evidence_index(
        promotion_rows=inputs["promotion_rows"],
        market_rows=inputs["market_rows"],
        detail_rows=inputs["detail_rows"],
        silver_rows=inputs["silver_evidence_rows"],
    )
    companies, candidates, legacy_coverage_diagnostics = (
        build_candidate_artifacts(
            candidates=inputs["candidates"],
            evidence_index=evidence,
            classic_sha=classic_sha,
        )
    )

    sources = build_source_artifacts(
        inputs["active_sources"],
        classic_sha=classic_sha,
    )
    vacancies = build_vacancy_artifacts(
        inputs["vacancy_rows"],
        locations_by_silver_id=inputs["locations_by_silver_id"],
        classic_sha=classic_sha,
    )
    source_vacancy_key_by_silver_id = {
        int(row["provenance"]["silver_job_id"]): row["source_vacancy_key"]
        for row in vacancies
    }
    facts = build_fact_artifacts(
        inputs["fact_rows"],
        source_vacancy_key_by_silver_id=source_vacancy_key_by_silver_id,
    )

    manifest = write_export_bundle(
        args.output_dir,
        classic_sha=classic_sha,
        companies=companies,
        candidates=candidates,
        sources=sources,
        vacancies=vacancies,
        facts=facts,
    )
    summary = {
        "classic_repository_sha": classic_sha,
        "company_count": len(companies),
        "candidate_count": len(candidates),
        "employer_source_count": len(sources),
        "current_vacancy_count": len(vacancies),
        "current_vacancy_fact_count": len(facts),
        "legacy_classic_coverage_count": len(legacy_coverage_diagnostics),
        "market_sensor_count_excluded_from_employer_sources": len(CORE_SENSORS),
        "manifest_sha256": manifest["manifest_sha256"],
        "database_access": "READ_ONLY",
        "provider_calls": 0,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    print("JAP_CLOUD_VNEXT_EXPORT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
