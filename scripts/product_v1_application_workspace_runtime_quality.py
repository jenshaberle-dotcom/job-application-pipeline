"""Product V1 Application Workspace drafting binding.

The Product path now uses embedded Codex for one bounded responsibility only:
adapting the approved CV profile/competency text and the application-letter text
to the exact selected vacancy. Deterministic context, source truth, template
authority, rendering, submission boundaries and all writes remain outside Codex.

If Codex allowance/credits/authentication are unavailable, the draft stops
visibly. JAP no longer substitutes deterministic filler prose for an
operator-facing application.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Mapping

from scripts.product_v1_application_workspace_runtime import (
    application_workspace_payload,
    load_application_workspace,
    require_live_application_target,
)
from src.search_intelligence.f6_template_review import (
    F6TemplateReviewStop,
    probe_review_replacement_overflows,
)
from src.search_intelligence.product_v1_codex_application_adapter import (
    request_codex_application_adaptation,
)


_MAX_CODEX_LAYOUT_ATTEMPTS = 3
_DEFAULT_PRIVATE_DOCUMENT_ROOT = Path("private_application_sources")
_CODEX_LAYOUT_ZONES = frozenset(
    {
        "base_cv:p1.short_profile",
        "base_cv:p1.competency_profile",
        *(f"base_application_letter:body.paragraph_{index}" for index in range(1, 7)),
    }
)


def _source_manifest_sha256(context: object) -> str:
    payload = context.source_manifest()
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _blocked_payload(*, context: object, reasons: list[str]) -> dict[str, object]:
    return {
        "schema": "job_application_pipeline.product_v1_application_draft_demo.v2",
        "status": "blocked",
        "blocked_reasons": reasons,
        "workspace": context.canonical_payload(),
        "draft_mode": "codex_embedded_v1",
        "codex_requests": 0,
        "provider_requests": 0,
        "database_writes": 0,
        "application_writes": 0,
        "submission_writes": 0,
        "send_actions": 0,
    }


def _private_document_root() -> Path:
    raw = os.environ.get("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", "").strip()
    return (
        Path(raw).expanduser().resolve()
        if raw
        else _DEFAULT_PRIVATE_DOCUMENT_ROOT.resolve()
    )


def _probe_generated_package_overflows(
    package: Mapping[str, object],
) -> tuple[str, ...]:
    replacements = package.get("zone_replacements")
    if not isinstance(replacements, Mapping):
        raise F6TemplateReviewStop(
            "generated Codex package has no template zone replacements"
        )
    return probe_review_replacement_overflows(
        root=_private_document_root(),
        replacements_by_document=replacements,
    )


def _compact_job_title(value: object) -> str:
    title = " ".join(str(value or "").split())
    return re.sub(
        r"\s*\((?:all\s+genders|m\s*/\s*w\s*/\s*d|w\s*/\s*m\s*/\s*d|"
        r"d\s*/\s*m\s*/\s*w|m\s*/\s*f\s*/\s*d|f\s*/\s*m\s*/\s*d)\)\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip() or title


def _refresh_application_letter_preview(package: dict[str, object]) -> None:
    preview = package.get("preview")
    replacements = package.get("zone_replacements")
    if not isinstance(preview, dict) or not isinstance(replacements, Mapping):
        return
    letter = replacements.get("base_application_letter")
    if not isinstance(letter, Mapping):
        return
    parts = [
        str(letter.get("salutation") or "").strip(),
        *(
            str(letter.get(f"body.paragraph_{index}") or "").strip()
            for index in range(1, 7)
        ),
        str(letter.get("closing.formula") or "").strip(),
    ]
    preview["application_letter"] = "\n\n".join(part for part in parts if part)


def _apply_deterministic_layout_repairs(
    package: Mapping[str, object],
    *,
    layout_overflows: tuple[str, ...],
    context: object,
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Repair JAP-owned or safely-normalizable zones without another LLM request.

    Some F6 zones are generated deterministically by JAP, so asking Codex to repair
    them can never converge. Salutation is hybrid: Codex may personalize it, but a
    neutral professional form is a safe deterministic fallback when the exact
    frozen zone cannot hold the personalized form.
    """

    repaired = deepcopy(dict(package))
    replacements = repaired.get("zone_replacements")
    if not isinstance(replacements, dict):
        return repaired, ()
    letter = replacements.get("base_application_letter")
    cv = replacements.get("base_cv")
    if not isinstance(letter, dict) or not isinstance(cv, dict):
        return repaired, ()

    language = str(repaired.get("language") or "de").strip().casefold()
    contact_name = " ".join(str(repaired.get("contact_name") or "").split())
    company_name = " ".join(
        str(getattr(getattr(context, "target", None), "company_name", "") or "").split()
    )
    title = _compact_job_title(
        getattr(getattr(context, "target", None), "title", "")
    )
    repairs: list[str] = []

    for qualified_zone in layout_overflows:
        if qualified_zone == "base_cv:p2.footer.date":
            raw = str(cv.get("p2.footer.date") or "")
            match = re.fullmatch(
                r"([^,]+),\s*(\d{1,2})\.\s+\S+\s+(\d{4})",
                raw,
            )
            if match:
                replacement = (
                    f"{match.group(1)}, {int(match.group(2)):02d}."
                    f"{context.as_of_date.month:02d}.{match.group(3)}"
                )
                cv["p2.footer.date"] = replacement
                repairs.append(f"{qualified_zone}=compact_date")
        elif qualified_zone == "base_application_letter:salutation":
            replacement = "Guten Tag," if language == "de" else "Hello,"
            if str(letter.get("salutation") or "") != replacement:
                letter["salutation"] = replacement
                repairs.append(f"{qualified_zone}=neutral_compact")
        elif qualified_zone == "base_application_letter:closing.formula":
            replacement = "Freundliche Grüße" if language == "de" else "Kind regards"
            if str(letter.get("closing.formula") or "") != replacement:
                letter["closing.formula"] = replacement
                repairs.append(f"{qualified_zone}=compact_closing")
        elif qualified_zone == "base_application_letter:subject":
            replacement = title
            if str(letter.get("subject") or "") != replacement and replacement:
                letter["subject"] = replacement
                repairs.append(f"{qualified_zone}=exact_title_only")
        elif qualified_zone == "base_application_letter:recipient.block":
            replacement = company_name
            if contact_name:
                replacement = f"{company_name}\n{contact_name}".strip()
            if str(letter.get("recipient.block") or "") != replacement and replacement:
                letter["recipient.block"] = replacement
                repairs.append(f"{qualified_zone}=compact_recipient")
        elif qualified_zone == "base_application_letter:date":
            raw = str(letter.get("date") or "")
            match = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
            if match:
                replacement = f"{match.group(1)}.{match.group(2)}.{match.group(3)[2:]}"
                letter["date"] = replacement
                repairs.append(f"{qualified_zone}=compact_date")

    if repairs:
        _refresh_application_letter_preview(repaired)
    return repaired, tuple(repairs)


def _codex_repairable_overflows(
    layout_overflows: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(zone for zone in layout_overflows if zone in _CODEX_LAYOUT_ZONES)


def _unsupported_layout_overflows(
    layout_overflows: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(zone for zone in layout_overflows if zone not in _CODEX_LAYOUT_ZONES)


def _draft_unavailable_payload(
    *,
    context: object,
    result: object,
    codex_requests: int,
    final_url: str,
    fetched_title: str,
    evidence_mode: str,
    job_detail_http_gets: int,
    reason_code: str | None = None,
    reason: str | None = None,
    layout_overflows: tuple[str, ...] = (),
    automatic_layout_repairs: tuple[str, ...] = (),
) -> dict[str, object]:
    resolved_reason_code = reason_code or getattr(result, "reason_code", None) or "codex_unavailable"
    resolved_reason = reason or getattr(result, "reason", None) or "Embedded Codex drafting is unavailable."
    return {
        "schema": "job_application_pipeline.product_v1_application_draft_demo.v2",
        "status": "draft_unavailable",
        "reason": resolved_reason,
        "reason_code": resolved_reason_code,
        "retryable": resolved_reason_code
        in {
            "codex_capacity_unavailable",
            "codex_timeout",
            "codex_execution_failed",
            "f6_template_fit_unresolved",
        },
        "draft_mode": "codex_embedded_v1",
        "codex_model": getattr(result, "model", None),
        "codex_reasoning_effort": getattr(result, "reasoning_effort", None),
        "codex_version": getattr(result, "codex_version", None),
        "codex_requests": codex_requests,
        "provider_requests": codex_requests,
        "llm_requests": codex_requests,
        "layout_fit_status": (
            "unresolved" if layout_overflows else "not_attempted"
        ),
        "layout_overflows": list(layout_overflows),
        "automatic_layout_repairs": list(automatic_layout_repairs),
        "fallback_generated": False,
        "fallback_policy": "no_low_quality_prose_fallback",
        "workspace": context.canonical_payload(),
        "live_job_evidence": {
            "final_url": final_url,
            "fetched_title": fetched_title,
            "detail_sha256": context.target.detail_sha256,
            "evidence_mode": evidence_mode,
        },
        "vacancy_revalidation_http_gets": 1,
        "lifecycle_health_observation_writes": 0,
        "job_detail_http_gets": job_detail_http_gets,
        "current_observation_detail_reuse": int(
            evidence_mode == "exact_persisted_observation"
        ),
        "database_writes": 0,
        "application_writes": 0,
        "submission_writes": 0,
        "send_actions": 0,
    }


def _local_private_draft_payload(
    *,
    context: object,
    final_url: str,
    fetched_title: str,
    evidence_mode: str,
    job_detail_http_gets: int,
) -> dict[str, object]:
    """Prepare a provider-free review draft from the current private templates.

    Descriptive source wording is preserved. JAP updates only deterministic
    target/date metadata; the operator may edit semantic text locally before the
    exact renderer is invoked. No document content leaves the local runtime.
    """

    language = "de"
    as_of_date = context.as_of_date
    months = (
        "Januar Februar März April Mai Juni Juli August September "
        "Oktober November Dezember"
    ).split()
    company_name = str(context.target.company_name).strip()
    title = str(context.target.title).strip()
    replacements: dict[str, dict[str, str]] = {
        "base_cv": {
            "p2.footer.date": (
                f"Hannover, {as_of_date.day}. {months[as_of_date.month - 1]} "
                f"{as_of_date.year}"
            ),
        },
        "base_application_letter": {
            "recipient.block": company_name,
            "date": as_of_date.strftime("%d.%m.%Y"),
            "subject": f"Bewerbung als {title}",
            "salutation": "Guten Tag,",
        },
    }
    package: dict[str, object] = {
        "status": "draft_for_review",
        "language": language,
        "rationale": (
            "Local-only mode: source wording is preserved and only deterministic "
            "target/date fields are prepared automatically. Descriptive adaptation "
            "remains an explicit local human edit."
        ),
        "contact_name": "",
        "zone_replacements": replacements,
        "draft_approval_authority": False,
        "application_authority": False,
        "submission_authority": False,
        "send_authority": False,
    }

    try:
        overflows = _probe_generated_package_overflows(package)
    except F6TemplateReviewStop as exc:
        return {
            "schema": "job_application_pipeline.product_v1_application_draft_demo.v2",
            "status": "draft_unavailable",
            "reason": str(exc),
            "reason_code": "f6_template_preflight_unavailable",
            "draft_mode": "local_private_edit",
            "provider_requests": 0,
            "llm_requests": 0,
            "database_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        }

    package, repairs = _apply_deterministic_layout_repairs(
        package,
        layout_overflows=overflows,
        context=context,
    )
    if repairs:
        try:
            overflows = _probe_generated_package_overflows(package)
        except F6TemplateReviewStop as exc:
            return {
                "schema": "job_application_pipeline.product_v1_application_draft_demo.v2",
                "status": "draft_unavailable",
                "reason": str(exc),
                "reason_code": "f6_template_preflight_unavailable",
                "draft_mode": "local_private_edit",
                "provider_requests": 0,
                "llm_requests": 0,
                "database_writes": 0,
                "submission_writes": 0,
                "send_actions": 0,
            }

    package["source_manifest_sha256"] = _source_manifest_sha256(context)
    package["candidate_fact_keys_used"] = []
    return {
        "schema": "job_application_pipeline.product_v1_application_draft_demo.v2",
        "status": "draft_for_review",
        "draft_mode": "local_private_edit",
        "fallback_reason": None,
        "fallback_generated": False,
        "quality_contract": "f6_local_private_manual_semantic_review_v1",
        "layout_policy": "preserve_exact_template_layout_modify_text_zones_only",
        "layout_fit_status": (
            "exact_template_preflight_pass"
            if not overflows
            else "local_manual_adjustment_required"
        ),
        "layout_overflows": list(overflows),
        "automatic_layout_repairs": list(repairs),
        "provider_requests": 0,
        "llm_requests": 0,
        "codex_requests": 0,
        "base_cv_text_shared_with_codex": False,
        "base_application_letter_text_shared_with_codex": False,
        "vacancy_text_shared_with_codex": False,
        "private_document_content_left_device": False,
        "render_status": "local_review_export_available",
        "package": package,
        "live_job_evidence": {
            "final_url": final_url,
            "fetched_title": fetched_title,
            "detail_sha256": context.target.detail_sha256,
            "evidence_mode": evidence_mode,
        },
        "job_detail_http_gets": job_detail_http_gets,
        "database_writes": 0,
        "application_writes": 0,
        "submission_writes": 0,
        "send_actions": 0,
        "draft_approval_authority": False,
        "application_authority": False,
        "submission_authority": False,
        "send_authority": False,
    }


def generate_application_draft_payload(
    silver_job_id: int,
    *,
    generation_mode: str = "codex_quality",
) -> dict[str, object]:
    require_live_application_target(silver_job_id)
    context, final_url, fetched_title, evidence_mode, job_detail_http_gets = (
        load_application_workspace(silver_job_id)
    )
    if not context.generation_ready:
        return _blocked_payload(
            context=context,
            reasons=list(context.blocked_reasons),
        )
    if generation_mode not in {"codex_quality", "local_private"}:
        return _blocked_payload(
            context=context,
            reasons=["unsupported_generation_mode"],
        )
    if generation_mode == "local_private":
        return _local_private_draft_payload(
            context=context,
            final_url=final_url,
            fetched_title=fetched_title,
            evidence_mode=evidence_mode,
            job_detail_http_gets=job_detail_http_gets,
        )
    if not context.claim_plan:
        return _blocked_payload(
            context=context,
            reasons=["candidate_job_claim_plan_required"],
        )

    result = request_codex_application_adaptation(context=context)
    codex_requests = int(result.attempted)
    if result.package is None:
        return _draft_unavailable_payload(
            context=context,
            result=result,
            codex_requests=codex_requests,
            final_url=final_url,
            fetched_title=fetched_title,
            evidence_mode=evidence_mode,
            job_detail_http_gets=job_detail_http_gets,
        )

    package = dict(result.package)
    automatic_layout_repairs: list[str] = []
    try:
        layout_overflows = _probe_generated_package_overflows(package)
    except F6TemplateReviewStop as exc:
        return _draft_unavailable_payload(
            context=context,
            result=result,
            codex_requests=codex_requests,
            final_url=final_url,
            fetched_title=fetched_title,
            evidence_mode=evidence_mode,
            job_detail_http_gets=job_detail_http_gets,
            reason_code="f6_template_preflight_unavailable",
            reason=str(exc),
        )

    package, deterministic_repairs = _apply_deterministic_layout_repairs(
        package,
        layout_overflows=layout_overflows,
        context=context,
    )
    automatic_layout_repairs.extend(deterministic_repairs)
    if deterministic_repairs:
        try:
            layout_overflows = _probe_generated_package_overflows(package)
        except F6TemplateReviewStop as exc:
            return _draft_unavailable_payload(
                context=context,
                result=result,
                codex_requests=codex_requests,
                final_url=final_url,
                fetched_title=fetched_title,
                evidence_mode=evidence_mode,
                job_detail_http_gets=job_detail_http_gets,
                reason_code="f6_template_preflight_unavailable",
                reason=str(exc),
                automatic_layout_repairs=tuple(automatic_layout_repairs),
            )

    unsupported = _unsupported_layout_overflows(layout_overflows)
    if unsupported:
        return _draft_unavailable_payload(
            context=context,
            result=result,
            codex_requests=codex_requests,
            final_url=final_url,
            fetched_title=fetched_title,
            evidence_mode=evidence_mode,
            job_detail_http_gets=job_detail_http_gets,
            reason_code="f6_template_fit_policy_missing",
            reason=(
                "Exact F6 preflight found an overflowing JAP-owned template zone "
                "without an automatic safe compaction policy."
            ),
            layout_overflows=unsupported,
            automatic_layout_repairs=tuple(automatic_layout_repairs),
        )

    layout_overflows = _codex_repairable_overflows(layout_overflows)
    while layout_overflows and codex_requests < _MAX_CODEX_LAYOUT_ATTEMPTS:
        result = request_codex_application_adaptation(
            context=context,
            layout_feedback=layout_overflows,
            previous_package=package,
        )
        codex_requests += int(result.attempted)
        if result.package is None:
            return _draft_unavailable_payload(
                context=context,
                result=result,
                codex_requests=codex_requests,
                final_url=final_url,
                fetched_title=fetched_title,
                evidence_mode=evidence_mode,
                job_detail_http_gets=job_detail_http_gets,
                layout_overflows=layout_overflows,
                automatic_layout_repairs=tuple(automatic_layout_repairs),
            )
        package = dict(result.package)
        try:
            layout_overflows = _probe_generated_package_overflows(package)
        except F6TemplateReviewStop as exc:
            return _draft_unavailable_payload(
                context=context,
                result=result,
                codex_requests=codex_requests,
                final_url=final_url,
                fetched_title=fetched_title,
                evidence_mode=evidence_mode,
                job_detail_http_gets=job_detail_http_gets,
                reason_code="f6_template_preflight_unavailable",
                reason=str(exc),
                automatic_layout_repairs=tuple(automatic_layout_repairs),
            )

        package, deterministic_repairs = _apply_deterministic_layout_repairs(
            package,
            layout_overflows=layout_overflows,
            context=context,
        )
        automatic_layout_repairs.extend(deterministic_repairs)
        if deterministic_repairs:
            try:
                layout_overflows = _probe_generated_package_overflows(package)
            except F6TemplateReviewStop as exc:
                return _draft_unavailable_payload(
                    context=context,
                    result=result,
                    codex_requests=codex_requests,
                    final_url=final_url,
                    fetched_title=fetched_title,
                    evidence_mode=evidence_mode,
                    job_detail_http_gets=job_detail_http_gets,
                    reason_code="f6_template_preflight_unavailable",
                    reason=str(exc),
                    automatic_layout_repairs=tuple(automatic_layout_repairs),
                )

        unsupported = _unsupported_layout_overflows(layout_overflows)
        if unsupported:
            return _draft_unavailable_payload(
                context=context,
                result=result,
                codex_requests=codex_requests,
                final_url=final_url,
                fetched_title=fetched_title,
                evidence_mode=evidence_mode,
                job_detail_http_gets=job_detail_http_gets,
                reason_code="f6_template_fit_policy_missing",
                reason=(
                    "Exact F6 preflight found an overflowing JAP-owned template zone "
                    "without an automatic safe compaction policy."
                ),
                layout_overflows=unsupported,
                automatic_layout_repairs=tuple(automatic_layout_repairs),
            )
        layout_overflows = _codex_repairable_overflows(layout_overflows)

    if layout_overflows:
        return _draft_unavailable_payload(
            context=context,
            result=result,
            codex_requests=codex_requests,
            final_url=final_url,
            fetched_title=fetched_title,
            evidence_mode=evidence_mode,
            job_detail_http_gets=job_detail_http_gets,
            reason_code="f6_template_fit_unresolved",
            reason=(
                "Codex could not produce review text that fits every frozen F6 "
                "template zone after bounded automatic repair attempts."
            ),
            layout_overflows=layout_overflows,
            automatic_layout_repairs=tuple(automatic_layout_repairs),
        )
    package["source_manifest_sha256"] = _source_manifest_sha256(context)
    package["candidate_fact_keys_used"] = sorted(
        entry.fact_key for entry in context.claim_plan
    )

    return {
        "schema": "job_application_pipeline.product_v1_application_draft_demo.v2",
        "status": "draft_for_review",
        "draft_mode": "codex_embedded_v1",
        "fallback_reason": None,
        "fallback_generated": False,
        "quality_contract": "f6_template_authority_v1",
        "codex_adaptation_contract": "f6_codex_adaptation_v1",
        "layout_policy": "preserve_exact_template_layout_modify_text_zones_only",
        "codex_model": result.model,
        "codex_reasoning_effort": getattr(result, "reasoning_effort", None),
        "codex_version": result.codex_version,
        "codex_requests": codex_requests,
        "provider_requests": codex_requests,
        "llm_requests": codex_requests,
        "layout_fit_status": "exact_template_preflight_pass",
        "layout_repair_attempts": max(0, codex_requests - 1),
        "layout_overflows": [],
        "automatic_layout_repairs": automatic_layout_repairs,
        "base_cv_text_shared_with_codex": True,
        "base_application_letter_text_shared_with_codex": True,
        "vacancy_text_shared_with_codex": True,
        "codex_source_authority": {
            "vacancy": "current_target_fact_authority",
            "candidate_facts": "approved_fact_authority",
            "cv": "candidate_fact_and_style_reference",
            "application_letter": "style_structure_quality_reference_only",
        },
        "render_status": "exact_template_preflight_pass_review_export_available",
        "legacy_generic_document_export": False,
        "package": package,
        "live_job_evidence": {
            "final_url": final_url,
            "fetched_title": fetched_title,
            "detail_sha256": context.target.detail_sha256,
            "evidence_mode": evidence_mode,
        },
        "job_detail_http_gets": job_detail_http_gets,
        "current_observation_detail_reuse": int(
            evidence_mode == "exact_persisted_observation"
        ),
        "database_writes": 0,
        "application_writes": 0,
        "submission_writes": 0,
        "send_actions": 0,
        "draft_approval_authority": False,
        "application_authority": False,
        "submission_authority": False,
        "send_authority": False,
    }


__all__ = ["application_workspace_payload", "generate_application_draft_payload"]
