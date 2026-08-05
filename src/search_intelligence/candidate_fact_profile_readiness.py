from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Final, Mapping, Sequence

from src.search_intelligence.candidate_fact_profile import (
    CAPABILITY_EVIDENCE_CLASSES,
    PROFILE_KEY,
    SCHEMA_VERSION,
    SOURCE_TYPE,
    CandidateFactProfile,
    parse_candidate_fact_profile,
)


AUDIT_KEY: Final = "CANDIDATE-FACT-PROFILE-READINESS-001"
REPORT_SCHEMA: Final = "candidate_fact_profile_readiness.v1"

_ALLOWED_PROFILE_STATES = frozenset({"draft", "approved", "superseded"})


@dataclass(frozen=True)
class CandidateFactProfileReadiness:
    audit_key: str
    profile_state: str
    profile_version: str | None
    payload_sha256: str | None
    payload_valid: bool
    payload_hash_matches: bool
    normalized_rows_match: bool
    approval_metadata_present: bool
    revision_count: int
    fact_count: int
    approved_fact_count: int
    capability_evidence_fact_count: int
    production_evidence_fact_count: int
    distinct_capability_tag_count: int
    category_counts: dict[str, int]
    evidence_class_counts: dict[str, int]
    approval_status_counts: dict[str, int]
    comparison_input_ready: bool
    blockers: tuple[str, ...]

    def canonical_payload(self) -> dict[str, Any]:
        return asdict(self)


def absent_candidate_fact_profile_readiness() -> CandidateFactProfileReadiness:
    return CandidateFactProfileReadiness(
        audit_key=AUDIT_KEY,
        profile_state="absent",
        profile_version=None,
        payload_sha256=None,
        payload_valid=False,
        payload_hash_matches=False,
        normalized_rows_match=False,
        approval_metadata_present=False,
        revision_count=0,
        fact_count=0,
        approved_fact_count=0,
        capability_evidence_fact_count=0,
        production_evidence_fact_count=0,
        distinct_capability_tag_count=0,
        category_counts={},
        evidence_class_counts={},
        approval_status_counts={},
        comparison_input_ready=False,
        blockers=("approved_profile_missing",),
    )


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _canonical_fact_payloads(profile: CandidateFactProfile) -> dict[str, dict[str, Any]]:
    return {fact.fact_key: fact.canonical_payload() for fact in profile.facts}


def _persisted_fact_payloads(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]] | None:
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        fact_key = row.get("fact_key")
        fact_payload = _mapping(row.get("fact_payload"))
        if not isinstance(fact_key, str) or not fact_key or fact_payload is None:
            return None
        if fact_key in result:
            return None
        result[fact_key] = fact_payload
    return result


def _counts(profile: CandidateFactProfile) -> tuple[
    int,
    int,
    int,
    int,
    int,
    dict[str, int],
    dict[str, int],
    dict[str, int],
]:
    approved = profile.approved_facts
    capability = profile.capability_evidence_facts
    production = profile.production_evidence_facts
    capability_tags = {
        tag
        for fact in capability
        for tag in fact.capability_tags
    }
    category_counts = Counter(fact.category for fact in profile.facts)
    evidence_counts = Counter(fact.evidence_class for fact in profile.facts)
    approval_counts = Counter(fact.approval_status for fact in profile.facts)
    return (
        len(profile.facts),
        len(approved),
        len(capability),
        len(production),
        len(capability_tags),
        dict(sorted(category_counts.items())),
        dict(sorted(evidence_counts.items())),
        dict(sorted(approval_counts.items())),
    )


def evaluate_candidate_fact_profile_readiness(
    *,
    profile_row: Mapping[str, Any] | None,
    fact_rows: Sequence[Mapping[str, Any]],
    revision_count: int,
) -> CandidateFactProfileReadiness:
    if profile_row is None:
        return absent_candidate_fact_profile_readiness()

    blockers: list[str] = []
    row_status = profile_row.get("status")
    profile_state = (
        row_status
        if isinstance(row_status, str) and row_status in _ALLOWED_PROFILE_STATES
        else "invalid"
    )
    if profile_state != "approved":
        blockers.append("profile_not_approved")

    if profile_row.get("profile_key") != PROFILE_KEY:
        blockers.append("profile_key_invalid")
    if profile_row.get("schema_version") != SCHEMA_VERSION:
        blockers.append("schema_version_invalid")
    if profile_row.get("source_type") != SOURCE_TYPE:
        blockers.append("source_type_invalid")

    payload = _mapping(profile_row.get("payload"))
    profile: CandidateFactProfile | None = None
    payload_valid = False
    if payload is None:
        blockers.append("profile_payload_invalid")
    else:
        try:
            profile = parse_candidate_fact_profile(payload)
            payload_valid = True
        except ValueError:
            blockers.append("profile_payload_invalid")

    row_payload_sha = profile_row.get("payload_sha256")
    payload_sha256 = row_payload_sha if isinstance(row_payload_sha, str) else None
    payload_hash_matches = bool(
        profile is not None
        and payload_sha256 is not None
        and profile.payload_sha256 == payload_sha256
    )
    if not payload_hash_matches:
        blockers.append("payload_hash_mismatch")

    approval_metadata_present = bool(
        profile_state == "approved"
        and profile_row.get("approved_by")
        and profile_row.get("approved_at")
        and profile is not None
        and profile.approved_by == profile_row.get("approved_by")
        and profile.approved_at is not None
    )
    if profile_state == "approved" and not approval_metadata_present:
        blockers.append("approval_metadata_missing_or_mismatched")

    persisted_payloads = _persisted_fact_payloads(fact_rows)
    normalized_rows_match = bool(
        profile is not None
        and persisted_payloads is not None
        and _canonical_fact_payloads(profile) == persisted_payloads
    )
    if not normalized_rows_match:
        blockers.append("normalized_fact_rows_mismatch")

    if revision_count < 0:
        blockers.append("revision_count_invalid")
    elif profile_state == "approved" and revision_count == 0:
        blockers.append("revision_history_missing")

    if profile is None:
        fact_count = len(fact_rows)
        approved_fact_count = 0
        capability_evidence_fact_count = 0
        production_evidence_fact_count = 0
        distinct_capability_tag_count = 0
        category_counts: dict[str, int] = {}
        evidence_class_counts: dict[str, int] = {}
        approval_status_counts: dict[str, int] = {}
        profile_version = (
            profile_row.get("profile_version")
            if isinstance(profile_row.get("profile_version"), str)
            else None
        )
    else:
        (
            fact_count,
            approved_fact_count,
            capability_evidence_fact_count,
            production_evidence_fact_count,
            distinct_capability_tag_count,
            category_counts,
            evidence_class_counts,
            approval_status_counts,
        ) = _counts(profile)
        profile_version = profile.profile_version

        approved_capability_rows = [
            fact
            for fact in profile.facts
            if fact.is_approved and fact.evidence_class in CAPABILITY_EVIDENCE_CLASSES
        ]
        if not approved_capability_rows:
            blockers.append("approved_capability_evidence_missing")
        if not any(fact.capability_tags for fact in approved_capability_rows):
            blockers.append("capability_tags_missing")

    blockers = sorted(set(blockers))
    return CandidateFactProfileReadiness(
        audit_key=AUDIT_KEY,
        profile_state=profile_state,
        profile_version=profile_version,
        payload_sha256=payload_sha256,
        payload_valid=payload_valid,
        payload_hash_matches=payload_hash_matches,
        normalized_rows_match=normalized_rows_match,
        approval_metadata_present=approval_metadata_present,
        revision_count=max(revision_count, 0),
        fact_count=fact_count,
        approved_fact_count=approved_fact_count,
        capability_evidence_fact_count=capability_evidence_fact_count,
        production_evidence_fact_count=production_evidence_fact_count,
        distinct_capability_tag_count=distinct_capability_tag_count,
        category_counts=category_counts,
        evidence_class_counts=evidence_class_counts,
        approval_status_counts=approval_status_counts,
        comparison_input_ready=not blockers,
        blockers=tuple(blockers),
    )
