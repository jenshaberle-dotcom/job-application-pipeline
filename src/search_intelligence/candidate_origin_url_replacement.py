"""Approval-gated replacement of a validated candidate origin URL."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, replace
import re
from typing import Iterable, Sequence
from urllib.parse import urlsplit, urlunsplit

from src.search_intelligence.connector_feasibility import (
    ConnectorFeasibilityItem,
    is_public_https_origin_url,
)

APPROVAL_TOKEN = "approve_candidate_origin_url_replacement"
TARGET_PATTERN = re.compile(r"^(?P<candidate_id>[1-9][0-9]*):(?P<company_key>[a-z0-9][a-z0-9_-]*)$")


@dataclass(frozen=True)
class ReplacementRequest:
    candidate_id: int
    company_key: str
    expected_previous_url: str
    proposed_url: str

    @property
    def target(self) -> str:
        return f"{self.candidate_id}:{self.company_key}"


@dataclass(frozen=True)
class CandidateOriginSnapshot:
    candidate_id: int
    company_key: str
    company_name: str
    status: str
    candidate_url: str | None
    source_name_candidate: str | None = None
    risk_level: str | None = None


@dataclass(frozen=True)
class ReplacementPlanItem:
    target: str
    candidate_id: int
    company_key: str
    company_name: str
    candidate_status: str
    current_url: str | None
    expected_previous_url: str
    proposed_url: str
    live_repair_candidate_url: str | None
    http_status: int | None
    reachable: bool
    feasibility_status: str
    feasibility_blocker_code: str | None
    url_quality_status: str
    url_quality_code: str | None
    decision: str
    status: str
    reason: str
    apply_allowed: bool
    applied: bool = False
    audit_review_id: int | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ReplacementSummary:
    candidate_count: int
    ready_count: int
    applied_count: int
    idempotent_count: int
    valid_stop_count: int
    decision_counts: dict[str, int]


def parse_target(value: str) -> tuple[int, str]:
    match = TARGET_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError(
            "Target must use exact candidate_id:company_key syntax; "
            f"received {value!r}."
        )
    return int(match.group("candidate_id")), match.group("company_key")


def canonical_https_url(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw or not is_public_https_origin_url(raw):
        return None
    parsed = urlsplit(raw)
    if parsed.username or parsed.password or parsed.fragment:
        return None
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    netloc = host
    if port and port != 443:
        netloc = f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return urlunsplit(("https", netloc, path, parsed.query, ""))


def same_url(left: str | None, right: str | None) -> bool:
    left_url = canonical_https_url(left)
    right_url = canonical_https_url(right)
    return bool(left_url and right_url and left_url == right_url)


def parse_repair_spec(value: str) -> ReplacementRequest:
    parts = value.split("|")
    if len(parts) != 3:
        raise ValueError(
            "Repair spec must use target|expected_previous_url|proposed_url syntax."
        )
    target, expected_previous_url, proposed_url = (part.strip() for part in parts)
    candidate_id, company_key = parse_target(target)
    if not canonical_https_url(expected_previous_url):
        raise ValueError(
            f"Expected previous URL is not a safe public HTTPS URL: {expected_previous_url!r}"
        )
    if not canonical_https_url(proposed_url):
        raise ValueError(
            f"Proposed URL is not a safe public HTTPS URL: {proposed_url!r}"
        )
    if same_url(expected_previous_url, proposed_url):
        raise ValueError("Expected previous URL and proposed URL must differ.")
    return ReplacementRequest(
        candidate_id=candidate_id,
        company_key=company_key,
        expected_previous_url=expected_previous_url,
        proposed_url=proposed_url,
    )


def validate_unique_requests(
    requests: Sequence[ReplacementRequest],
) -> tuple[ReplacementRequest, ...]:
    if not requests:
        raise ValueError("At least one repair request is required.")
    targets: set[str] = set()
    candidate_ids: set[int] = set()
    for request in requests:
        if request.target in targets:
            raise ValueError(f"Duplicate repair target: {request.target}")
        if request.candidate_id in candidate_ids:
            raise ValueError(
                "A candidate ID may appear only once per replacement transaction: "
                f"{request.candidate_id}"
            )
        targets.add(request.target)
        candidate_ids.add(request.candidate_id)
    return tuple(sorted(requests, key=lambda item: item.candidate_id))


def validate_apply_authority(
    requests: Sequence[ReplacementRequest],
    *,
    approval_token: str | None,
    approved_targets: Iterable[str],
) -> None:
    if approval_token != APPROVAL_TOKEN:
        raise ValueError("Exact candidate-origin replacement approval token is required.")
    parsed_approved = [
        f"{candidate_id}:{company_key}"
        for candidate_id, company_key in (
            parse_target(value) for value in approved_targets
        )
    ]
    if len(parsed_approved) != len(set(parsed_approved)):
        raise ValueError("Approved targets must not contain duplicates.")
    expected = {request.target for request in requests}
    approved = set(parsed_approved)
    if approved != expected:
        raise ValueError(
            "Approved target coverage must exactly match requested replacements: "
            f"expected={sorted(expected)} approved={sorted(approved)}"
        )


def _plan(
    *,
    request: ReplacementRequest,
    candidate: CandidateOriginSnapshot,
    item: ConnectorFeasibilityItem,
    decision: str,
    status: str,
    reason: str,
    apply_allowed: bool,
) -> ReplacementPlanItem:
    return ReplacementPlanItem(
        target=request.target,
        candidate_id=candidate.candidate_id,
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        candidate_status=candidate.status,
        current_url=candidate.candidate_url,
        expected_previous_url=request.expected_previous_url,
        proposed_url=request.proposed_url,
        live_repair_candidate_url=item.url_quality.repair_candidate_url,
        http_status=item.http_status,
        reachable=item.reachable,
        feasibility_status=item.feasibility_status,
        feasibility_blocker_code=item.blocker_code,
        url_quality_status=item.url_quality.status,
        url_quality_code=item.url_quality.code,
        decision=decision,
        status=status,
        reason=reason,
        apply_allowed=apply_allowed,
    )


def build_replacement_plan_item(
    request: ReplacementRequest,
    candidate: CandidateOriginSnapshot,
    item: ConnectorFeasibilityItem,
    *,
    duplicate_selected_url_exists: bool = False,
) -> ReplacementPlanItem:
    if (
        candidate.candidate_id != request.candidate_id
        or candidate.company_key != request.company_key
    ):
        return _plan(
            request=request,
            candidate=candidate,
            item=item,
            decision="target_identity_mismatch",
            status="valid_stop",
            reason="Current candidate identity does not match the exact requested target.",
            apply_allowed=False,
        )
    current_url = candidate.candidate_url
    if same_url(current_url, request.proposed_url):
        return _plan(
            request=request,
            candidate=candidate,
            item=item,
            decision="no_action_already_replaced",
            status="passed",
            reason="Candidate already stores the exact proposed replacement URL.",
            apply_allowed=False,
        )
    if candidate.status == "active_controlled":
        return _plan(
            request=request,
            candidate=candidate,
            item=item,
            decision="protected_active_controlled",
            status="valid_stop",
            reason="active_controlled candidates are protected from URL replacement.",
            apply_allowed=False,
        )
    if not canonical_https_url(current_url):
        return _plan(
            request=request,
            candidate=candidate,
            item=item,
            decision="initial_persistence_required",
            status="valid_stop",
            reason="Candidate has no safe populated URL; use the initial CAND-001 persistence gate.",
            apply_allowed=False,
        )
    if not same_url(current_url, request.expected_previous_url):
        return _plan(
            request=request,
            candidate=candidate,
            item=item,
            decision="previous_url_drift",
            status="valid_stop",
            reason="Current candidate URL no longer matches the exact expected previous URL.",
            apply_allowed=False,
        )
    if duplicate_selected_url_exists:
        return _plan(
            request=request,
            candidate=candidate,
            item=item,
            decision="duplicate_selected_url",
            status="valid_stop",
            reason="Another candidate for the same company already stores the proposed URL.",
            apply_allowed=False,
        )
    if item.blocker_code != "origin_url_repair_candidate_detected":
        return _plan(
            request=request,
            candidate=candidate,
            item=item,
            decision="live_repair_evidence_missing",
            status="valid_stop",
            reason=(
                "Fresh S7N evidence did not return the required "
                "origin_url_repair_candidate_detected outcome."
            ),
            apply_allowed=False,
        )
    live_repair_url = item.url_quality.repair_candidate_url
    if not same_url(live_repair_url, request.proposed_url):
        return _plan(
            request=request,
            candidate=candidate,
            item=item,
            decision="live_repair_candidate_mismatch",
            status="valid_stop",
            reason=(
                "Fresh S7N repair candidate does not exactly match the proposed "
                "replacement URL."
            ),
            apply_allowed=False,
        )
    return _plan(
        request=request,
        candidate=candidate,
        item=item,
        decision="replace_validated_candidate_url",
        status="operator_decision_required",
        reason=(
            "Fresh bounded S7N evidence confirms the exact proposed URL as the "
            "repair candidate for the exact current URL."
        ),
        apply_allowed=True,
    )


def mark_applied(
    item: ReplacementPlanItem,
    *,
    audit_review_id: int,
) -> ReplacementPlanItem:
    if not item.apply_allowed:
        raise ValueError("Only replacement-ready plans may be marked applied.")
    return replace(
        item,
        status="applied",
        applied=True,
        audit_review_id=audit_review_id,
    )


def summarize_replacement_plans(
    items: Sequence[ReplacementPlanItem],
) -> ReplacementSummary:
    decisions = Counter(item.decision for item in items)
    return ReplacementSummary(
        candidate_count=len(items),
        ready_count=sum(1 for item in items if item.apply_allowed),
        applied_count=sum(1 for item in items if item.applied),
        idempotent_count=decisions.get("no_action_already_replaced", 0),
        valid_stop_count=sum(1 for item in items if item.status == "valid_stop"),
        decision_counts=dict(sorted(decisions.items())),
    )


def classify_apply_set(items: Sequence[ReplacementPlanItem]) -> str:
    if items and all(
        item.decision == "no_action_already_replaced" for item in items
    ):
        return "idempotent_replay"
    if items and all(item.apply_allowed for item in items):
        return "apply_ready"
    return "blocked"
