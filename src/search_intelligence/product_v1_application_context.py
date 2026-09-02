"""Source-grounded Product V1 application generation context.

This module binds one authoritative Top-5 job to approved private Candidate Facts
and approved base CV/application-letter documents. Base documents are structure
and style sources only; candidate claims must come from approved Candidate Facts.

The module performs no provider call, draft persistence, operator approval,
submission or send action. It never grants application/product authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import re
from typing import Any, Iterable, Sequence


TOP5_AUTHORITY_SOURCE = "gold_product_v1_top_jobs"
REQUIRED_DOCUMENT_TYPES = ("base_cv", "base_application_letter")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ApplicationTargetSnapshot:
    silver_job_id: int
    product_rank: int
    title: str
    company_name: str
    source_url: str
    canonical_source_type: str
    product_readiness_status: str
    origin_validation_status: str
    activity_status: str
    hard_filter_status: str
    detail_text: str
    authority_source: str = TOP5_AUTHORITY_SOURCE
    employer_origin_authorized: bool | None = None

    @property
    def detail_sha256(self) -> str:
        return sha256(self.detail_text.encode("utf-8")).hexdigest()

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "silver_job_id": self.silver_job_id,
            "product_rank": self.product_rank,
            "title": self.title,
            "company_name": self.company_name,
            "source_url": self.source_url,
            "canonical_source_type": self.canonical_source_type,
            "product_readiness_status": self.product_readiness_status,
            "origin_validation_status": self.origin_validation_status,
            "activity_status": self.activity_status,
            "hard_filter_status": self.hard_filter_status,
            "detail_sha256": self.detail_sha256,
            "authority_source": self.authority_source,
            "employer_origin_authorized": self.employer_origin_authorized,
        }


@dataclass(frozen=True)
class ApplicationSourceDocumentSnapshot:
    document_type: str
    source_label: str
    source_reference: str
    content_sha256: str
    content: str
    status: str
    source_hash_verified: bool | None = None

    def canonical_manifest_entry(self) -> dict[str, object]:
        return {
            "document_type": self.document_type,
            "source_label": self.source_label,
            "source_reference": self.source_reference,
            "content_sha256": self.content_sha256,
            "status": self.status,
            "source_hash_verified": self.source_hash_verified,
            "fact_authority": "false",
        }


@dataclass(frozen=True)
class CandidateFactSnapshot:
    fact_key: str
    category: str
    evidence_class: str
    approval_status: str
    statement: str
    capability_tags: tuple[str, ...]
    limitations: tuple[str, ...]
    valid_from: date | None = None
    valid_until: date | None = None

    @property
    def statement_sha256(self) -> str:
        return sha256(self.statement.encode("utf-8")).hexdigest()

    def is_valid_on(self, as_of_date: date) -> bool:
        if self.approval_status != "approved":
            return False
        if self.valid_from is not None and as_of_date < self.valid_from:
            return False
        if self.valid_until is not None and as_of_date > self.valid_until:
            return False
        return True

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "fact_key": self.fact_key,
            "category": self.category,
            "evidence_class": self.evidence_class,
            "approval_status": self.approval_status,
            "statement": self.statement,
            "statement_sha256": self.statement_sha256,
            "capability_tags": list(self.capability_tags),
            "limitations": list(self.limitations),
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
        }


@dataclass(frozen=True)
class JobCapabilityReference:
    capability_tag: str
    evidence: str
    span_start: int
    span_end: int

    def canonical_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateClaimPlanEntry:
    fact_key: str
    statement: str
    statement_sha256: str
    limitations: tuple[str, ...]
    matched_capability_tags: tuple[str, ...]
    job_references: tuple[JobCapabilityReference, ...]
    claim_authority: str = "approved_candidate_fact"

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "fact_key": self.fact_key,
            "statement": self.statement,
            "statement_sha256": self.statement_sha256,
            "limitations": list(self.limitations),
            "matched_capability_tags": list(self.matched_capability_tags),
            "job_references": [reference.canonical_payload() for reference in self.job_references],
            "claim_authority": self.claim_authority,
        }


@dataclass(frozen=True)
class ProductV1ApplicationContext:
    target: ApplicationTargetSnapshot
    generation_ready: bool
    blocked_reasons: tuple[str, ...]
    source_documents: tuple[ApplicationSourceDocumentSnapshot, ...]
    approved_candidate_facts: tuple[CandidateFactSnapshot, ...]
    claim_plan: tuple[CandidateClaimPlanEntry, ...]
    candidate_profile_sha256: str
    as_of_date: date
    provider_requests: int = 0
    database_writes: int = 0
    application_writes: int = 0
    submission_writes: int = 0
    candidate_fact_authority: bool = False
    generation_context_authority: bool = False
    draft_approval_authority: bool = False
    application_authority: bool = False
    submission_authority: bool = False
    product_authority: bool = False

    def source_manifest(self) -> dict[str, Any]:
        return {
            "target": self.target.canonical_payload(),
            "candidate_profile_sha256": self.candidate_profile_sha256,
            "candidate_fact_keys": [fact.fact_key for fact in self.approved_candidate_facts],
            "candidate_fact_statement_sha256": {
                fact.fact_key: fact.statement_sha256 for fact in self.approved_candidate_facts
            },
            "documents": [document.canonical_manifest_entry() for document in self.source_documents],
            "as_of_date": self.as_of_date.isoformat(),
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "target": self.target.canonical_payload(),
            "generation_ready": self.generation_ready,
            "blocked_reasons": list(self.blocked_reasons),
            "source_manifest": self.source_manifest(),
            "approved_candidate_facts": [fact.canonical_payload() for fact in self.approved_candidate_facts],
            "claim_plan": [entry.canonical_payload() for entry in self.claim_plan],
            "provider_requests": self.provider_requests,
            "database_writes": self.database_writes,
            "application_writes": self.application_writes,
            "submission_writes": self.submission_writes,
            "candidate_fact_authority": self.candidate_fact_authority,
            "generation_context_authority": self.generation_context_authority,
            "draft_approval_authority": self.draft_approval_authority,
            "application_authority": self.application_authority,
            "submission_authority": self.submission_authority,
            "product_authority": self.product_authority,
        }


def _normalized_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is missing")
    return " ".join(value.split())


def _validate_target(target: ApplicationTargetSnapshot) -> tuple[str, ...]:
    reasons: list[str] = []
    if target.authority_source != TOP5_AUTHORITY_SOURCE:
        reasons.append("top5_authority_required")
    if target.product_rank < 1 or target.product_rank > 5:
        reasons.append("authoritative_top5_rank_required")
    if target.product_readiness_status != "rankable":
        reasons.append("job_not_rankable")
    if target.origin_validation_status != "validated":
        reasons.append("origin_not_validated")
    if target.activity_status != "active":
        reasons.append("job_not_confirmed_active")
    if target.hard_filter_status != "passed":
        reasons.append("hard_filter_not_passed")
    employer_origin_authorized = (
        target.canonical_source_type == "employer_origin"
        if target.employer_origin_authorized is None
        else target.employer_origin_authorized
    )
    if not employer_origin_authorized:
        reasons.append("employer_origin_required")
    if target.silver_job_id <= 0:
        reasons.append("invalid_silver_job_id")
    if not target.title.strip() or not target.company_name.strip():
        reasons.append("job_identity_incomplete")
    if not target.source_url.startswith("https://"):
        reasons.append("https_source_url_required")
    if not target.detail_text.strip():
        reasons.append("job_detail_evidence_required")
    return tuple(reasons)


def _validate_document(document: ApplicationSourceDocumentSnapshot) -> str | None:
    if document.document_type not in REQUIRED_DOCUMENT_TYPES:
        return "unsupported_application_source_document"
    if document.status != "approved":
        return f"{document.document_type}_not_approved"
    if not _SHA256_RE.fullmatch(document.content_sha256):
        return f"{document.document_type}_invalid_sha256"
    if document.source_hash_verified is None:
        actual_sha = sha256(document.content.encode("utf-8")).hexdigest()
        if actual_sha != document.content_sha256:
            return f"{document.document_type}_content_hash_mismatch"
    elif document.source_hash_verified is False:
        return f"{document.document_type}_content_hash_mismatch"
    if not document.source_reference.strip() or not document.source_label.strip():
        return f"{document.document_type}_source_reference_missing"
    return None


def _approved_documents(
    documents: Sequence[ApplicationSourceDocumentSnapshot],
) -> tuple[tuple[ApplicationSourceDocumentSnapshot, ...], tuple[str, ...]]:
    valid: dict[str, ApplicationSourceDocumentSnapshot] = {}
    reasons: list[str] = []
    for document in documents:
        reason = _validate_document(document)
        if reason is not None:
            reasons.append(reason)
            continue
        if document.document_type in valid:
            reasons.append(f"duplicate_{document.document_type}")
            continue
        valid[document.document_type] = document
    for document_type in REQUIRED_DOCUMENT_TYPES:
        if document_type not in valid:
            reasons.append(f"missing_{document_type}")
    ordered = tuple(valid[document_type] for document_type in REQUIRED_DOCUMENT_TYPES if document_type in valid)
    return ordered, tuple(sorted(set(reasons)))


def _normalize_capability_tag(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _tag_pattern(tag: str) -> re.Pattern[str]:
    escaped = re.escape(tag).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![\w]){escaped}(?![\w])", re.IGNORECASE)


def _job_references_for_fact(
    *, fact: CandidateFactSnapshot, detail_text: str
) -> tuple[JobCapabilityReference, ...]:
    references: list[JobCapabilityReference] = []
    seen: set[tuple[str, int, int]] = set()
    for raw_tag in fact.capability_tags:
        tag = _normalize_capability_tag(raw_tag)
        if not tag:
            continue
        for match in _tag_pattern(tag).finditer(detail_text):
            key = (tag, match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            references.append(
                JobCapabilityReference(
                    capability_tag=tag,
                    evidence=match.group(0),
                    span_start=match.start(),
                    span_end=match.end(),
                )
            )
    return tuple(references)


def _claim_plan(
    *, facts: Sequence[CandidateFactSnapshot], detail_text: str
) -> tuple[CandidateClaimPlanEntry, ...]:
    entries: list[CandidateClaimPlanEntry] = []
    for fact in facts:
        references = _job_references_for_fact(fact=fact, detail_text=detail_text)
        if not references:
            continue
        matched_tags = tuple(sorted({reference.capability_tag for reference in references}))
        entries.append(
            CandidateClaimPlanEntry(
                fact_key=fact.fact_key,
                statement=fact.statement,
                statement_sha256=fact.statement_sha256,
                limitations=fact.limitations,
                matched_capability_tags=matched_tags,
                job_references=references,
            )
        )
    return tuple(entries)


def build_product_v1_application_context(
    *,
    target: ApplicationTargetSnapshot,
    candidate_profile_status: str,
    candidate_profile_sha256: str,
    candidate_facts: Iterable[CandidateFactSnapshot],
    source_documents: Sequence[ApplicationSourceDocumentSnapshot],
    as_of_date: date,
) -> ProductV1ApplicationContext:
    """Build a bounded, non-mutating application generation context."""

    blocked = list(_validate_target(target))
    approved_documents, document_reasons = _approved_documents(source_documents)
    blocked.extend(document_reasons)

    if candidate_profile_status != "approved":
        blocked.append("candidate_fact_profile_not_approved")
    if not _SHA256_RE.fullmatch(candidate_profile_sha256):
        blocked.append("candidate_fact_profile_sha256_invalid")

    facts: list[CandidateFactSnapshot] = []
    if candidate_profile_status == "approved":
        for fact in candidate_facts:
            statement = _normalized_text(fact.statement, field_name="candidate fact statement")
            normalized = CandidateFactSnapshot(
                fact_key=_normalized_text(fact.fact_key, field_name="candidate fact key"),
                category=fact.category,
                evidence_class=fact.evidence_class,
                approval_status=fact.approval_status,
                statement=statement,
                capability_tags=tuple(tag for tag in fact.capability_tags if str(tag).strip()),
                limitations=tuple(item for item in fact.limitations if str(item).strip()),
                valid_from=fact.valid_from,
                valid_until=fact.valid_until,
            )
            if normalized.is_valid_on(as_of_date):
                facts.append(normalized)
    if not facts:
        blocked.append("approved_candidate_facts_required")

    facts.sort(key=lambda item: item.fact_key)
    claim_plan = _claim_plan(facts=facts, detail_text=target.detail_text)
    blocked_reasons = tuple(sorted(set(blocked)))
    generation_ready = not blocked_reasons

    return ProductV1ApplicationContext(
        target=target,
        generation_ready=generation_ready,
        blocked_reasons=blocked_reasons,
        source_documents=approved_documents,
        approved_candidate_facts=tuple(facts),
        claim_plan=claim_plan,
        candidate_profile_sha256=candidate_profile_sha256,
        as_of_date=as_of_date,
        generation_context_authority=generation_ready,
    )


__all__ = [
    "TOP5_AUTHORITY_SOURCE",
    "ApplicationSourceDocumentSnapshot",
    "ApplicationTargetSnapshot",
    "CandidateClaimPlanEntry",
    "CandidateFactSnapshot",
    "JobCapabilityReference",
    "ProductV1ApplicationContext",
    "build_product_v1_application_context",
]
