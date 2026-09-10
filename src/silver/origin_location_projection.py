from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Protocol

from src.silver.successfactors_location_projection import (
    write_silver_job_with_successfactors_locations,
)


GENERIC_LOCATION_EVIDENCE_SOURCE = "generic_origin_schema_job_location"
FINANZ_INFORMATIK_LOCATION_EVIDENCE_SOURCE = "finanz_informatik_detail_text"
_ALLOWED_LOCATION_EVIDENCE_SOURCES = frozenset(
    {
        GENERIC_LOCATION_EVIDENCE_SOURCE,
        FINANZ_INFORMATIK_LOCATION_EVIDENCE_SOURCE,
    }
)


class SilverRepositoryProtocol(Protocol):
    def get_connection(self) -> Any: ...


@dataclass(frozen=True)
class OriginLocationRow:
    city: str
    country_code: str
    is_primary: bool
    evidence_source: str
    evidence_text: str
    observed_at_utc: str | None


@dataclass(frozen=True)
class OriginLocationProjection:
    authoritative: bool
    evidence_source: str | None
    rows: tuple[OriginLocationRow, ...]


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip(" ,;|")


def _source_default_evidence(source_name: str) -> str | None:
    if source_name.startswith("generic_origin:"):
        return GENERIC_LOCATION_EVIDENCE_SOURCE
    if source_name.startswith("finanz_informatik:"):
        return FINANZ_INFORMATIK_LOCATION_EVIDENCE_SOURCE
    return None


def build_origin_location_projection(
    raw_job: Mapping[str, Any],
    *,
    legacy_city: object,
) -> OriginLocationProjection:
    """Project explicit pre-Bronze Origin `job.locations` into Silver rows.

    Missing `job.locations` means no authoritative multi-location evidence for this
    parser family and therefore preserves existing rows. An explicit list is
    authoritative for the supported origin parser family. Unknown/blank country
    codes are deliberately not invented; those rows remain in Bronze evidence only.
    """

    source_name = _text(raw_job.get("source_name"))
    evidence_source = _source_default_evidence(source_name)
    if evidence_source is None:
        return OriginLocationProjection(False, None, ())

    raw_data = raw_job.get("raw_data")
    if not isinstance(raw_data, Mapping):
        raise ValueError("raw_job.raw_data must be an object")
    job = raw_data.get("job")
    if not isinstance(job, Mapping):
        raise ValueError("raw_job.raw_data.job must be an object")
    if "locations" not in job:
        return OriginLocationProjection(False, evidence_source, ())

    raw_locations = job.get("locations")
    if not isinstance(raw_locations, list):
        raise ValueError("raw_job.raw_data.job.locations must be a list")

    observed_at = raw_data.get("observed_at_utc")
    if observed_at is not None and not isinstance(observed_at, str):
        raise ValueError("raw_job.raw_data.observed_at_utc must be a string or null")

    legacy = _text(legacy_city).casefold()
    parsed: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(raw_locations):
        if not isinstance(item, Mapping):
            # Old generic Bronze stored location strings; those are not precise
            # enough to become one-to-many Silver authority.
            continue
        city = _text(item.get("city"))
        country_code = _text(item.get("country_code")).upper()
        source = _text(item.get("evidence_source")) or evidence_source
        evidence_text = _text(item.get("evidence_text")) or city
        if not city:
            continue
        if len(country_code) != 2 or not country_code.isalpha():
            continue
        if source not in _ALLOWED_LOCATION_EVIDENCE_SOURCES:
            raise ValueError(f"unsupported origin location evidence source: {source}")
        identity = city.casefold(), country_code.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        parsed.append(
            {
                "city": city,
                "country_code": country_code,
                "evidence_source": source,
                "evidence_text": evidence_text,
            }
        )

    primary_index: int | None = None
    if parsed:
        primary_index = next(
            (
                index
                for index, row in enumerate(parsed)
                if row["city"].casefold() == legacy
                or row["city"].casefold() in legacy
            ),
            0,
        )

    rows = tuple(
        OriginLocationRow(
            city=row["city"],
            country_code=row["country_code"],
            is_primary=index == primary_index,
            evidence_source=row["evidence_source"],
            evidence_text=row["evidence_text"],
            observed_at_utc=observed_at,
        )
        for index, row in enumerate(parsed)
    )
    return OriginLocationProjection(True, evidence_source, rows)


def _upsert_silver_job(cur: Any, silver_job: Mapping[str, Any]) -> int:
    cur.execute(
        """
        INSERT INTO silver_jobs (
            raw_job_id, source_name, external_job_id, source_url, title,
            company_name, city, postal_code, country, publication_date,
            normalized_title, normalized_company_name, normalized_location,
            canonical_status, canonical_source_type, canonical_key_candidate
        )
        VALUES (
            %(raw_job_id)s, %(source_name)s, %(external_job_id)s, %(source_url)s,
            %(title)s, %(company_name)s, %(city)s, %(postal_code)s, %(country)s,
            %(publication_date)s, %(normalized_title)s, %(normalized_company_name)s,
            %(normalized_location)s, %(canonical_status)s,
            %(canonical_source_type)s, %(canonical_key_candidate)s
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
        dict(silver_job),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("Silver upsert returned no id")
    if isinstance(row, Mapping):
        return int(row["id"])
    return int(row[0])


def _synchronize_origin_locations(
    cur: Any,
    *,
    silver_job_id: int,
    projection: OriginLocationProjection,
) -> None:
    if not projection.authoritative or not projection.evidence_source:
        return

    evidence_source = projection.evidence_source
    primary = next((row for row in projection.rows if row.is_primary), None)
    if primary is None:
        cur.execute(
            """
            UPDATE silver_job_locations
            SET is_primary = FALSE, updated_at = NOW()
            WHERE silver_job_id = %s
              AND evidence_source = %s
              AND is_primary = TRUE
            """,
            (silver_job_id, evidence_source),
        )
    else:
        cur.execute(
            """
            UPDATE silver_job_locations
            SET is_primary = FALSE, updated_at = NOW()
            WHERE silver_job_id = %s
              AND evidence_source = %s
              AND is_primary = TRUE
              AND NOT (
                  lower(trim(city)) = lower(trim(%s))
                  AND upper(country_code) = upper(%s)
              )
            """,
            (silver_job_id, evidence_source, primary.city, primary.country_code),
        )

    expected = [
        {"city": row.city, "country_code": row.country_code}
        for row in projection.rows
    ]
    cur.execute(
        """
        DELETE FROM silver_job_locations AS existing
        WHERE existing.silver_job_id = %s
          AND existing.evidence_source = %s
          AND NOT EXISTS (
              SELECT 1
              FROM jsonb_to_recordset(%s::jsonb)
                   AS expected(city TEXT, country_code TEXT)
              WHERE lower(trim(expected.city)) = lower(trim(existing.city))
                AND upper(expected.country_code) = upper(existing.country_code)
          )
        """,
        (silver_job_id, evidence_source, json.dumps(expected, ensure_ascii=False)),
    )

    for row in projection.rows:
        cur.execute(
            """
            INSERT INTO silver_job_locations (
                silver_job_id, city, country_code, is_primary, evidence_source,
                evidence_text, observed_at_utc
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (
                silver_job_id,
                lower(trim(city)),
                lower(trim(country_code))
            )
            DO UPDATE SET
                is_primary = EXCLUDED.is_primary,
                evidence_source = EXCLUDED.evidence_source,
                evidence_text = EXCLUDED.evidence_text,
                observed_at_utc = EXCLUDED.observed_at_utc,
                updated_at = NOW()
            """,
            (
                silver_job_id,
                row.city,
                row.country_code,
                row.is_primary,
                row.evidence_source,
                row.evidence_text,
                row.observed_at_utc,
            ),
        )


def write_silver_job_with_origin_locations(
    repository: SilverRepositoryProtocol,
    *,
    silver_job: Mapping[str, Any],
    raw_job: Mapping[str, Any],
) -> int:
    """Atomically write Silver plus structured location evidence for origin families."""

    source_name = _text(raw_job.get("source_name"))
    if source_name.startswith("successfactors:"):
        return write_silver_job_with_successfactors_locations(
            repository,
            silver_job=silver_job,
            raw_job=raw_job,
        )

    projection = build_origin_location_projection(
        raw_job,
        legacy_city=silver_job.get("city"),
    )
    conn = repository.get_connection()
    try:
        with conn.cursor() as cur:
            silver_job_id = _upsert_silver_job(cur, silver_job)
            _synchronize_origin_locations(
                cur,
                silver_job_id=silver_job_id,
                projection=projection,
            )
        conn.commit()
        return silver_job_id
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


__all__ = [
    "FINANZ_INFORMATIK_LOCATION_EVIDENCE_SOURCE",
    "GENERIC_LOCATION_EVIDENCE_SOURCE",
    "OriginLocationProjection",
    "OriginLocationRow",
    "build_origin_location_projection",
    "write_silver_job_with_origin_locations",
]
