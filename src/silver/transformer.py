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


def transform_bundesagentur_raw_job(raw_job: dict) -> dict:
    raw_data = raw_job["raw_data"]
    job_data = raw_data.get("job", {})
    location = first_location(job_data)

    publication_date = parse_date(
        job_data.get("aktuelleVeroeffentlichungsdatum")
        or job_data.get("veroeffentlichtAm")
        or job_data.get("datum")
    )

    return {
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


def transform_raw_job_to_silver(raw_job: dict) -> dict:
    source_name = raw_job["source_name"]

    if source_name == "bundesagentur_fuer_arbeit":
        return transform_bundesagentur_raw_job(raw_job)

    raise ValueError(f"No Silver transformer implemented for source: {source_name}")
