"""Deterministic ATS authority-attempt and gap observations for LLM-BOOST-001.

This module turns an already executed provider-specific authority validation
attempt into a stable, replay-safe observation. It performs no network,
provider, database, connector activation, or product mutation.

Search/model output can never grant tenant authority here. An exhausted
deterministic attempt may only establish an external evidence gap and make the
shared search-first booster eligible to look for alternate evidence which must
subsequently pass deterministic validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import StrEnum
import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse

from src.search_intelligence.ats_delegation_evidence import ATSDelegationEvidence
from src.search_intelligence.llm_booster_policy import (
    BoosterPlan,
    BoosterStage,
    BoosterSurface,
    TavilyState,
    build_booster_plan,
)

ATS_AUTHORITY_GAP_CONTRACT_VERSION = "LLM-BOOST-001.ats-authority-gap.v1"

_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "msclkid",
    "ref",
    "referrer",
    "source",
}


class ATSAuthorityAttemptOutcome(StrEnum):
    """Fail-closed result of one deterministic authority evidence attempt."""

    HTTP_RATE_LIMITED = "http_rate_limited"
    HTTP_UNAVAILABLE = "http_unavailable"
    ACCESS_BLOCKED = "access_blocked"
    TRANSPORT_FAILURE = "transport_failure"
    REDIRECTED_AWAY = "redirected_away"
    EMPTY_EVIDENCE = "empty_evidence"
    INVALID_EVIDENCE = "invalid_evidence"
    EMPLOYER_MISMATCH = "employer_mismatch"


@dataclass(frozen=True)
class ATSAuthorityAttemptObservation:
    contract_version: str
    provider: str
    employer_identity: str
    target_url: str
    evidence_url: str
    validation_contract: str
    outcome: ATSAuthorityAttemptOutcome
    request_fingerprint: str
    http_status: int | None = None
    final_url: str | None = None
    tenant_authority: bool = False
    delegation_permitted: bool = False
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["outcome"] = self.outcome.value
        return payload


@dataclass(frozen=True)
class ATSAuthorityGapDecision:
    contract_version: str
    classification: str
    external_information_gap: bool
    semantic_booster_eligible: bool
    deterministic_request_replay_blocked: bool
    unchanged_gap_skip: bool
    next_action: str
    evidence_fingerprint: str
    booster_plan: BoosterPlan
    tenant_authority: bool = False
    delegation_permitted: bool = False
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "classification": self.classification,
            "external_information_gap": self.external_information_gap,
            "semantic_booster_eligible": self.semantic_booster_eligible,
            "deterministic_request_replay_blocked": self.deterministic_request_replay_blocked,
            "unchanged_gap_skip": self.unchanged_gap_skip,
            "next_action": self.next_action,
            "evidence_fingerprint": self.evidence_fingerprint,
            "booster_plan": self.booster_plan.to_json(),
            "tenant_authority": self.tenant_authority,
            "delegation_permitted": self.delegation_permitted,
            "product_authority": self.product_authority,
        }


def _normalize_identity(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalize_request_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("ATS authority request URL must be non-empty")
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().strip(".")
    if parsed.scheme.lower() not in {"http", "https"} or not host:
        raise ValueError("ATS authority request URL must be absolute HTTP(S)")
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query_pairs = []
    for key, item in parse_qsl(parsed.query or "", keep_blank_values=True):
        normalized_key = key.strip().lower()
        if normalized_key.startswith("utm_") or normalized_key in _TRACKING_QUERY_KEYS:
            continue
        query_pairs.append((key, item))
    return parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=host,
        path=path,
        params="",
        query=urlencode(sorted(query_pairs)),
        fragment="",
    ).geturl()


def _gate_external_stages(plan: BoosterPlan, *, reason_code: str) -> BoosterPlan:
    """Project a shared plan into a deterministic-only ATS decision.

    The shared planner deliberately keeps model fallback eligible when Tavily is
    unavailable. ATS adds a stricter station gate: before provider-specific
    authority validation is actually exhausted, *no* semantic stage may run.
    This function changes eligibility only; it does not duplicate stage order,
    model configuration, budget, or cost policy.
    """

    return replace(
        plan,
        stages=tuple(
            stage
            if stage.stage == BoosterStage.DETERMINISTIC
            else replace(stage, eligible=False, reason_code=reason_code)
            for stage in plan.stages
        ),
    )


def ats_authority_request_fingerprint(
    *,
    provider: str,
    employer_identity: str,
    target_url: str,
    evidence_url: str,
    validation_contract: str,
) -> str:
    """Stable identity of an exact deterministic authority evidence request."""

    parts = (
        _normalize_identity(provider),
        _normalize_identity(employer_identity),
        _normalize_request_url(target_url),
        _normalize_request_url(evidence_url),
        str(validation_contract or "").strip(),
    )
    if any(not part for part in parts):
        raise ValueError("ATS authority request fingerprint fields must be non-empty")
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def build_ats_authority_attempt_observation(
    *,
    provider: str,
    employer_identity: str,
    target_url: str,
    evidence_url: str,
    validation_contract: str,
    outcome: ATSAuthorityAttemptOutcome,
    http_status: int | None = None,
    final_url: str | None = None,
) -> ATSAuthorityAttemptObservation:
    """Record one completed fail-closed deterministic authority attempt."""

    return ATSAuthorityAttemptObservation(
        contract_version=ATS_AUTHORITY_GAP_CONTRACT_VERSION,
        provider=_normalize_identity(provider),
        employer_identity=_normalize_identity(employer_identity),
        target_url=_normalize_request_url(target_url),
        evidence_url=_normalize_request_url(evidence_url),
        validation_contract=str(validation_contract or "").strip(),
        outcome=outcome,
        request_fingerprint=ats_authority_request_fingerprint(
            provider=provider,
            employer_identity=employer_identity,
            target_url=target_url,
            evidence_url=evidence_url,
            validation_contract=validation_contract,
        ),
        http_status=http_status,
        final_url=(None if not final_url else _normalize_request_url(final_url)),
    )


def ats_authority_gap_fingerprint(
    *,
    delegation_evidence: ATSDelegationEvidence,
    attempt: ATSAuthorityAttemptObservation | None,
) -> str:
    """Stable semantic identity used to suppress unchanged booster spend."""

    parts = [
        ATS_AUTHORITY_GAP_CONTRACT_VERSION,
        delegation_evidence.evidence_fingerprint,
    ]
    if attempt is not None:
        parts.extend(
            (
                attempt.request_fingerprint,
                attempt.outcome.value,
                str(attempt.http_status or ""),
                attempt.final_url or "",
            )
        )
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _shared_plan(
    *,
    tavily_state: TavilyState,
    deterministic_resolved: bool,
    external_information_gap: bool,
) -> BoosterPlan:
    return build_booster_plan(
        surface=BoosterSurface.ATS_DELEGATION,
        tavily_state=tavily_state,
        deterministic_resolved=deterministic_resolved,
        external_information_gap=external_information_gap,
    )


def analyze_ats_authority_gap(
    *,
    delegation_evidence: ATSDelegationEvidence,
    tavily_state: TavilyState,
    authority_attempt: ATSAuthorityAttemptObservation | None = None,
    previous_gap_fingerprint: str | None = None,
) -> ATSAuthorityGapDecision:
    """Decide whether ATS may escalate beyond deterministic authority validation."""

    fingerprint = ats_authority_gap_fingerprint(
        delegation_evidence=delegation_evidence,
        attempt=authority_attempt,
    )

    if delegation_evidence.delegation_permitted:
        return ATSAuthorityGapDecision(
            contract_version=ATS_AUTHORITY_GAP_CONTRACT_VERSION,
            classification="ats_authority_resolved",
            external_information_gap=False,
            semantic_booster_eligible=False,
            deterministic_request_replay_blocked=False,
            unchanged_gap_skip=False,
            next_action="use_validated_ats_delegation_evidence",
            evidence_fingerprint=fingerprint,
            booster_plan=_shared_plan(
                tavily_state=tavily_state,
                deterministic_resolved=True,
                external_information_gap=False,
            ),
            tenant_authority=delegation_evidence.tenant_authority,
            delegation_permitted=True,
        )

    if delegation_evidence.classification == "ats_provider_conflict":
        plan = _gate_external_stages(
            _shared_plan(
                tavily_state=tavily_state,
                deterministic_resolved=False,
                external_information_gap=False,
            ),
            reason_code="ats_provider_conflict_deterministic_only",
        )
        return ATSAuthorityGapDecision(
            contract_version=ATS_AUTHORITY_GAP_CONTRACT_VERSION,
            classification="ats_provider_conflict_deterministic_only",
            external_information_gap=False,
            semantic_booster_eligible=False,
            deterministic_request_replay_blocked=False,
            unchanged_gap_skip=False,
            next_action="resolve_provider_conflict_deterministically",
            evidence_fingerprint=fingerprint,
            booster_plan=plan,
        )

    if delegation_evidence.provider is not None and authority_attempt is None:
        plan = _gate_external_stages(
            _shared_plan(
                tavily_state=tavily_state,
                deterministic_resolved=False,
                external_information_gap=False,
            ),
            reason_code="deterministic_authority_path_not_exhausted",
        )
        return ATSAuthorityGapDecision(
            contract_version=ATS_AUTHORITY_GAP_CONTRACT_VERSION,
            classification="ats_deterministic_authority_attempt_required",
            external_information_gap=False,
            semantic_booster_eligible=False,
            deterministic_request_replay_blocked=False,
            unchanged_gap_skip=False,
            next_action=delegation_evidence.next_action,
            evidence_fingerprint=fingerprint,
            booster_plan=plan,
        )

    if authority_attempt is not None:
        if delegation_evidence.provider != authority_attempt.provider:
            raise ValueError("ATS authority attempt provider must match delegation evidence")
        unchanged = bool(
            previous_gap_fingerprint and previous_gap_fingerprint == fingerprint
        )
        plan = _shared_plan(
            tavily_state=tavily_state,
            deterministic_resolved=False,
            external_information_gap=True,
        )
        if unchanged:
            plan = _gate_external_stages(
                plan,
                reason_code="unchanged_ats_authority_gap_fingerprint",
            )
        return ATSAuthorityGapDecision(
            contract_version=ATS_AUTHORITY_GAP_CONTRACT_VERSION,
            classification=(
                "ats_authority_gap_unchanged"
                if unchanged
                else "ats_authority_external_evidence_gap"
            ),
            external_information_gap=True,
            semantic_booster_eligible=not unchanged,
            deterministic_request_replay_blocked=True,
            unchanged_gap_skip=unchanged,
            next_action=(
                "await_changed_authority_evidence"
                if unchanged
                else "search_for_alternate_ats_authority_evidence"
            ),
            evidence_fingerprint=fingerprint,
            booster_plan=plan,
        )

    external_gap = bool(delegation_evidence.semantic_booster_eligible)
    plan = _shared_plan(
        tavily_state=tavily_state,
        deterministic_resolved=False,
        external_information_gap=external_gap,
    )
    if not external_gap:
        plan = _gate_external_stages(
            plan,
            reason_code="deterministic_ats_resolution_required",
        )
    return ATSAuthorityGapDecision(
        contract_version=ATS_AUTHORITY_GAP_CONTRACT_VERSION,
        classification="ats_provider_external_information_gap",
        external_information_gap=external_gap,
        semantic_booster_eligible=external_gap,
        deterministic_request_replay_blocked=False,
        unchanged_gap_skip=False,
        next_action=delegation_evidence.next_action,
        evidence_fingerprint=fingerprint,
        booster_plan=plan,
    )


__all__ = [
    "ATS_AUTHORITY_GAP_CONTRACT_VERSION",
    "ATSAuthorityAttemptObservation",
    "ATSAuthorityAttemptOutcome",
    "ATSAuthorityGapDecision",
    "analyze_ats_authority_gap",
    "ats_authority_gap_fingerprint",
    "ats_authority_request_fingerprint",
    "build_ats_authority_attempt_observation",
]
