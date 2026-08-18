"""Bounded AI drafting for Product V1 CV and application-letter assistance.

A source-grounded :class:`ProductV1ApplicationContext` is required before any
provider request. Models may produce only a structured ``draft_for_review``
package. Every candidate-specific fragment must cite approved Candidate Fact
keys from the deterministic claim plan; vacancy-specific assertions must cite
exact employer-origin detail quotes.

Draft approval, persistence, application authority, submission and send remain
separate operator/product boundaries. Tavily, deep external evidence and Pro
mode are intentionally excluded from this same-context drafting stage.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Callable, Mapping, Sequence

import requests

from src.search_intelligence.detail_semantics_grounding import locate_unique_evidence_span
from src.search_intelligence.llm_booster_policy import (
    BoosterStage,
    HARD_COST_CEILING_USD,
    MODEL_CONFIG,
)
from src.search_intelligence.origin_llm_adjudication import OPENAI_RESPONSES_URL
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)
from src.search_intelligence.product_v1_application_context import (
    ProductV1ApplicationContext,
)


DRAFT_FRAGMENT_KINDS = (
    "cv_summary",
    "cv_bullet",
    "letter_opening",
    "letter_fit",
    "letter_closing",
)
MODEL_STAGES = (
    BoosterStage.LUNA_MEDIUM,
    BoosterStage.TERRA_MEDIUM,
    BoosterStage.SOL_MEDIUM,
    BoosterStage.LUNA_MAX,
)
MAX_DETAIL_TEXT_CHARS = 16_000
MAX_FRAGMENTS = 12
MAX_FRAGMENT_CHARS = 2_000
MAX_FACT_KEYS_PER_FRAGMENT = 4
MAX_JOB_QUOTES_PER_FRAGMENT = 4

_NUMERIC_TOKEN_RE = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?%?(?![\w])")

SYSTEM_INSTRUCTIONS = """Create source-grounded job-application draft fragments for operator review only.
Use only the supplied authoritative vacancy detail and approved Candidate Fact claim plan. Candidate facts are
private factual authority; base-document text is intentionally not supplied as fact authority. Return status
'draft_for_review' and structured fragments only. Every cv_summary/cv_bullet must cite at least one allowed
candidate_fact_key. Every letter_opening must cite at least one exact vacancy quote. Every letter_fit must cite at
least one allowed candidate_fact_key and one exact vacancy quote. letter_closing must stay generic and cite no
facts or vacancy quotes. Do not invent years, counts, percentages, certifications, employers, skills, salary,
location, availability or experience. Do not approve, persist, submit or send anything. Do not claim application,
submission or product authority. Do not use outside knowledge.
"""

Transport = Callable[
    [str, Mapping[str, str], Mapping[str, object], float], Mapping[str, object]
]


@dataclass(frozen=True)
class DraftJobEvidenceReference:
    evidence: str
    span_start: int
    span_end: int

    def canonical_payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ApplicationDraftFragment:
    kind: str
    text: str
    candidate_fact_keys: tuple[str, ...]
    job_evidence: tuple[DraftJobEvidenceReference, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "text": self.text,
            "candidate_fact_keys": list(self.candidate_fact_keys),
            "job_evidence": [reference.canonical_payload() for reference in self.job_evidence],
        }


@dataclass(frozen=True)
class ApplicationDraftPackage:
    status: str
    fragments: tuple[ApplicationDraftFragment, ...]
    rationale: str
    source_manifest_sha256: str
    candidate_fact_keys_used: tuple[str, ...]
    draft_approval_authority: bool = False
    application_authority: bool = False
    submission_authority: bool = False
    product_authority: bool = False

    def canonical_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "fragments": [fragment.canonical_payload() for fragment in self.fragments],
            "rationale": self.rationale,
            "source_manifest_sha256": self.source_manifest_sha256,
            "candidate_fact_keys_used": list(self.candidate_fact_keys_used),
            "draft_approval_authority": self.draft_approval_authority,
            "application_authority": self.application_authority,
            "submission_authority": self.submission_authority,
            "product_authority": self.product_authority,
        }


@dataclass(frozen=True)
class ApplicationDraftObservation:
    status: str
    request_attempted: bool
    package: ApplicationDraftPackage | None
    model: str | None = None
    response_id: str | None = None
    estimated_cost_usd: float = 0.0
    rationale: str = ""
    draft_approval_authority: bool = False
    application_authority: bool = False
    submission_authority: bool = False
    product_authority: bool = False


@dataclass(frozen=True)
class ApplicationDraftStageEvidence:
    stage: BoosterStage
    attempted: bool
    status: str
    reason_code: str
    provider_requests: int
    package_fingerprint: str | None = None
    estimated_cost_usd: float = 0.0
    draft_approval_authority: bool = False
    application_authority: bool = False
    submission_authority: bool = False
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        return payload


@dataclass(frozen=True)
class ProductV1ApplicationDraftExecution:
    context: ProductV1ApplicationContext
    package: ApplicationDraftPackage | None
    stages: tuple[ApplicationDraftStageEvidence, ...]
    provider_requests: int
    llm_requests: int
    tavily_requests: int = 0
    database_writes: int = 0
    application_writes: int = 0
    submission_writes: int = 0
    send_actions: int = 0
    draft_approval_authority: bool = False
    application_authority: bool = False
    submission_authority: bool = False
    product_authority: bool = False

    @property
    def estimated_model_cost_usd(self) -> float:
        return sum(stage.estimated_cost_usd for stage in self.stages)

    def to_json(self) -> dict[str, object]:
        return {
            "context_source_manifest": self.context.source_manifest(),
            "package": self.package.canonical_payload() if self.package else None,
            "stages": [stage.to_json() for stage in self.stages],
            "provider_requests": self.provider_requests,
            "llm_requests": self.llm_requests,
            "tavily_requests": self.tavily_requests,
            "estimated_model_cost_usd": round(self.estimated_model_cost_usd, 8),
            "database_writes": self.database_writes,
            "application_writes": self.application_writes,
            "submission_writes": self.submission_writes,
            "send_actions": self.send_actions,
            "draft_approval_authority": self.draft_approval_authority,
            "application_authority": self.application_authority,
            "submission_authority": self.submission_authority,
            "product_authority": self.product_authority,
        }


def _transport(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, object],
    timeout_seconds: float,
) -> Mapping[str, object]:
    response = requests.post(
        url,
        headers=dict(headers),
        json=dict(payload),
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    decoded = response.json()
    if not isinstance(decoded, Mapping):
        raise ValueError("OpenAI response root must be an object")
    return decoded


def _extract_output_text(response: Mapping[str, object]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    output = response.get("output")
    if not isinstance(output, list):
        raise ValueError("response contains no output array")
    parts: list[str] = []
    for item in output:
        if not isinstance(item, Mapping):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if (
                isinstance(block, Mapping)
                and block.get("type") == "output_text"
                and isinstance(block.get("text"), str)
            ):
                parts.append(str(block["text"]))
    if not parts:
        raise ValueError("response contains no output_text")
    return "".join(parts)


def _estimated_cost(model: str, usage: Mapping[str, object] | None) -> float:
    prices = MODEL_PRICES_USD_PER_MILLION.get(model)
    if prices is None or usage is None:
        return 0.0
    input_price, output_price = prices
    return (
        int(usage.get("input_tokens") or 0) * input_price / 1_000_000
        + int(usage.get("output_tokens") or 0) * output_price / 1_000_000
    )


def _safe_message(exc: BaseException) -> str:
    text = " ".join(str(exc).split()) or type(exc).__name__
    return re.sub(r"Bearer\s+\S+", "Bearer ***", text, flags=re.IGNORECASE)[:500]


def _source_manifest_sha256(context: ProductV1ApplicationContext) -> str:
    encoded = json.dumps(
        context.source_manifest(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _schema(allowed_fact_keys: Sequence[str]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "fragments", "rationale"],
        "properties": {
            "status": {"type": "string", "enum": ["draft_for_review"]},
            "fragments": {
                "type": "array",
                "minItems": 2,
                "maxItems": MAX_FRAGMENTS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "text", "candidate_fact_keys", "job_evidence"],
                    "properties": {
                        "kind": {"type": "string", "enum": list(DRAFT_FRAGMENT_KINDS)},
                        "text": {"type": "string", "minLength": 1, "maxLength": MAX_FRAGMENT_CHARS},
                        "candidate_fact_keys": {
                            "type": "array",
                            "maxItems": MAX_FACT_KEYS_PER_FRAGMENT,
                            "uniqueItems": True,
                            "items": {"type": "string", "enum": list(allowed_fact_keys)},
                        },
                        "job_evidence": {
                            "type": "array",
                            "maxItems": MAX_JOB_QUOTES_PER_FRAGMENT,
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1, "maxLength": 1_200},
                        },
                    },
                },
            },
            "rationale": {"type": "string", "maxLength": 600},
        },
    }


def _packet(context: ProductV1ApplicationContext) -> dict[str, object]:
    claim_plan = []
    for entry in context.claim_plan:
        claim_plan.append(
            {
                "fact_key": entry.fact_key,
                "approved_statement": entry.statement,
                "limitations": list(entry.limitations),
                "matched_job_evidence": [
                    reference.evidence for reference in entry.job_references
                ],
            }
        )
    return {
        "target": {
            "title": context.target.title,
            "company_name": context.target.company_name,
            "source_url": context.target.source_url,
            "detail_text": context.target.detail_text[:MAX_DETAIL_TEXT_CHARS],
        },
        "approved_claim_plan": claim_plan,
        "source_manifest_sha256": _source_manifest_sha256(context),
        "base_documents": [
            {
                "document_type": document.document_type,
                "source_label": document.source_label,
                "content_sha256": document.content_sha256,
                "fact_authority": False,
            }
            for document in context.source_documents
        ],
        "authority_constraints": {
            "draft_for_review_only": True,
            "candidate_claims_require_fact_keys": True,
            "vacancy_assertions_require_exact_quotes": True,
            "base_document_fact_authority": False,
            "draft_approval_authority": False,
            "application_authority": False,
            "submission_authority": False,
            "send_authority": False,
            "product_authority": False,
        },
    }


def _validate_root(decoded: Mapping[str, object]) -> None:
    if set(decoded) != {"status", "fragments", "rationale"}:
        raise ValueError("application draft response contains unexpected root fields")
    if decoded.get("status") != "draft_for_review":
        raise ValueError("application draft status must be draft_for_review")


def _fact_map(context: ProductV1ApplicationContext) -> dict[str, str]:
    return {entry.fact_key: entry.statement for entry in context.claim_plan}


def _validate_numeric_claims(
    *,
    text: str,
    fact_statements: Sequence[str],
    job_quotes: Sequence[str],
    context: ProductV1ApplicationContext,
) -> None:
    allowed_sources = [
        *fact_statements,
        *job_quotes,
        context.target.title,
        context.target.company_name,
    ]
    for token in _NUMERIC_TOKEN_RE.findall(text):
        if not any(token.casefold() in source.casefold() for source in allowed_sources):
            raise ValueError(f"unsupported numeric draft claim: {token}")


def _validate_fragment(
    *,
    raw: Mapping[str, object],
    context: ProductV1ApplicationContext,
    allowed_facts: Mapping[str, str],
) -> ApplicationDraftFragment:
    expected = {"kind", "text", "candidate_fact_keys", "job_evidence"}
    if set(raw) != expected:
        raise ValueError("application draft fragment contains unexpected fields")
    kind = str(raw.get("kind") or "")
    if kind not in DRAFT_FRAGMENT_KINDS:
        raise ValueError(f"unsupported application draft fragment kind: {kind}")
    text = " ".join(str(raw.get("text") or "").split())
    if not text or len(text) > MAX_FRAGMENT_CHARS:
        raise ValueError("application draft fragment text is empty or oversized")

    raw_fact_keys = raw.get("candidate_fact_keys")
    raw_job_evidence = raw.get("job_evidence")
    if not isinstance(raw_fact_keys, list) or not isinstance(raw_job_evidence, list):
        raise ValueError("application draft fragment references must be arrays")
    fact_keys = tuple(str(item) for item in raw_fact_keys)
    job_quotes = tuple(str(item) for item in raw_job_evidence)
    if len(fact_keys) > MAX_FACT_KEYS_PER_FRAGMENT or len(set(fact_keys)) != len(fact_keys):
        raise ValueError("application draft candidate fact references are invalid")
    if len(job_quotes) > MAX_JOB_QUOTES_PER_FRAGMENT or len(set(job_quotes)) != len(job_quotes):
        raise ValueError("application draft vacancy evidence references are invalid")
    unknown = [fact_key for fact_key in fact_keys if fact_key not in allowed_facts]
    if unknown:
        raise ValueError(f"unknown Candidate Fact key in application draft: {unknown[0]}")

    if kind in {"cv_summary", "cv_bullet"} and not fact_keys:
        raise ValueError(f"{kind} requires an approved Candidate Fact key")
    if kind == "letter_opening" and not job_quotes:
        raise ValueError("letter_opening requires exact vacancy evidence")
    if kind == "letter_fit" and (not fact_keys or not job_quotes):
        raise ValueError("letter_fit requires Candidate Fact and vacancy evidence")
    if kind == "letter_closing" and (fact_keys or job_quotes):
        raise ValueError("letter_closing must stay generic and uncited")

    references: list[DraftJobEvidenceReference] = []
    for quote in job_quotes:
        if not quote or len(quote) > 1_200:
            raise ValueError("vacancy evidence quote is empty or oversized")
        start, end = locate_unique_evidence_span(
            detail_text=context.target.detail_text,
            evidence=quote,
        )
        references.append(
            DraftJobEvidenceReference(evidence=quote, span_start=start, span_end=end)
        )

    fact_statements = [allowed_facts[fact_key] for fact_key in fact_keys]
    _validate_numeric_claims(
        text=text,
        fact_statements=fact_statements,
        job_quotes=job_quotes,
        context=context,
    )
    return ApplicationDraftFragment(
        kind=kind,
        text=text,
        candidate_fact_keys=fact_keys,
        job_evidence=tuple(references),
    )


def _validate_package(
    *, decoded: Mapping[str, object], context: ProductV1ApplicationContext
) -> ApplicationDraftPackage:
    _validate_root(decoded)
    raw_fragments = decoded.get("fragments")
    if not isinstance(raw_fragments, list):
        raise ValueError("application draft fragments must be an array")
    if not 2 <= len(raw_fragments) <= MAX_FRAGMENTS:
        raise ValueError("application draft fragment count is outside bounds")

    allowed_facts = _fact_map(context)
    fragments: list[ApplicationDraftFragment] = []
    seen_text: set[str] = set()
    for raw in raw_fragments:
        if not isinstance(raw, Mapping):
            raise ValueError("application draft fragment must be an object")
        fragment = _validate_fragment(
            raw=raw,
            context=context,
            allowed_facts=allowed_facts,
        )
        fingerprint_text = fragment.text.casefold()
        if fingerprint_text in seen_text:
            raise ValueError("duplicate application draft fragment text")
        seen_text.add(fingerprint_text)
        fragments.append(fragment)

    kinds = [fragment.kind for fragment in fragments]
    if not any(kind in {"cv_summary", "cv_bullet"} for kind in kinds):
        raise ValueError("application draft package requires CV assistance")
    if not any(kind.startswith("letter_") for kind in kinds):
        raise ValueError("application draft package requires application-letter assistance")
    if kinds.count("cv_summary") > 1:
        raise ValueError("application draft package permits at most one cv_summary")
    if kinds.count("letter_opening") > 1 or kinds.count("letter_closing") > 1:
        raise ValueError("application draft package permits one opening/closing maximum")

    used_fact_keys = tuple(
        sorted({fact_key for fragment in fragments for fact_key in fragment.candidate_fact_keys})
    )
    rationale = " ".join(str(decoded.get("rationale") or "").split())[:600]
    return ApplicationDraftPackage(
        status="draft_for_review",
        fragments=tuple(fragments),
        rationale=rationale,
        source_manifest_sha256=_source_manifest_sha256(context),
        candidate_fact_keys_used=used_fact_keys,
    )


def request_product_v1_application_draft(
    *,
    context: ProductV1ApplicationContext,
    api_key: str,
    model: str,
    reasoning_effort: str = "medium",
    max_output_tokens: int = 1_500,
    timeout_seconds: float = 90.0,
    transport: Transport = _transport,
) -> ApplicationDraftObservation:
    """Request one draft-for-review package from an already-ready context."""

    if not context.generation_ready:
        return ApplicationDraftObservation(
            status="blocked",
            request_attempted=False,
            package=None,
            model=model,
            rationale="generation_context_not_ready",
        )
    allowed_fact_keys = tuple(sorted(_fact_map(context)))
    if not allowed_fact_keys:
        return ApplicationDraftObservation(
            status="blocked",
            request_attempted=False,
            package=None,
            model=model,
            rationale="candidate_job_claim_plan_required",
        )

    packet = _packet(context)
    packet_json = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    packet_sha = hashlib.sha256(packet_json.encode("utf-8")).hexdigest()
    payload: dict[str, object] = {
        "model": model,
        "store": False,
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": reasoning_effort},
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_INSTRUCTIONS}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": packet_json}],
            },
        ],
        "text": {
            "verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": "product_v1_application_draft_for_review",
                "strict": True,
                "schema": _schema(allowed_fact_keys),
            },
        },
    }

    try:
        response = transport(
            OPENAI_RESPONSES_URL,
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            payload,
            timeout_seconds,
        )
        decoded = json.loads(_extract_output_text(response))
        if not isinstance(decoded, Mapping):
            raise ValueError("application draft response must be an object")
        package = _validate_package(decoded=decoded, context=context)
        usage = response.get("usage")
        usage_map = usage if isinstance(usage, Mapping) else None
        return ApplicationDraftObservation(
            status="completed",
            request_attempted=True,
            package=package,
            model=str(response.get("model") or model),
            response_id=str(response.get("id") or "") or None,
            estimated_cost_usd=_estimated_cost(model, usage_map),
            rationale=f"packet_sha256={packet_sha}; validated_draft_for_review",
        )
    except (
        json.JSONDecodeError,
        requests.RequestException,
        TypeError,
        ValueError,
    ) as exc:
        return ApplicationDraftObservation(
            status="failed_closed",
            request_attempted=True,
            package=None,
            model=model,
            estimated_cost_usd=0.0,
            rationale=(
                f"packet_sha256={packet_sha}; failure={type(exc).__name__}: "
                f"{_safe_message(exc)}"
            )[:700],
        )


def _package_fingerprint(package: ApplicationDraftPackage) -> str:
    encoded = json.dumps(
        package.canonical_payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


ModelCallback = Callable[[BoosterStage], ApplicationDraftObservation]


def execute_product_v1_application_drafter(
    *,
    context: ProductV1ApplicationContext,
    model: ModelCallback,
) -> ProductV1ApplicationDraftExecution:
    """Run the bounded model cascade and stop on the first validated draft."""

    ready = context.generation_ready and bool(context.claim_plan)
    stages: list[ApplicationDraftStageEvidence] = [
        ApplicationDraftStageEvidence(
            stage=BoosterStage.DETERMINISTIC,
            attempted=True,
            status="ready" if ready else "blocked",
            reason_code=(
                "source_grounded_application_context_ready"
                if ready
                else "source_grounded_application_context_incomplete"
            ),
            provider_requests=0,
        ),
        ApplicationDraftStageEvidence(
            stage=BoosterStage.TAVILY,
            attempted=False,
            status="skipped",
            reason_code="external_search_not_indicated_for_application_drafting",
            provider_requests=0,
        ),
    ]
    provider_requests = 0
    accepted_package: ApplicationDraftPackage | None = None

    for stage in MODEL_STAGES:
        if not ready or accepted_package is not None:
            stages.append(
                ApplicationDraftStageEvidence(
                    stage=stage,
                    attempted=False,
                    status="skipped",
                    reason_code=(
                        "validated_draft_already_available"
                        if accepted_package is not None
                        else "application_context_not_ready"
                    ),
                    provider_requests=0,
                )
            )
            continue

        observation = model(stage)
        request_count = int(observation.request_attempted)
        provider_requests += request_count
        cost = float(observation.estimated_cost_usd or 0.0)
        if (
            observation.draft_approval_authority
            or observation.application_authority
            or observation.submission_authority
            or observation.product_authority
        ):
            stages.append(
                ApplicationDraftStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="model_application_authority_claim_rejected",
                    provider_requests=request_count,
                    estimated_cost_usd=cost,
                )
            )
            break
        if cost < 0 or cost > HARD_COST_CEILING_USD[stage]:
            stages.append(
                ApplicationDraftStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="model_cost_ceiling_exceeded",
                    provider_requests=request_count,
                    estimated_cost_usd=cost,
                )
            )
            break
        if observation.status == "completed" and observation.package is not None:
            accepted_package = observation.package
            stages.append(
                ApplicationDraftStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="draft_for_review",
                    reason_code="source_grounded_draft_validated",
                    provider_requests=request_count,
                    package_fingerprint=_package_fingerprint(observation.package),
                    estimated_cost_usd=cost,
                )
            )
            continue

        # Invalid or malformed drafts have no authority and may escalate to the
        # next bounded model stage; no failed draft is persisted or reused.
        stages.append(
            ApplicationDraftStageEvidence(
                stage=stage,
                attempted=observation.request_attempted,
                status="unresolved",
                reason_code=(
                    "draft_validation_failed_closed"
                    if observation.status == "failed_closed"
                    else "no_validated_draft"
                ),
                provider_requests=request_count,
                estimated_cost_usd=cost,
            )
        )

    stages.append(
        ApplicationDraftStageEvidence(
            stage=BoosterStage.DEEP_EVIDENCE,
            attempted=False,
            status="skipped",
            reason_code="deep_external_evidence_not_activated_for_application_drafting",
            provider_requests=0,
        )
    )
    return ProductV1ApplicationDraftExecution(
        context=context,
        package=accepted_package,
        stages=tuple(stages),
        provider_requests=provider_requests,
        llm_requests=provider_requests,
    )


def openai_application_draft_model_callback(
    *,
    context: ProductV1ApplicationContext,
    api_key: str,
    transport: Transport = _transport,
) -> ModelCallback:
    """Bind the canonical bounded model campaign to one ready application context."""

    def callback(stage: BoosterStage) -> ApplicationDraftObservation:
        model, reasoning_effort = MODEL_CONFIG[stage]
        return request_product_v1_application_draft(
            context=context,
            api_key=api_key,
            model=model,
            reasoning_effort=reasoning_effort,
            transport=transport,
        )

    return callback


__all__ = [
    "ApplicationDraftFragment",
    "ApplicationDraftObservation",
    "ApplicationDraftPackage",
    "DraftJobEvidenceReference",
    "ProductV1ApplicationDraftExecution",
    "execute_product_v1_application_drafter",
    "openai_application_draft_model_callback",
    "request_product_v1_application_draft",
]
