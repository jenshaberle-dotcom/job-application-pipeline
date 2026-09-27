"""Read-only adapter from existing connector records into Census observations."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from src.connectors.base import RawJobRecord
from src.search_intelligence.employer_discovery_census import MarketJobObservation


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _ba_location(value: object) -> str:
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, Mapping):
        return _clean(value)
    return " ".join(
        part
        for part in (
            _clean(value.get("plz")),
            _clean(value.get("ort")),
            _clean(value.get("land")),
        )
        if part
    )


def market_observation_from_raw_record(
    record: RawJobRecord,
    *,
    observed_at_utc: str | None = None,
) -> MarketJobObservation:
    """Project connector evidence without granting ingestion or relevance authority."""
    raw = record.raw_data if isinstance(record.raw_data, Mapping) else {}
    job = raw.get("job")
    card = raw.get("result_card")
    title = company = location = description = ""
    remote_signal = False

    if record.source_name == "bundesagentur_fuer_arbeit" and isinstance(job, Mapping):
        title = _clean(job.get("titel") or job.get("stellenangebotsTitel"))
        company = _clean(job.get("arbeitgeber") or job.get("firma"))
        location = _ba_location(job.get("arbeitsort") or job.get("stellenlokationen"))
        description = _clean(
            job.get("stellenbeschreibung") or job.get("beschreibung") or job.get("description")
        )
        remote_signal = any(
            token in _clean(job).casefold()
            for token in ("remote", "homeoffice", "home office", "mobiles arbeiten")
        )
    elif isinstance(card, Mapping):
        title = _clean(card.get("title"))
        company = _clean(card.get("company_name"))
        location = _clean(card.get("location"))
        description = _clean(card.get("raw_card_text"))
        remote_signal = bool(_clean(card.get("remote_hint_text")))
    elif isinstance(job, Mapping):
        title = _clean(job.get("title") or job.get("titel"))
        company = _clean(
            job.get("company_name") or job.get("arbeitgeber") or job.get("company")
        )
        raw_location = job.get("location") or job.get("arbeitsort")
        if isinstance(raw_location, Mapping):
            raw_location = raw_location.get("name") or raw_location.get("city")
        location = _clean(raw_location)
        description = _clean(
            job.get("description") or job.get("beschreibung") or job.get("content")
        )
        remote_signal = any(
            token in f"{location} {description}".casefold()
            for token in ("remote", "homeoffice", "home office", "mobiles arbeiten")
        )

    extraction = raw.get("extraction")
    observed = observed_at_utc
    if observed is None and isinstance(extraction, Mapping):
        observed = _clean(extraction.get("observed_at_utc")) or None
    if observed is None:
        observed = datetime.now(UTC).isoformat()

    reference = _clean(record.external_job_id) or _clean(record.source_url)
    return MarketJobObservation(
        source=record.source_name,
        title=title,
        company_name=company or None,
        location=location or None,
        observed_at_utc=observed,
        reference=reference,
        description=description,
        remote_signal=remote_signal,
    )
