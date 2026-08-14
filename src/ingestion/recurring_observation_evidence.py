"""Stable per-sighting evidence hashing for recurring connector observations.

The hash is deliberately narrower than the full connector ``raw_data`` payload.
Connector payloads may contain search/run context such as search terms or
``observed_at_utc`` which changes every execution without changing the job. Those
fields must not cause paid recurring semantic work.

Conversely, the exact current ``source_url`` plus source-provided job/structural
evidence is retained so a real route or content change invalidates the cache.
This module only projects and hashes evidence; it owns no booster eligibility or
product authority.
"""

from __future__ import annotations

from typing import Any

from src.connectors.base import RawJobRecord
from src.search_intelligence.recurring_connector_economics import normalized_evidence_hash


RECURRING_OBSERVATION_EVIDENCE_CONTRACT_VERSION = "recurring-observation-evidence.v1"

# These top-level containers are execution/query metadata or deterministic
# derivatives, not source-local job evidence. Keeping them in the hash would make
# the same job appear changed merely because another term/profile saw it or a new
# run timestamp was generated.
NON_EVIDENCE_TOP_LEVEL_KEYS = frozenset(
    {
        "search_profile",
        "search_context",
        "extraction",
        "matching",
        "quality_signals",
        "acquisition_evidence",
    }
)


def recurring_observation_evidence(record: RawJobRecord) -> dict[str, Any]:
    """Project durable current evidence from one normalized connector record."""

    raw_evidence = {
        key: value
        for key, value in record.raw_data.items()
        if key not in NON_EVIDENCE_TOP_LEVEL_KEYS
    }
    return {
        "source_url": record.source_url.strip(),
        "raw_evidence": raw_evidence,
    }


def recurring_observation_evidence_hash(record: RawJobRecord) -> str:
    """Hash one current sighting under the explicit v1 projection contract."""

    return normalized_evidence_hash(recurring_observation_evidence(record))
