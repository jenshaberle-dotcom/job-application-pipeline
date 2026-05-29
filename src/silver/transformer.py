from datetime import date


def parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def first_location(job_data: dict) -> dict:
    location = job_data.get("arbeitsort")

    if isinstance(location, dict):
        return location

    if isinstance(location, list) and location:
        first = location[0]
        if isinstance(first, dict):
            return first

    return {}


def normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = " ".join(value.strip().lower().split())

    return normalized or None


def build_normalized_location(city: object, postal_code: object, country: object) -> str | None:
    parts = [
        normalize_text(city),
        normalize_text(postal_code),
        normalize_text(country),
    ]

    normalized_parts = [part for part in parts if part]

    if not normalized_parts:
        return None

    return " | ".join(normalized_parts)


def build_canonical_key_candidate(
    normalized_company_name: str | None,
    normalized_title: str | None,
    normalized_location: str | None,
) -> str | None:
    parts = [
        normalized_company_name,
        normalized_title,
        normalized_location,
    ]

    key_parts = [part for part in parts if part]

    if not key_parts:
        return None

    return " :: ".join(key_parts)


def canonical_source_type(source_name: object) -> str:
    if isinstance(source_name, str) and source_name.startswith("finanz_informatik:"):
        return "employer_origin_career_site"

    return "unknown"


def add_canonicalization_fields(job: dict) -> dict:
    normalized_title = normalize_text(job.get("title"))
    normalized_company_name = normalize_text(job.get("company_name"))
    normalized_location = build_normalized_location(
        job.get("city"),
        job.get("postal_code"),
        job.get("country"),
    )

    job["normalized_title"] = normalized_title
    job["normalized_company_name"] = normalized_company_name
    job["normalized_location"] = normalized_location
    job["canonical_status"] = "discovery_only"
    job["canonical_source_type"] = canonical_source_type(job.get("source_name"))
    job["canonical_key_candidate"] = build_canonical_key_candidate(
        normalized_company_name,
        normalized_title,
        normalized_location,
    )

    return job


def transform_bundesagentur_raw_job(raw_job: dict) -> dict:
    raw_data = raw_job["raw_data"]
    job_data = raw_data.get("job", {})
    location = first_location(job_data)

    publication_date = parse_date(
        job_data.get("aktuelleVeroeffentlichungsdatum")
        or job_data.get("veroeffentlichtAm")
        or job_data.get("datum")
    )

    return add_canonicalization_fields(
        {
            "raw_job_id": raw_job["id"],
            "source_name": raw_job["source_name"],
            "external_job_id": raw_job["external_job_id"],
            "source_url": raw_job["source_url"],
            "title": job_data.get("titel"),
            "company_name": job_data.get("arbeitgeber"),
            "city": location.get("ort"),
            "postal_code": location.get("plz"),
            "country": location.get("land"),
            "publication_date": publication_date,
        }
    )


def transform_greenhouse_raw_job(raw_job: dict) -> dict:
    raw_data = raw_job["raw_data"]
    job_data = raw_data.get("job", {})
    location = job_data.get("location") or {}

    publication_date = parse_date(
        job_data.get("first_published")
        or job_data.get("updated_at")
    )

    return add_canonicalization_fields(
        {
            "raw_job_id": raw_job["id"],
            "source_name": raw_job["source_name"],
            "external_job_id": raw_job["external_job_id"],
            "source_url": job_data.get("absolute_url") or raw_job["source_url"],
            "title": job_data.get("title"),
            "company_name": job_data.get("company_name"),
            "city": location.get("name"),
            "postal_code": None,
            "country": None,
            "publication_date": publication_date,
        }
    )


def transform_personio_raw_job(raw_job: dict) -> dict:
    raw_data = raw_job["raw_data"]
    job_data = raw_data.get("job", {})

    return add_canonicalization_fields(
        {
            "raw_job_id": raw_job["id"],
            "source_name": raw_job["source_name"],
            "external_job_id": raw_job["external_job_id"],
            "source_url": job_data.get("source_url") or raw_job["source_url"],
            "title": job_data.get("title"),
            "company_name": job_data.get("company_name"),
            "city": job_data.get("location"),
            "postal_code": None,
            "country": None,
            "publication_date": None,
        }
    )


def transform_finanz_informatik_raw_job(raw_job: dict) -> dict:
    raw_data = raw_job["raw_data"]
    job_data = raw_data.get("job", {})
    result_card = raw_data.get("result_card", {})

    return add_canonicalization_fields(
        {
            "raw_job_id": raw_job["id"],
            "source_name": raw_job["source_name"],
            "external_job_id": raw_job["external_job_id"],
            "source_url": (
                job_data.get("source_url")
                or result_card.get("detail_url")
                or raw_job["source_url"]
            ),
            "title": job_data.get("title") or result_card.get("title"),
            "company_name": (
                job_data.get("company_name")
                or result_card.get("company_name")
                or "Finanz Informatik GmbH & Co. KG"
            ),
            "city": job_data.get("location") or result_card.get("location"),
            "postal_code": None,
            "country": "DE",
            "publication_date": None,
        }
    )


def transform_stepstone_raw_job(raw_job: dict) -> dict:
    raw_data = raw_job["raw_data"]
    result_card = raw_data.get("result_card", {})

    return add_canonicalization_fields(
        {
            "raw_job_id": raw_job["id"],
            "source_name": raw_job["source_name"],
            "external_job_id": raw_job["external_job_id"],
            "source_url": result_card.get("detail_url") or raw_job["source_url"],
            "title": result_card.get("title"),
            "company_name": result_card.get("company_name"),
            "city": result_card.get("location"),
            "postal_code": None,
            "country": None,
            "publication_date": None,
        }
    )


def transform_raw_job_to_silver(raw_job: dict) -> dict:
    source_name = raw_job["source_name"]

    if source_name == "bundesagentur_fuer_arbeit":
        return transform_bundesagentur_raw_job(raw_job)

    if source_name.startswith("greenhouse:"):
        return transform_greenhouse_raw_job(raw_job)

    if source_name.startswith("personio:"):
        return transform_personio_raw_job(raw_job)

    if source_name.startswith("finanz_informatik:"):
        return transform_finanz_informatik_raw_job(raw_job)

    if source_name == "stepstone":
        return transform_stepstone_raw_job(raw_job)

    raise ValueError(f"No Silver transformer implemented for source: {source_name}")


def get_supported_source_patterns() -> list[str]:
    return [
        "bundesagentur_fuer_arbeit",
        "greenhouse:%",
        "personio:%",
        "finanz_informatik:%",
        "stepstone",
    ]
