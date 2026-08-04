"""Pure architecture contract for browser-protected employer origins.

This module deliberately performs no network access and installs no runtime hook.
It separates two independent facts:

* origin truth: the exact URL is an official, reusable employer career origin;
* collection readiness: an approved collector can fetch that URL without
  bypassing access controls.

A browser or operator evidence record may establish origin truth. A requests
probe may establish collection readiness. HTTP 403, challenge pages, and short
brand hosts never establish origin truth by themselves.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Literal

from src.search_intelligence.origin_source_discovery_agent import normalize_candidate_url

ORIGIN_EVIDENCE_SOURCES = frozenset({"browser_observation", "operator_attestation"})
CAREER_SIGNALS = frozenset(
    {
        "career",
        "careers",
        "job",
        "jobs",
        "karriere",
        "recruiting",
        "stellen",
        "stellenangebote",
        "vacancies",
    }
)
PROHIBITED_AUTOMATION_TECHNIQUES = frozenset(
    {
        "captcha_solver",
        "challenge_token_reuse",
        "cookie_import",
        "fingerprint_spoofing",
        "proxy_rotation",
        "rate_limit_evasion",
        "session_hijack",
        "stealth_plugin",
        "webdriver_evasion",
    }
)

OriginEvidenceSource = Literal["browser_observation", "operator_attestation"]
OriginTruthState = Literal["unverified", "verified"]
CollectionState = Literal[
    "unknown",
    "ready",
    "blocked_by_access_control",
    "blocked_unreachable",
]
ArchitectureDecision = Literal[
    "operator_review_required",
    "origin_verified_collection_unknown",
    "origin_verified_collection_ready",
    "origin_verified_collection_blocked",
]


@dataclass(frozen=True)
class OriginTruthEvidence:
    """Immutable evidence for an exact employer-origin relationship."""

    schema_version: str
    evidence_id: str
    company_key: str
    normalized_url: str
    evidence_source: OriginEvidenceSource
    observed_at: str
    expires_at: str
    verifier_identity: str
    verifier_version: str
    requested_url: str
    final_url: str
    canonical_url: str | None
    page_title: str
    observed_entity_tokens: tuple[str, ...]
    observed_career_signals: tuple[str, ...]
    content_sha256: str
    screenshot_sha256: str | None = None
    operator_approval_token: str | None = None
    challenge_encountered: bool = False
    automation_interacted_with_challenge: bool = False
    automation_techniques: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["observed_entity_tokens"] = list(self.observed_entity_tokens)
        payload["observed_career_signals"] = list(self.observed_career_signals)
        payload["automation_techniques"] = list(self.automation_techniques)
        return payload


@dataclass(frozen=True)
class CollectorCapabilityEvidence:
    """Immutable evidence for non-browser collection feasibility."""

    schema_version: str
    evidence_id: str
    normalized_url: str
    observed_at: str
    expires_at: str
    collector_identity: str
    collector_version: str
    requested_url: str
    final_url: str | None
    status_code: int | None
    reachable: bool
    challenge_detected: bool
    failure_class: str | None
    side_effect_free: bool
    provider_requests: int
    pipeline_mutation: bool

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class BrowserProtectedOriginDecision:
    """Deterministic replay result for split origin and collector truth."""

    company_key: str
    normalized_url: str
    decision: ArchitectureDecision
    origin_truth_state: OriginTruthState
    collection_state: CollectionState
    verification_basis: str | None
    verified_url: str | None
    collection_feasibility_proven: bool
    source_activation_allowed: bool
    operator_review_required: bool
    provider_requests: int
    pipeline_mutation: bool
    evidence_ids: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["evidence_ids"] = list(self.evidence_ids)
        payload["reasons"] = list(self.reasons)
        return payload


def _parse_timestamp(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _is_fresh(*, observed_at: str, expires_at: str, now: str) -> bool:
    observed = _parse_timestamp(observed_at)
    expires = _parse_timestamp(expires_at)
    current = _parse_timestamp(now)
    return bool(
        observed is not None
        and expires is not None
        and current is not None
        and observed <= current < expires
    )


def _is_sha256(value: str | None) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "").strip().lower()))


def _compact_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _exact_url_match(value: str | None, expected: str) -> bool:
    normalized = normalize_candidate_url(value)
    return normalized is not None and normalized == expected


def _origin_evidence_reasons(
    evidence: OriginTruthEvidence,
    *,
    company_key: str,
    expected_url: str,
    required_entity_tokens: tuple[str, ...],
    now: str,
) -> tuple[str, ...]:
    reasons: list[str] = []

    if evidence.schema_version != "1.0":
        reasons.append("unsupported origin evidence schema")
    if evidence.company_key != company_key:
        reasons.append("origin evidence company key mismatch")
    if evidence.evidence_source not in ORIGIN_EVIDENCE_SOURCES:
        reasons.append("unsupported origin evidence source")
    if not _is_fresh(
        observed_at=evidence.observed_at,
        expires_at=evidence.expires_at,
        now=now,
    ):
        reasons.append("origin evidence is expired, future-dated, or time-invalid")

    for label, url in (
        ("registered", evidence.normalized_url),
        ("requested", evidence.requested_url),
        ("final", evidence.final_url),
    ):
        if not _exact_url_match(url, expected_url):
            reasons.append(f"{label} origin URL does not exactly match operator URL")
    if evidence.canonical_url is not None and not _exact_url_match(
        evidence.canonical_url,
        expected_url,
    ):
        reasons.append("canonical origin URL does not exactly match operator URL")

    if not evidence.verifier_identity.strip() or not evidence.verifier_version.strip():
        reasons.append("origin evidence provenance is incomplete")
    if not evidence.page_title.strip():
        reasons.append("origin evidence page title is missing")
    if not _is_sha256(evidence.content_sha256):
        reasons.append("origin evidence content digest is invalid")
    if evidence.screenshot_sha256 is not None and not _is_sha256(
        evidence.screenshot_sha256
    ):
        reasons.append("origin evidence screenshot digest is invalid")

    required = {
        _compact_token(token)
        for token in required_entity_tokens
        if _compact_token(token)
    }
    observed = {
        _compact_token(token)
        for token in evidence.observed_entity_tokens
        if _compact_token(token)
    }
    if not required:
        reasons.append("no distinctive employer entity tokens were required")
    elif not required.issubset(observed):
        reasons.append("origin evidence lacks the full distinctive employer entity")

    career_signals = {
        _compact_token(signal)
        for signal in evidence.observed_career_signals
        if _compact_token(signal)
    }
    normalized_career_signals = {_compact_token(item) for item in CAREER_SIGNALS}
    if not career_signals.intersection(normalized_career_signals):
        reasons.append("origin evidence lacks a career or job signal")

    techniques = {
        str(item or "").strip().lower() for item in evidence.automation_techniques
    }
    prohibited = sorted(techniques.intersection(PROHIBITED_AUTOMATION_TECHNIQUES))
    if prohibited:
        reasons.append(
            "origin evidence used prohibited automation techniques: "
            + ", ".join(prohibited)
        )
    if evidence.automation_interacted_with_challenge:
        reasons.append("automation interacted with an access-control challenge")
    if evidence.challenge_encountered:
        reasons.append(
            "browser verifier encountered a challenge and must stop without "
            "establishing origin truth"
        )

    if (
        evidence.evidence_source == "operator_attestation"
        and not str(evidence.operator_approval_token or "").strip()
    ):
        reasons.append("operator attestation lacks an approval token")

    return tuple(dict.fromkeys(reasons))


def _collector_state(
    evidence: CollectorCapabilityEvidence | None,
    *,
    expected_url: str,
    now: str,
) -> tuple[CollectionState, tuple[str, ...], tuple[str, ...]]:
    if evidence is None:
        return "unknown", ("no collector capability evidence supplied",), ()

    evidence_ids = (evidence.evidence_id,)
    reasons: list[str] = []
    if evidence.schema_version != "1.0":
        reasons.append("unsupported collector evidence schema")
    if not _is_fresh(
        observed_at=evidence.observed_at,
        expires_at=evidence.expires_at,
        now=now,
    ):
        reasons.append("collector evidence is expired, future-dated, or time-invalid")
    for label, url in (
        ("registered", evidence.normalized_url),
        ("requested", evidence.requested_url),
    ):
        if not _exact_url_match(url, expected_url):
            reasons.append(f"{label} collector URL does not exactly match operator URL")
    if evidence.final_url is not None and not _exact_url_match(
        evidence.final_url,
        expected_url,
    ):
        reasons.append("final collector URL does not exactly match operator URL")
    if not evidence.collector_identity.strip() or not evidence.collector_version.strip():
        reasons.append("collector evidence provenance is incomplete")
    if not evidence.side_effect_free:
        reasons.append("collector evidence was not side-effect free")
    if evidence.provider_requests != 0:
        reasons.append("collector evidence used provider requests")
    if evidence.pipeline_mutation:
        reasons.append("collector evidence mutated pipeline state")

    if reasons:
        return "unknown", tuple(dict.fromkeys(reasons)), evidence_ids

    if (
        evidence.reachable
        and evidence.status_code is not None
        and 200 <= evidence.status_code < 400
    ):
        return "ready", ("approved collector reached the exact origin URL",), evidence_ids

    if evidence.challenge_detected or evidence.status_code in {401, 403, 429}:
        return (
            "blocked_by_access_control",
            (
                "approved collector remains blocked by access control; "
                "no bypass is authorized",
            ),
            evidence_ids,
        )
    return (
        "blocked_unreachable",
        ("approved collector could not reach the exact origin URL",),
        evidence_ids,
    )


def evaluate_browser_protected_origin(
    *,
    company_key: str,
    operator_url: str,
    required_entity_tokens: tuple[str, ...],
    origin_evidence: OriginTruthEvidence | None,
    collector_evidence: CollectorCapabilityEvidence | None,
    now: str,
) -> BrowserProtectedOriginDecision:
    """Replay architecture evidence without network access or side effects."""

    normalized_url = normalize_candidate_url(operator_url)
    if normalized_url is None:
        return BrowserProtectedOriginDecision(
            company_key=company_key,
            normalized_url="",
            decision="operator_review_required",
            origin_truth_state="unverified",
            collection_state="unknown",
            verification_basis=None,
            verified_url=None,
            collection_feasibility_proven=False,
            source_activation_allowed=False,
            operator_review_required=True,
            provider_requests=0,
            pipeline_mutation=False,
            evidence_ids=(),
            reasons=("operator URL is invalid",),
        )

    if origin_evidence is None:
        origin_reasons = ("no origin-truth evidence supplied",)
        origin_verified = False
        origin_evidence_ids: tuple[str, ...] = ()
        verification_basis = None
    else:
        origin_reasons = _origin_evidence_reasons(
            origin_evidence,
            company_key=company_key,
            expected_url=normalized_url,
            required_entity_tokens=required_entity_tokens,
            now=now,
        )
        origin_verified = not origin_reasons
        origin_evidence_ids = (origin_evidence.evidence_id,)
        verification_basis = (
            origin_evidence.evidence_source if origin_verified else None
        )

    collection_state, collection_reasons, collector_evidence_ids = _collector_state(
        collector_evidence,
        expected_url=normalized_url,
        now=now,
    )
    evidence_ids = tuple(dict.fromkeys((*origin_evidence_ids, *collector_evidence_ids)))

    if not origin_verified:
        return BrowserProtectedOriginDecision(
            company_key=company_key,
            normalized_url=normalized_url,
            decision="operator_review_required",
            origin_truth_state="unverified",
            collection_state=collection_state,
            verification_basis=None,
            verified_url=None,
            collection_feasibility_proven=collection_state == "ready",
            source_activation_allowed=False,
            operator_review_required=True,
            provider_requests=0,
            pipeline_mutation=False,
            evidence_ids=evidence_ids,
            reasons=tuple((*origin_reasons, *collection_reasons)),
        )

    if collection_state == "ready":
        decision: ArchitectureDecision = "origin_verified_collection_ready"
    elif collection_state in {"blocked_by_access_control", "blocked_unreachable"}:
        decision = "origin_verified_collection_blocked"
    else:
        decision = "origin_verified_collection_unknown"

    return BrowserProtectedOriginDecision(
        company_key=company_key,
        normalized_url=normalized_url,
        decision=decision,
        origin_truth_state="verified",
        collection_state=collection_state,
        verification_basis=verification_basis,
        verified_url=normalized_url,
        collection_feasibility_proven=collection_state == "ready",
        source_activation_allowed=False,
        operator_review_required=False,
        provider_requests=0,
        pipeline_mutation=False,
        evidence_ids=evidence_ids,
        reasons=tuple((*origin_reasons, *collection_reasons)),
    )


__all__ = [
    "ArchitectureDecision",
    "BrowserProtectedOriginDecision",
    "CAREER_SIGNALS",
    "CollectionState",
    "CollectorCapabilityEvidence",
    "ORIGIN_EVIDENCE_SOURCES",
    "OriginTruthEvidence",
    "PROHIBITED_AUTOMATION_TECHNIQUES",
    "evaluate_browser_protected_origin",
]
