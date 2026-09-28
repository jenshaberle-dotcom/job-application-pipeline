from __future__ import annotations

from typing import Any

from src.search_intelligence.company_vocabulary import extract_vocabulary_terms


MARKET_SENSOR_EVIDENCE_SOURCE = "market_sensor_ingestion"
MARKET_SENSOR_EVIDENCE_KIND = "market_sensor_company_sighting"


def build_market_sensor_evidence_payload(
    *,
    source_name: str,
    company_name: str,
    display_title: str | None,
    search_profile_name: str | None,
    search_term: str | None,
    ingestion_run_id: int | None,
) -> dict[str, Any]:
    """Build the canonical persistence payload for one market-sensor observation.

    All market sensors cross the persistence boundary in the same minimized form:
    company identity plus derived vocabulary and search lineage. Sensor URLs, raw
    external job identifiers and Product/Bronze/Silver authority never cross.
    """

    normalized_title = " ".join(str(display_title or "").split()).strip()
    vocabulary_terms = (
        extract_vocabulary_terms(normalized_title) if normalized_title else ()
    )

    return {
        "evidence_source": MARKET_SENSOR_EVIDENCE_SOURCE,
        "evidence_kind": MARKET_SENSOR_EVIDENCE_KIND,
        "source_name": source_name,
        "company_name": company_name,
        "title": " ".join(vocabulary_terms),
        "evidence_url": None,
        "search_profile_name": search_profile_name,
        "search_term": search_term,
        "ingestion_run_id": ingestion_run_id,
        "raw_job_external_id": None,
        "evidence": {
            "boundary": {
                "company_identity_only": True,
                "vocabulary_only": True,
                "sensor_url_forwarded": False,
                "raw_job_identity_forwarded": False,
                "bronze_write": False,
                "silver_write": False,
                "product_write": False,
                "candidate_creation": False,
                "source_activation": False,
                "scheduler_change": False,
            },
            "vocabulary_terms": list(vocabulary_terms),
        },
    }
