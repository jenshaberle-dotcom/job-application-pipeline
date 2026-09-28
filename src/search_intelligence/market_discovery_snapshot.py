"""Verified read-only market-discovery evidence for the JAP Classic Sources UI.

This module deliberately carries only minimised, already-qualified output from the
latest accepted full-raster comparison flight. It is presentation evidence, not
Product job authority: no raw aggregator URL, listing body, candidate creation,
connector activation, Bronze/Silver write, ranking or Top-5 authority is present.

Refresh this snapshot only from a successful bounded Census comparison flight.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

LATEST_VERIFIED_DISCOVERY_RUN = {
    "run_id": "36398829769",
    "source_sha": "1ed77d39b0ed8827ae6a06efed20513beae72972",
    "observed_at_utc": "2026-09-28T08:41:15.408460+00:00",
    "provider": "tavily",
    "provider_authority": "explicit_operator_selected_external_index_transport",
    "search_term_count": 22,
    "location_signals": ("Hannover", "Deutschland remote"),
    "candidate_baseline_count": 67,
    "boundary": {
        "read_only_discovery_evidence": True,
        "direct_board_requests": 0,
        "database_writes": 0,
        "bronze_writes": 0,
        "silver_writes": 0,
        "product_writes": 0,
        "candidate_creation": 0,
        "connector_activation": 0,
    },
}

_SOURCE_DISCOVERY_EVIDENCE: dict[str, dict[str, Any]] = {
    "bundesagentur_fuer_arbeit": {
        "mode": "registered_connector",
        "query_count": 19,
        "observed_jobs": 811,
        "qualifying_jobs": 306,
        "unique_qualifying_employers": 213,
        "incremental_novel_employers": None,
        "leads": (),
    },
    "stepstone": {
        "mode": "registered_connector",
        "query_count": 17,
        "observed_jobs": 425,
        "qualifying_jobs": 67,
        "unique_qualifying_employers": 43,
        "incremental_novel_employers": None,
        "leads": (),
    },
    "goodjobs": {
        "mode": "external_index_only",
        "query_count": 44,
        "observed_jobs": 5,
        "qualifying_jobs": 1,
        "unique_qualifying_employers": 1,
        "incremental_novel_employers": 1,
        "leads": (
            {
                "company_key": "encavis",
                "company_name": "Encavis GmbH",
                "matching_job_count": 1,
                "matching_roles": ("Data Engineer",),
                "origin_status": "novel",
                "verification_status": "employer_origin_verification_pending",
                "location_confidence": "uncertain",
                "location_summary": "Remote hint found; employer-origin confirmation still required.",
            },
        ),
    },
    "xing": {
        "mode": "external_index_only",
        "query_count": 44,
        "observed_jobs": 0,
        "qualifying_jobs": 0,
        "unique_qualifying_employers": 0,
        "incremental_novel_employers": 0,
        "leads": (),
    },
    "meinestadt": {
        "mode": "external_index_only",
        "query_count": 44,
        "observed_jobs": 0,
        "qualifying_jobs": 0,
        "unique_qualifying_employers": 0,
        "incremental_novel_employers": 0,
        "leads": (),
    },
    "get_in_it": {
        "mode": "external_index_only",
        "query_count": 44,
        "observed_jobs": 0,
        "qualifying_jobs": 0,
        "unique_qualifying_employers": 0,
        "incremental_novel_employers": 0,
        "leads": (),
    },
    "jobvector": {
        "mode": "external_index_only",
        "query_count": 44,
        "observed_jobs": 0,
        "qualifying_jobs": 0,
        "unique_qualifying_employers": 0,
        "incremental_novel_employers": 0,
        "leads": (),
    },
}


def discovery_evidence_for_source(source_name: str) -> dict[str, Any] | None:
    """Return an isolated UI projection of the latest verified sensor evidence."""
    evidence = _SOURCE_DISCOVERY_EVIDENCE.get(source_name)
    if evidence is None:
        return None
    result = deepcopy(evidence)
    result.update(
        {
            "run_id": LATEST_VERIFIED_DISCOVERY_RUN["run_id"],
            "source_sha": LATEST_VERIFIED_DISCOVERY_RUN["source_sha"],
            "observed_at_utc": LATEST_VERIFIED_DISCOVERY_RUN["observed_at_utc"],
            "search_term_count": LATEST_VERIFIED_DISCOVERY_RUN["search_term_count"],
            "location_signals": list(LATEST_VERIFIED_DISCOVERY_RUN["location_signals"]),
            "boundary": deepcopy(LATEST_VERIFIED_DISCOVERY_RUN["boundary"]),
        }
    )
    result["leads"] = [dict(item) for item in result.get("leads", ())]
    for lead in result["leads"]:
        lead["matching_roles"] = list(lead.get("matching_roles", ()))
    return result
