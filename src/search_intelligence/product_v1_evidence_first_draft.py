"""Provider-free, source-grounded Product V1 review draft fallback.

This module is a resilience surface for the live demo, not a new product or
application authority. It may run only after the canonical Application Workspace
is generation-ready. It copies approved Candidate Fact statements and exact
vacancy evidence into a small deterministic review package; it does not invent
candidate claims, call a provider, persist a draft, approve an application,
submit, or send anything.

The result deliberately remains ``draft_for_review`` and is labelled by runtime
callers as ``deterministic_evidence_first`` so it cannot be confused with a
provider-polished draft.
"""

from __future__ import annotations

from hashlib import sha256
import json

from src.search_intelligence.product_v1_application_context import (
    CandidateClaimPlanEntry,
    ProductV1ApplicationContext,
)
from src.search_intelligence.product_v1_application_drafter import (
    ApplicationDraftFragment,
    ApplicationDraftPackage,
    DraftJobEvidenceReference,
)


MAX_EVIDENCE_FIRST_FACTS = 3
MAX_SOURCE_TEXT_CHARS = 1_800


class EvidenceFirstDraftStop(ValueError):
    """Fail closed when a deterministic review draft cannot stay source-grounded."""


def _manifest_sha256(context: ProductV1ApplicationContext) -> str:
    encoded = json.dumps(
        context.source_manifest(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


def _require_source_text(value: str, *, label: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise EvidenceFirstDraftStop(f"{label} is empty")
    if len(text) > MAX_SOURCE_TEXT_CHARS:
        raise EvidenceFirstDraftStop(f"{label} exceeds deterministic draft bound")
    return text


def _first_reference(entry: CandidateClaimPlanEntry) -> DraftJobEvidenceReference:
    if not entry.job_references:
        raise EvidenceFirstDraftStop(
            f"claim plan entry has no exact vacancy evidence: {entry.fact_key}"
        )
    reference = entry.job_references[0]
    return DraftJobEvidenceReference(
        evidence=reference.evidence,
        span_start=reference.span_start,
        span_end=reference.span_end,
    )


def _assert_reference_exact(
    context: ProductV1ApplicationContext,
    reference: DraftJobEvidenceReference,
) -> None:
    detail = context.target.detail_text
    if not (0 <= reference.span_start < reference.span_end <= len(detail)):
        raise EvidenceFirstDraftStop("vacancy evidence span is outside current detail text")
    if detail[reference.span_start : reference.span_end] != reference.evidence:
        raise EvidenceFirstDraftStop("vacancy evidence span no longer matches current detail")


def build_evidence_first_review_draft(
    context: ProductV1ApplicationContext,
) -> ApplicationDraftPackage:
    """Build a deterministic, evidence-copy review package with zero provider calls."""

    if not context.generation_ready:
        raise EvidenceFirstDraftStop("source-grounded application context is not ready")
    if not context.claim_plan:
        raise EvidenceFirstDraftStop("candidate-job claim plan is required")

    entries = tuple(context.claim_plan[:MAX_EVIDENCE_FIRST_FACTS])
    primary = entries[0]
    primary_statement = _require_source_text(
        primary.statement,
        label=f"Candidate Fact {primary.fact_key}",
    )
    primary_reference = _first_reference(primary)
    _assert_reference_exact(context, primary_reference)

    fragments: list[ApplicationDraftFragment] = [
        ApplicationDraftFragment(
            kind="cv_summary",
            text=primary_statement,
            candidate_fact_keys=(primary.fact_key,),
            job_evidence=(),
        )
    ]

    for entry in entries[1:]:
        statement = _require_source_text(
            entry.statement,
            label=f"Candidate Fact {entry.fact_key}",
        )
        fragments.append(
            ApplicationDraftFragment(
                kind="cv_bullet",
                text=statement,
                candidate_fact_keys=(entry.fact_key,),
                job_evidence=(),
            )
        )

    title = _require_source_text(context.target.title, label="job title")
    company = _require_source_text(context.target.company_name, label="company name")
    quote = _require_source_text(primary_reference.evidence, label="vacancy evidence")
    fragments.extend(
        (
            ApplicationDraftFragment(
                kind="letter_opening",
                text=(
                    f"I am applying for the {title} role at {company}. "
                    f"The vacancy explicitly references {quote}."
                ),
                candidate_fact_keys=(),
                job_evidence=(primary_reference,),
            ),
            ApplicationDraftFragment(
                kind="letter_fit",
                text=(
                    f"{primary_statement} "
                    f"This is directly relevant to the vacancy evidence: {quote}."
                ),
                candidate_fact_keys=(primary.fact_key,),
                job_evidence=(primary_reference,),
            ),
            ApplicationDraftFragment(
                kind="letter_closing",
                text="I would welcome the opportunity to discuss the role and the fit in more detail.",
                candidate_fact_keys=(),
                job_evidence=(),
            ),
        )
    )

    used_fact_keys = tuple(
        sorted({key for fragment in fragments for key in fragment.candidate_fact_keys})
    )
    return ApplicationDraftPackage(
        status="draft_for_review",
        fragments=tuple(fragments),
        rationale=(
            "Deterministic evidence-first fallback assembled only from approved "
            "Candidate Facts, exact current vacancy evidence and authoritative job identity; "
            "provider polishing was not required. REVIEW REQUIRED."
        ),
        source_manifest_sha256=_manifest_sha256(context),
        candidate_fact_keys_used=used_fact_keys,
    )


__all__ = [
    "EvidenceFirstDraftStop",
    "build_evidence_first_review_draft",
]
