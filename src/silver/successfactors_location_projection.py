from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Protocol, Sequence


AUTOMATIC_EVIDENCE_SOURCE = "successfactors_detail_location_field"
_BLOCKED_CITY_VALUES = {
    "flexible",
    "home office",
    "homeoffice",
    "hybrid",
    "remote",
    "work from home",
}
_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")


class SilverRepositoryProtocol(Protocol):
    def get_connection(self) -> Any: ...


@dataclass(frozen=True)
class SilverLocationRow:
    city: str
    country_code: str
    is_primary: bool
    evidence_source: str
    evidence_text: str
    observed_at_utc: str | None

    def identity(self) -> tuple[str, str]:
        return self.city.casefold(), self.country_code.casefold()

    def payload(self) -> dict[str, object]:
        return {
            "city": self.city,
            "country_code": self.country_code,
            "is_primary": self.is_primary,
            "evidence_source": self.evidence_source,
            "evidence_text": self.evidence_text,
            "observed_at_utc": self.observed_at_utc,
        }


@dataclass(frozen=True)
class SilverLocationProjection:
    authoritative: bool
    rows: tuple[SilverLocationRow, ...]

    @property
    def primary(self) -> SilverLocationRow | None:
        return next((row for row in self.rows if row.is_primary), None)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _required_text(value: object, label: str, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    text = " ".join(value.split()).strip(" ,;|")
    if not text:
        raise ValueError(f"{label} must not be blank")
    if len(text) > max_length:
        raise ValueError(f"{label} exceeds {max_length} characters")
    return text


def _normalize_city(value: object, label: str) -> str:
    city = _required_text(value, label, max_length=80)
    if city.casefold() in _BLOCKED_CITY_VALUES:
        raise ValueError(f"{label} is a work model, not a city")
    if any(character.isdigit() for character in city):
        raise ValueError(f"{label} contains digits")
    if ":" in city or "|" in city:
        raise ValueError(f"{label} contains an unsupported delimiter")
    return city


def _normalize_country_code(value: object, label: str) -> str:
    country_code = _required_text(value, label, max_length=2).upper()
    if not _COUNTRY_CODE.fullmatch(country_code):
        raise ValueError(f"{label} must be a two-letter country code")
    return country_code


def build_successfactors_location_projection(
    raw_job: Mapping[str, Any],
    *,
    legacy_city: object,
) -> SilverLocationProjection:
    """Build an authoritative projection only from explicit raw `job.locations`.

    Legacy SuccessFactors raw records predate the structured field. Missing and
    explicit-empty therefore have different meanings:

    - missing: preserve any existing location rows;
    - empty list: authoritative evidence currently contains no locations.
    """

    source_name = raw_job.get("source_name")
    if not isinstance(source_name, str) or not source_name.startswith(
        "successfactors:"
    ):
        return SilverLocationProjection(authoritative=False, rows=())

    raw_data = _mapping(raw_job.get("raw_data"), "raw_job.raw_data")
    job_data = _mapping(raw_data.get("job"), "raw_job.raw_data.job")

    if "locations" not in job_data:
        return SilverLocationProjection(authoritative=False, rows=())

    raw_locations = job_data["locations"]
    if not isinstance(raw_locations, list):
        raise ValueError("raw_job.raw_data.job.locations must be a list")

    observed_at = raw_data.get("observed_at_utc")
    if observed_at is not None and not isinstance(observed_at, str):
        raise ValueError("raw_job.raw_data.observed_at_utc must be a string or null")

    legacy_city_text = (
        " ".join(legacy_city.split()).strip().casefold()
        if isinstance(legacy_city, str)
        else ""
    )

    parsed: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, value in enumerate(raw_locations):
        item = _mapping(value, f"job.locations[{index}]")
        city = _normalize_city(item.get("city"), f"job.locations[{index}].city")
        country_code = _normalize_country_code(
            item.get("country_code"),
            f"job.locations[{index}].country_code",
        )
        evidence_source = _required_text(
            item.get("evidence_source"),
            f"job.locations[{index}].evidence_source",
            max_length=120,
        )
        if evidence_source != AUTOMATIC_EVIDENCE_SOURCE:
            raise ValueError(
                "structured SuccessFactors location evidence source mismatch: "
                f"{evidence_source}"
            )
        evidence_text = _required_text(
            item.get("evidence_text"),
            f"job.locations[{index}].evidence_text",
            max_length=1000,
        )

        identity = city.casefold(), country_code.casefold()
        if identity in seen:
            raise ValueError(
                "duplicate structured SuccessFactors location identity: "
                f"{city}, {country_code}"
            )
        seen.add(identity)
        parsed.append(
            {
                "city": city,
                "country_code": country_code,
                "evidence_source": evidence_source,
                "evidence_text": evidence_text,
            }
        )

    primary_index: int | None = None
    if parsed:
        primary_index = next(
            (
                index
                for index, item in enumerate(parsed)
                if item["city"].casefold() == legacy_city_text
            ),
            0,
        )

    rows = tuple(
        SilverLocationRow(
            city=item["city"],
            country_code=item["country_code"],
            is_primary=index == primary_index,
            evidence_source=item["evidence_source"],
            evidence_text=item["evidence_text"],
            observed_at_utc=observed_at,
        )
        for index, item in enumerate(parsed)
    )
    return SilverLocationProjection(authoritative=True, rows=rows)


def _upsert_silver_job(cur: Any, silver_job: Mapping[str, Any]) -> int:
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
        dict(silver_job),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("Silver upsert returned no id")
    if isinstance(row, Mapping):
        return int(row["id"])
    return int(row[0])


def _synchronize_locations(
    cur: Any,
    *,
    silver_job_id: int,
    projection: SilverLocationProjection,
) -> None:
    if not projection.authoritative:
        return

    primary = projection.primary
    if primary is None:
        cur.execute(
            """
            UPDATE silver_job_locations
            SET is_primary = FALSE,
                updated_at = NOW()
            WHERE silver_job_id = %s
              AND evidence_source = %s
              AND is_primary = TRUE
            """,
            (silver_job_id, AUTOMATIC_EVIDENCE_SOURCE),
        )
    else:
        cur.execute(
            """
            UPDATE silver_job_locations
            SET is_primary = FALSE,
                updated_at = NOW()
            WHERE silver_job_id = %s
              AND evidence_source = %s
              AND is_primary = TRUE
              AND NOT (
                  lower(trim(city)) = lower(trim(%s))
                  AND upper(country_code) = upper(%s)
              )
            """,
            (
                silver_job_id,
                AUTOMATIC_EVIDENCE_SOURCE,
                primary.city,
                primary.country_code,
            ),
        )

    expected_payload = [
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
        (
            silver_job_id,
            AUTOMATIC_EVIDENCE_SOURCE,
            json.dumps(expected_payload, ensure_ascii=False),
        ),
    )

    for row in projection.rows:
        cur.execute(
            """
            INSERT INTO silver_job_locations (
                silver_job_id,
                city,
                country_code,
                is_primary,
                evidence_source,
                evidence_text,
                observed_at_utc
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
            WHERE silver_job_locations.is_primary IS DISTINCT FROM EXCLUDED.is_primary
               OR silver_job_locations.evidence_source IS DISTINCT FROM EXCLUDED.evidence_source
               OR silver_job_locations.evidence_text IS DISTINCT FROM EXCLUDED.evidence_text
               OR silver_job_locations.observed_at_utc IS DISTINCT FROM EXCLUDED.observed_at_utc
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


def write_silver_job_with_successfactors_locations(
    repository: SilverRepositoryProtocol,
    *,
    silver_job: Mapping[str, Any],
    raw_job: Mapping[str, Any],
) -> int:
    """Atomically write one Silver job and its explicit SuccessFactors locations."""

    projection = build_successfactors_location_projection(
        raw_job,
        legacy_city=silver_job.get("city"),
    )

    conn = repository.get_connection()
    try:
        with conn.cursor() as cur:
            silver_job_id = _upsert_silver_job(cur, silver_job)
            _synchronize_locations(
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
