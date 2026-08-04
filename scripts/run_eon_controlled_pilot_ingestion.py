from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_database_config  # noqa: E402
from src.connectors.base import SearchProfile, SearchTerm  # noqa: E402
from src.connectors.successfactors_preview import (  # noqa: E402
    SuccessFactorsPreviewConnector,
)
from src.ingestion.eon_controlled_pilot import (  # noqa: E402
    APPROVAL_TOKEN,
    EXPECTED_EXTERNAL_JOB_ID,
    PILOT_KEY,
    PILOT_PAGE_SIZE,
    PILOT_PROFILE_NAME,
    PILOT_SEARCH_TERM,
    PILOT_SOURCE_NAME,
    PILOT_TARGET_KEY,
    PreviewApprovalEvidence,
    authorize_fresh_record_for_pipeline,
    is_authorized_pilot_raw_data,
    load_preview_approval_evidence,
)
from src.silver.transformer import transform_raw_job_to_silver  # noqa: E402


DRY_RUN_RESULT = "EON_CONTROLLED_PILOT_DRY_RUN_VALIDATED"
APPLY_RESULT = "EON_CONTROLLED_PILOT_APPLIED"


@dataclass(frozen=True)
class PilotProfileBinding:
    profile: SearchProfile
    term: SearchTerm
    profile_is_active: bool
    term_is_active: bool


@dataclass(frozen=True)
class PilotApplyResult:
    ingestion_run_id: int
    raw_job_id: int
    raw_job_inserted: bool
    silver_job_id: int
    product_readiness_status: str
    readiness: Mapping[str, Any]


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def validate_profile_row(row: Mapping[str, Any] | None) -> PilotProfileBinding:
    if row is None:
        raise ValueError(f"pilot profile or Data term is missing: {PILOT_PROFILE_NAME}")
    if row["profile_name"] != PILOT_PROFILE_NAME:
        raise ValueError("pilot profile name mismatch")
    if row["source_name"] != PILOT_SOURCE_NAME:
        raise ValueError("pilot source mismatch")
    if row["profile_is_active"] is not False:
        raise ValueError("pilot profile must remain inactive")
    if row["term_is_active"] is not True:
        raise ValueError("pilot Data term must be active")
    if str(row["search_term"]).casefold() != PILOT_SEARCH_TERM.casefold():
        raise ValueError("pilot search term mismatch")
    if int(row["page_size"]) != PILOT_PAGE_SIZE:
        raise ValueError("pilot page size must remain one")
    if row["search_location"] is not None or row["search_radius_km"] is not None:
        raise ValueError("pilot profile must not add a location or radius filter")

    return PilotProfileBinding(
        profile=SearchProfile(
            id=int(row["profile_id"]),
            profile_name=str(row["profile_name"]),
            source_name=str(row["source_name"]),
            search_location=row["search_location"],
            search_radius_km=row["search_radius_km"],
            offer_type=row["offer_type"],
            page_size=int(row["page_size"]),
        ),
        term=SearchTerm(
            id=int(row["search_term_id"]),
            search_term=str(row["search_term"]),
        ),
        profile_is_active=bool(row["profile_is_active"]),
        term_is_active=bool(row["term_is_active"]),
    )


def load_pilot_profile(
    conn: psycopg.Connection[Any],
    *,
    lock: bool = False,
) -> PilotProfileBinding:
    lock_clause = "FOR SHARE OF sp, st" if lock else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                sp.id AS profile_id,
                sp.profile_name,
                sp.source_name,
                sp.search_location,
                sp.search_radius_km,
                sp.offer_type,
                sp.page_size,
                sp.is_active AS profile_is_active,
                st.id AS search_term_id,
                st.search_term,
                st.is_active AS term_is_active
            FROM search_profiles sp
            JOIN search_terms st
              ON st.search_profile_id = sp.id
            WHERE sp.profile_name = %s
              AND lower(st.search_term) = lower(%s)
            {lock_clause}
            """,
            (PILOT_PROFILE_NAME, PILOT_SEARCH_TERM),
        )
        rows = cur.fetchall()
    if len(rows) != 1:
        raise ValueError(
            f"expected exactly one inactive pilot profile/Data-term binding, found {len(rows)}"
        )
    return validate_profile_row(rows[0])


def preflight_profile() -> PilotProfileBinding:
    conn = connect()
    try:
        binding = load_pilot_profile(conn)
        conn.rollback()
        return binding
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_fresh_pilot_record(
    binding: PilotProfileBinding,
) -> tuple[object, str]:
    connector = SuccessFactorsPreviewConnector(
        target_key=PILOT_TARGET_KEY,
        max_detail_pages=PILOT_PAGE_SIZE,
    )
    records, final_url = connector.fetch_jobs(binding.profile, binding.term)
    if len(records) != 1:
        raise ValueError(f"fresh E.ON pilot fetch must return exactly one record, found {len(records)}")
    return records[0], final_url


def _insert_ingestion_run(
    cur: psycopg.Cursor[Any],
    *,
    binding: PilotProfileBinding,
    requested_url: str,
) -> int:
    cur.execute(
        """
        INSERT INTO ingestion_runs (
            source_name,
            search_profile_id,
            search_term_id,
            search_term,
            requested_url
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            PILOT_SOURCE_NAME,
            binding.profile.id,
            binding.term.id,
            binding.term.search_term,
            requested_url,
        ),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("pilot ingestion run insert returned no id")
    return int(row["id"])


def _insert_or_load_raw_job(
    cur: psycopg.Cursor[Any],
    *,
    record: object,
    ingestion_run_id: int,
    search_profile_id: int,
) -> tuple[dict[str, Any], bool]:
    cur.execute(
        """
        INSERT INTO raw_jobs (
            source_name,
            source_url,
            external_job_id,
            raw_data,
            ingestion_run_id,
            search_profile_id
        )
        VALUES (%s, %s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (source_name, external_job_id)
        WHERE external_job_id IS NOT NULL
        DO NOTHING
        RETURNING id, source_name, external_job_id, source_url, raw_data
        """,
        (
            record.source_name,
            record.source_url,
            record.external_job_id,
            json.dumps(record.raw_data, ensure_ascii=False),
            ingestion_run_id,
            search_profile_id,
        ),
    )
    inserted = cur.fetchone()
    if inserted is not None:
        return dict(inserted), True

    cur.execute(
        """
        SELECT id, source_name, external_job_id, source_url, raw_data
        FROM raw_jobs
        WHERE source_name = %s
          AND external_job_id = %s
        FOR SHARE
        """,
        (PILOT_SOURCE_NAME, EXPECTED_EXTERNAL_JOB_ID),
    )
    existing = cur.fetchone()
    if existing is None:
        raise RuntimeError("pilot duplicate lookup returned no raw job")
    existing_dict = dict(existing)
    if not is_authorized_pilot_raw_data(existing_dict["raw_data"]):
        raise ValueError(
            "existing raw job is not an explicitly authorized pilot dataset; "
            "refusing to reuse preview or unrelated data"
        )
    return existing_dict, False


def _record_observation(
    cur: psycopg.Cursor[Any],
    *,
    raw_job: Mapping[str, Any],
    ingestion_run_id: int,
) -> None:
    cur.execute(
        """
        INSERT INTO job_observations (
            source_name,
            external_job_id,
            source_url,
            ingestion_run_id,
            raw_job_id,
            is_seen
        )
        VALUES (%s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (
            ingestion_run_id,
            source_name,
            external_job_id
        )
        WHERE external_job_id IS NOT NULL
        DO UPDATE SET
            source_url = EXCLUDED.source_url,
            raw_job_id = EXCLUDED.raw_job_id,
            is_seen = TRUE
        """,
        (
            raw_job["source_name"],
            raw_job["external_job_id"],
            raw_job["source_url"],
            ingestion_run_id,
            raw_job["id"],
        ),
    )


def _upsert_silver_job(cur: psycopg.Cursor[Any], silver_job: Mapping[str, Any]) -> int:
    cur.execute(
        """
        INSERT INTO silver_jobs (
            raw_job_id,
            source_name,
            external_job_id,
            source_url,
            title,
            company_name,
            city,
            postal_code,
            country,
            publication_date,
            normalized_title,
            normalized_company_name,
            normalized_location,
            canonical_status,
            canonical_source_type,
            canonical_key_candidate
        )
        VALUES (
            %(raw_job_id)s,
            %(source_name)s,
            %(external_job_id)s,
            %(source_url)s,
            %(title)s,
            %(company_name)s,
            %(city)s,
            %(postal_code)s,
            %(country)s,
            %(publication_date)s,
            %(normalized_title)s,
            %(normalized_company_name)s,
            %(normalized_location)s,
            %(canonical_status)s,
            %(canonical_source_type)s,
            %(canonical_key_candidate)s
        )
        ON CONFLICT (raw_job_id)
        DO UPDATE SET
            source_name = EXCLUDED.source_name,
            external_job_id = EXCLUDED.external_job_id,
            source_url = EXCLUDED.source_url,
            title = EXCLUDED.title,
            company_name = EXCLUDED.company_name,
            city = EXCLUDED.city,
            postal_code = EXCLUDED.postal_code,
            country = EXCLUDED.country,
            publication_date = EXCLUDED.publication_date,
            normalized_title = EXCLUDED.normalized_title,
            normalized_company_name = EXCLUDED.normalized_company_name,
            normalized_location = EXCLUDED.normalized_location,
            canonical_status = EXCLUDED.canonical_status,
            canonical_source_type = EXCLUDED.canonical_source_type,
            canonical_key_candidate = EXCLUDED.canonical_key_candidate,
            normalized_at = NOW(),
            updated_at = NOW()
        RETURNING id
        """,
        silver_job,
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("pilot Silver upsert returned no id")
    return int(row["id"])


def _record_processing_decision(
    cur: psycopg.Cursor[Any],
    *,
    raw_job_id: int,
) -> None:
    cur.execute(
        """
        INSERT INTO silver_processing_decisions (
            raw_job_id,
            decision,
            reason,
            role_matches,
            skill_matches,
            accessibility_matches
        )
        VALUES (%s, 'included', %s, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)
        ON CONFLICT (raw_job_id)
        DO UPDATE SET
            decision = EXCLUDED.decision,
            reason = EXCLUDED.reason,
            role_matches = EXCLUDED.role_matches,
            skill_matches = EXCLUDED.skill_matches,
            accessibility_matches = EXCLUDED.accessibility_matches,
            decided_at = NOW()
        """,
        (raw_job_id, "explicitly_authorized_eon_data_pilot"),
    )


def _load_product_readiness(
    cur: psycopg.Cursor[Any],
    *,
    silver_job_id: int,
) -> dict[str, Any]:
    cur.execute(
        """
        SELECT *
        FROM gold_product_v1_job_readiness
        WHERE silver_job_id = %s
        """,
        (silver_job_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("Product V1 readiness view returned no pilot row")
    return dict(row)


def _finish_ingestion_run(
    cur: psycopg.Cursor[Any],
    *,
    ingestion_run_id: int,
    inserted: bool,
) -> None:
    cur.execute(
        """
        UPDATE ingestion_runs
        SET
            finished_at = NOW(),
            status = 'success',
            total_loaded = 1,
            inserted_count = %s,
            duplicate_count = %s
        WHERE id = %s
        """,
        (1 if inserted else 0, 0 if inserted else 1, ingestion_run_id),
    )
    if cur.rowcount != 1:
        raise RuntimeError("pilot ingestion run finalization did not update one row")


def apply_pipeline_transaction(
    conn: psycopg.Connection[Any],
    *,
    record: object,
    expected_binding: PilotProfileBinding,
    requested_url: str,
) -> PilotApplyResult:
    with conn.cursor() as cur:
        binding = load_pilot_profile(conn, lock=True)
        if binding != expected_binding:
            raise ValueError("pilot profile changed between preflight and apply")
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"{PILOT_SOURCE_NAME}:{EXPECTED_EXTERNAL_JOB_ID}",),
        )
        ingestion_run_id = _insert_ingestion_run(
            cur,
            binding=binding,
            requested_url=requested_url,
        )
        raw_job, inserted = _insert_or_load_raw_job(
            cur,
            record=record,
            ingestion_run_id=ingestion_run_id,
            search_profile_id=binding.profile.id,
        )
        _record_observation(
            cur,
            raw_job=raw_job,
            ingestion_run_id=ingestion_run_id,
        )
        silver_job = transform_raw_job_to_silver(raw_job)
        silver_job_id = _upsert_silver_job(cur, silver_job)
        _record_processing_decision(cur, raw_job_id=int(raw_job["id"]))
        readiness = _load_product_readiness(cur, silver_job_id=silver_job_id)
        _finish_ingestion_run(
            cur,
            ingestion_run_id=ingestion_run_id,
            inserted=inserted,
        )

    return PilotApplyResult(
        ingestion_run_id=ingestion_run_id,
        raw_job_id=int(raw_job["id"]),
        raw_job_inserted=inserted,
        silver_job_id=silver_job_id,
        product_readiness_status=str(readiness["product_readiness_status"]),
        readiness=readiness,
    )


def run_apply(
    *,
    evidence: PreviewApprovalEvidence,
    binding: PilotProfileBinding,
    reviewed_by: str,
    approval_token: str,
) -> PilotApplyResult:
    fresh_record, final_url = fetch_fresh_pilot_record(binding)
    authorized_record = authorize_fresh_record_for_pipeline(
        fresh_record,
        evidence=evidence,
        reviewed_by=reviewed_by,
        approval_token=approval_token,
    )

    conn = connect()
    try:
        result = apply_pipeline_transaction(
            conn,
            record=authorized_record,
            expected_binding=binding,
            requested_url=final_url,
        )
        conn.commit()
        return result
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def write_report(
    *,
    output_dir: Path,
    evidence: PreviewApprovalEvidence,
    binding: PilotProfileBinding,
    reviewed_by: str,
    apply_result: PilotApplyResult | None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"eon_controlled_pilot_ingestion_{stamp}.json"
    payload = {
        "schema_version": "eon_controlled_pilot_ingestion_audit.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "pilot_key": PILOT_KEY,
        "mode": "apply" if apply_result is not None else "dry_run",
        "reviewed_by": reviewed_by,
        "preview_approval_evidence": asdict(evidence),
        "profile": {
            "profile_id": binding.profile.id,
            "profile_name": binding.profile.profile_name,
            "source_name": binding.profile.source_name,
            "is_active": binding.profile_is_active,
            "search_term_id": binding.term.id,
            "search_term": binding.term.search_term,
            "term_is_active": binding.term_is_active,
            "page_size": binding.profile.page_size,
        },
        "apply_result": asdict(apply_result) if apply_result is not None else None,
        "review_output_only_not_pipeline_input": True,
        "boundary": {
            "preview_artifact_used_as_job_data": False,
            "fresh_live_fetch_required_for_apply": True,
            "max_records": 1,
            "max_http_requests": 2 if apply_result is not None else 0,
            "provider_requests": 0,
            "assessment_inserted": False,
            "score_invented": False,
            "top_jobs_forced": False,
            "scheduler_changed": False,
            "profile_activated": False,
            "production_activation_allowed": False,
            "database_mutation": apply_result is not None,
            "bronze_silver_atomic_transaction": True,
        },
    }
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate or explicitly run the isolated E.ON Bronze-to-Product-V1 pilot."
    )
    parser.add_argument("--preview-artifact", type=Path, required=True)
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.reviewed_by.strip():
        raise SystemExit("--reviewed-by must not be blank")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit(f"--apply requires --approval-token {APPROVAL_TOKEN}")
    if not args.apply and args.approval_token:
        raise SystemExit("--approval-token is accepted only together with --apply")

    try:
        evidence = load_preview_approval_evidence(args.preview_artifact)
        binding = preflight_profile()
        apply_result = (
            run_apply(
                evidence=evidence,
                binding=binding,
                reviewed_by=args.reviewed_by,
                approval_token=args.approval_token,
            )
            if args.apply
            else None
        )
        report_path = write_report(
            output_dir=args.output_dir,
            evidence=evidence,
            binding=binding,
            reviewed_by=args.reviewed_by,
            apply_result=apply_result,
        )
    except (OSError, ValueError, RuntimeError, psycopg.Error) as exc:
        raise SystemExit(str(exc)) from exc

    print("E.ON controlled pilot ingestion")
    print(f"mode: {'apply' if apply_result is not None else 'dry_run'}")
    print(f"preview_artifact_sha256: {evidence.artifact_sha256}")
    print(f"profile_active: {str(binding.profile_is_active).lower()}")
    print("provider_requests: 0")
    print("scheduler_changed: false")
    if apply_result is not None:
        print(f"ingestion_run_id: {apply_result.ingestion_run_id}")
        print(f"raw_job_id: {apply_result.raw_job_id}")
        print(f"raw_job_inserted: {str(apply_result.raw_job_inserted).lower()}")
        print(f"silver_job_id: {apply_result.silver_job_id}")
        print(f"product_readiness_status: {apply_result.product_readiness_status}")
        if apply_result.product_readiness_status == "assessment_required":
            print("STOP: assessment_required; no assessment or score was created.")
    else:
        print("network_requests: 0")
        print("database_mutation: false")
    print(f"artifact_json: {report_path}")
    print(f"RESULT: {APPLY_RESULT if apply_result is not None else DRY_RUN_RESULT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
