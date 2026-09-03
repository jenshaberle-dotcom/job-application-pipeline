"""Bounded live Market Sensor scout for E2E-SLICE-001.

This operator-side probe reads active sensor profiles from PostgreSQL and performs
bounded live GETs through the existing registered sensor connectors. It does not
write to PostgreSQL and does not ingest Bronze/Silver/Gold rows.

Market Sensors discover companies, not jobs. Job records are observation evidence
that a company exists and may be relevant. A new job at a company already known to
the pipeline is therefore not a new Market Sensor discovery. When a previously
unknown company is observed through at least one role-relevant job signal, one
company can be held out of the pipeline as immutable discovery evidence for the
later cold E2E proof. The reservation is a local JSON artifact only; it deliberately
does not create an Employer-Origin candidate or otherwise pre-consume the cold path.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.registry import SourceRole, build_default_connector_registry
from src.search_intelligence.product_v1_contenders import classify_role_title


DEFAULT_OUTPUT = Path(".runtime/e2e/e2e_slice_001_market_sensor_scout.json")
DEFAULT_RESERVATION = Path(".runtime/e2e/e2e_slice_001_reserved_company.json")


@dataclass(frozen=True)
class ProfileSpec:
    id: int
    profile_name: str
    source_name: str
    search_location: str | None
    search_radius_km: int | None
    offer_type: int | None
    page_size: int
    legacy_search_term: str | None


@dataclass(frozen=True)
class TermSpec:
    id: int | None
    search_term: str


@dataclass(frozen=True)
class Observation:
    source_name: str
    profile_name: str
    search_term: str
    external_job_id: str | None
    source_url: str
    title: str
    company_name: str
    location: str
    role_profile_match: bool
    role_tier: str | None
    role_family: str | None
    role_signals: tuple[str, ...]
    company_known: bool


def _normalize_company(value: object) -> str:
    text = str(value or "").casefold()
    return re.sub(r"[^a-z0-9]+", "", text)


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _ba_location(job: Mapping[str, object]) -> str:
    raw = job.get("arbeitsort")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if not isinstance(raw, Mapping):
        return ""
    return " ".join(
        part
        for part in (
            _clean_text(raw.get("plz")),
            _clean_text(raw.get("ort")),
            _clean_text(raw.get("land")),
        )
        if part
    )


def _record_fields(record: RawJobRecord) -> tuple[str, str, str]:
    raw = record.raw_data if isinstance(record.raw_data, Mapping) else {}
    job = raw.get("job")
    card = raw.get("result_card")

    if record.source_name == "bundesagentur_fuer_arbeit" and isinstance(job, Mapping):
        return (
            _clean_text(job.get("titel")),
            _clean_text(job.get("arbeitgeber")),
            _ba_location(job),
        )

    if isinstance(card, Mapping):
        return (
            _clean_text(card.get("title")),
            _clean_text(card.get("company_name")),
            _clean_text(card.get("location")),
        )

    if isinstance(job, Mapping):
        location = job.get("location")
        if isinstance(location, Mapping):
            location = location.get("name") or location.get("city")
        return (
            _clean_text(job.get("title")),
            _clean_text(job.get("company_name")),
            _clean_text(location),
        )

    return "", "", ""


def observation_from_record(
    record: RawJobRecord,
    *,
    profile_name: str,
    search_term: str,
    known_companies: set[str],
) -> Observation:
    title, company, location = _record_fields(record)
    role = classify_role_title(title) if title else None
    normalized_company = _normalize_company(company)
    return Observation(
        source_name=record.source_name,
        profile_name=profile_name,
        search_term=search_term,
        external_job_id=record.external_job_id,
        source_url=record.source_url,
        title=title,
        company_name=company,
        location=location,
        role_profile_match=role is not None,
        role_tier=(str(role.tier) if role else None),
        role_family=(str(role.family) if role else None),
        role_signals=(tuple(str(item) for item in role.signals) if role else ()),
        company_known=(not normalized_company or normalized_company in known_companies),
    )


def fresh_company_names(observations: Sequence[Observation]) -> list[str]:
    """Return unique previously unknown companies, never merely new job records."""

    return sorted(
        {
            row.company_name
            for row in observations
            if row.company_name and not row.company_known
        },
        key=str.casefold,
    )


def choose_reservation(observations: Sequence[Observation]) -> Observation | None:
    candidates = [
        row
        for row in observations
        if row.company_name and not row.company_known and row.role_profile_match
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda row: (
            row.source_name,
            row.company_name.casefold(),
            row.title.casefold(),
            row.source_url,
        ),
    )[0]


def _load_profiles(
    conn: psycopg.Connection[object],
    *,
    page_size_cap: int,
) -> list[ProfileSpec]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                profile_name,
                source_name,
                search_location,
                search_radius_km,
                offer_type,
                LEAST(page_size, %s) AS page_size,
                search_term
            FROM search_profiles
            WHERE is_active
            ORDER BY source_name, id
            """,
            (page_size_cap,),
        )
        rows = cur.fetchall()
    return [
        ProfileSpec(
            id=int(row["id"]),
            profile_name=str(row["profile_name"]),
            source_name=str(row["source_name"]),
            search_location=(
                str(row["search_location"])
                if row.get("search_location") is not None
                else None
            ),
            search_radius_km=(
                int(row["search_radius_km"])
                if row.get("search_radius_km") is not None
                else None
            ),
            offer_type=(
                int(row["offer_type"])
                if row.get("offer_type") is not None
                else None
            ),
            page_size=int(row["page_size"]),
            legacy_search_term=(
                str(row["search_term"]).strip()
                if row.get("search_term") is not None
                and str(row["search_term"]).strip()
                else None
            ),
        )
        for row in rows
    ]


def _load_terms(
    conn: psycopg.Connection[object],
    profile_ids: Sequence[int],
) -> dict[int, list[TermSpec]]:
    by_profile: dict[int, list[TermSpec]] = defaultdict(list)
    if not profile_ids:
        return by_profile
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT search_profile_id, id, search_term
            FROM search_terms
            WHERE is_active
              AND search_profile_id = ANY(%s)
            ORDER BY search_profile_id, id
            """,
            (list(profile_ids),),
        )
        for row in cur.fetchall():
            by_profile[int(row["search_profile_id"])].append(
                TermSpec(id=int(row["id"]), search_term=str(row["search_term"]))
            )
    return by_profile


def _load_known_companies(conn: psycopg.Connection[object]) -> set[str]:
    known: set[str] = set()
    queries = (
        "SELECT company_name FROM silver_jobs WHERE company_name IS NOT NULL",
        "SELECT company_name FROM employer_origin_source_candidates WHERE company_name IS NOT NULL",
    )
    for query in queries:
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
        except psycopg.Error:
            conn.rollback()
            continue
        for row in rows:
            normalized = _normalize_company(row["company_name"])
            if normalized:
                known.add(normalized)
    return known


def _search_profile(spec: ProfileSpec) -> SearchProfile:
    return SearchProfile(
        id=spec.id,
        profile_name=spec.profile_name,
        source_name=spec.source_name,
        search_location=spec.search_location,
        search_radius_km=spec.search_radius_km,
        offer_type=spec.offer_type,
        page_size=spec.page_size,
    )


def _term_specs(
    profile: ProfileSpec,
    terms_by_profile: Mapping[int, Sequence[TermSpec]],
    *,
    max_terms: int,
) -> list[TermSpec]:
    terms = list(terms_by_profile.get(profile.id, ()))
    if not terms and profile.legacy_search_term:
        terms = [TermSpec(id=None, search_term=profile.legacy_search_term)]
    return terms[:max_terms]


def _reservation_payload(observation: Observation) -> dict[str, object]:
    evidence = asdict(observation)
    encoded = json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return {
        "schema": "job_application_pipeline.e2e_slice_001.reserved_company.v1",
        "reserved_at": datetime.now(UTC).isoformat(),
        "status": "held_out_of_pipeline_for_cold_e2e",
        "must_not_pre_ingest": True,
        "discovery_unit": "company",
        "job_record_semantics": "discovery_evidence_only",
        "discovery_evidence_sha256": hashlib.sha256(encoded).hexdigest(),
        "observation": evidence,
        "required_later_path": [
            "market_sensor",
            "company_discovery",
            "employer_origin_resolution",
            "connector_auto_generation",
            "connector_fixture_job_test_plane_only",
            "real_current_vacancy_with_detail",
            "bronze",
            "silver",
            "gold",
            "capability_and_hard_filters",
            "ranking",
            "ui",
            "supported_cv_and_application_letter",
            "docx_pdf_zip",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--reservation-output",
        "--reserve-output",
        dest="reservation_output",
        type=Path,
        default=DEFAULT_RESERVATION,
    )
    parser.add_argument("--page-size-cap", type=int, default=10)
    parser.add_argument("--max-profiles-per-sensor", type=int, default=2)
    parser.add_argument("--max-terms-per-profile", type=int, default=2)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.page_size_cap < 1 or args.max_profiles_per_sensor < 1 or args.max_terms_per_profile < 1:
        raise SystemExit("All bounds must be >= 1")

    registry = build_default_connector_registry()
    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(),
        row_factory=dict_row,
    ) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        profiles = _load_profiles(conn, page_size_cap=args.page_size_cap)
        terms_by_profile = _load_terms(conn, [profile.id for profile in profiles])
        known_companies = _load_known_companies(conn)
        conn.rollback()

    sensor_profiles: dict[str, list[ProfileSpec]] = defaultdict(list)
    for profile in profiles:
        try:
            role = registry.role_for(profile.source_name)
        except ValueError:
            continue
        if role == SourceRole.SENSOR:
            sensor_profiles[profile.source_name].append(profile)

    report_sources: list[dict[str, object]] = []
    observations: list[Observation] = []

    for source_name in sorted(sensor_profiles):
        source_profiles = sensor_profiles[source_name][: args.max_profiles_per_sensor]
        connector = registry.create(source_name)
        source_runs: list[dict[str, object]] = []
        for profile in source_profiles:
            terms = _term_specs(
                profile,
                terms_by_profile,
                max_terms=args.max_terms_per_profile,
            )
            if not terms:
                source_runs.append(
                    {
                        "profile_name": profile.profile_name,
                        "status": "no_active_search_terms",
                        "error": None,
                        "observed_job_count": 0,
                    }
                )
                continue
            for term in terms:
                started = datetime.now(UTC)
                try:
                    records, final_url = connector.fetch_jobs(
                        _search_profile(profile),
                        SearchTerm(search_term=term.search_term, id=term.id),
                    )
                    current = [
                        observation_from_record(
                            record,
                            profile_name=profile.profile_name,
                            search_term=term.search_term,
                            known_companies=known_companies,
                        )
                        for record in records
                    ]
                    observations.extend(current)
                    status = "healthy"
                    error = None
                except Exception as exc:  # noqa: BLE001 - exact live sensor error is evidence
                    current = []
                    final_url = None
                    status = "failed"
                    error = f"{type(exc).__name__}: {exc}"
                source_runs.append(
                    {
                        "profile_name": profile.profile_name,
                        "search_term": term.search_term,
                        "status": status,
                        "error": error,
                        "final_url": final_url,
                        "duration_seconds": round(
                            (datetime.now(UTC) - started).total_seconds(), 3
                        ),
                        "observed_job_count": len(current),
                    }
                )

        source_status = (
            "healthy"
            if source_runs and all(run["status"] == "healthy" for run in source_runs)
            else "failed"
        )
        report_sources.append(
            {
                "source_name": source_name,
                "source_role": "sensor",
                "status": source_status,
                "profiles_probed": len(source_profiles),
                "runs": source_runs,
            }
        )

    reservation = choose_reservation(observations)
    fresh_companies = fresh_company_names(observations)
    report = {
        "schema": "job_application_pipeline.e2e_slice_001.market_sensor_scout.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "summary": {
            "configured_sensor_count": len(sensor_profiles),
            "healthy_sensor_count": sum(
                source["status"] == "healthy" for source in report_sources
            ),
            "job_observation_count": len(observations),
            "fresh_company_count": len(fresh_companies),
            "discovery_unit": "company",
            "reservation_created": reservation is not None,
        },
        "sources": report_sources,
        "fresh_companies": fresh_companies,
        "job_observations": [asdict(row) for row in observations],
        "reservation": asdict(reservation) if reservation else None,
        "boundaries": {
            "database_transaction": "read_only",
            "database_writes": 0,
            "network_gets": True,
            "market_sensor_discovery_unit": "company",
            "job_records_are_discovery_evidence_only": True,
            "bronze_writes": 0,
            "silver_writes": 0,
            "gold_writes": 0,
            "candidate_writes": 0,
            "connector_generation": 0,
            "ranking_writes": 0,
            "provider_requests": 0,
            "fixture_job_product_writes": 0,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    if reservation is not None:
        args.reservation_output.parent.mkdir(parents=True, exist_ok=True)
        args.reservation_output.write_text(
            json.dumps(
                _reservation_payload(reservation),
                indent=2,
                ensure_ascii=False,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )

    print("=== E2E-SLICE-001 MARKET SENSOR LIVE SCOUT ===")
    print("DISCOVERY_UNIT=company")
    print(f"CONFIGURED_SENSORS={len(sensor_profiles)}")
    print(f"HEALTHY_SENSORS={report['summary']['healthy_sensor_count']}")
    for source in report_sources:
        print(
            f"SENSOR={source['source_name']}|{source['status']}|"
            f"profiles={source['profiles_probed']}"
        )
        for run in source["runs"]:
            print(
                f"SENSOR_RUN={source['source_name']}|{run['profile_name']}|"
                f"{run.get('search_term') or '-'}|{run['status']}|"
                f"job_signals={run['observed_job_count']}|"
                f"seconds={run.get('duration_seconds', 0)}"
            )
            if run.get("error"):
                print(
                    f"SENSOR_ERROR={source['source_name']}|"
                    f"{run['profile_name']}|{run['error']}"
                )
    print(f"JOB_OBSERVATIONS={len(observations)}")
    print(f"FRESH_COMPANIES={len(fresh_companies)}")
    for company in fresh_companies[:20]:
        print(f"FRESH_COMPANY={company}")
    if reservation is not None:
        print(
            "RESERVED_E2E_COMPANY="
            f"{reservation.source_name}|{reservation.company_name}|"
            f"{reservation.title}|{reservation.source_url}"
        )
        print(f"reservation={args.reservation_output.resolve()}")
    else:
        print("RESERVED_E2E_COMPANY=NONE")
    print("DATABASE_WRITES=0")
    print("BRONZE_WRITES=0")
    print("SILVER_WRITES=0")
    print("GOLD_WRITES=0")
    print(f"artifact={args.output.resolve()}")

    if not sensor_profiles:
        print("E2E_SLICE_001_MARKET_SENSOR_SCOUT=BLOCKED_NO_ACTIVE_SENSORS")
        return 2
    failed = [source for source in report_sources if source["status"] != "healthy"]
    if failed:
        print("E2E_SLICE_001_MARKET_SENSOR_SCOUT=BLOCKED_SENSOR_FAILURE")
        return 2
    print("E2E_SLICE_001_MARKET_SENSOR_SCOUT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
