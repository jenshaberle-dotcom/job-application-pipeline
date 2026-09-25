"""Embedded Codex drafting adapter for JAP Classic F6.

Codex is deliberately used for one bounded product responsibility only:
adapt the approved CV profile/competency text and the application-letter text
to the exact selected vacancy. It receives no repository task and no mutation
authority. The CLI runs in a temporary read-only workspace and must return a
strict JSON-schema result.

ChatGPT-authenticated Codex consumes the account's included Codex allowance
first and, when enabled/available for the account, purchased credits after it.
JAP does not buy credits, change account settings, or silently switch to an API
key. If Codex capacity is unavailable, drafting stops visibly instead of
falling back to low-quality deterministic prose.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Mapping

from src.search_intelligence.product_v1_application_context import (
    ProductV1ApplicationContext,
)


DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_TIMEOUT_SECONDS = 180.0
MAX_VACANCY_CHARS = 16_000
MAX_CV_CHARS = 18_000
MAX_LETTER_CHARS = 14_000

# Frozen F6 layout budgets. These are content limits, not layout authority:
# Codex must stay inside the already-approved text zones and the renderer remains
# the final exact-fit/pixel-identity gate.
CV_SHORT_PROFILE_MAX_CHARS = 520
CV_COMPETENCY_PROFILE_MAX_CHARS = 180
LETTER_PARAGRAPH_MIN_COUNT = 4
LETTER_PARAGRAPH_MAX_COUNT = 6
LETTER_PARAGRAPH_MAX_CHARS = 520
CAPACITY_PATTERNS = (
    "usage limit",
    "usage_limit",
    "rate limit",
    "rate_limit",
    "quota",
    "credit balance",
    "credits exhausted",
    "credit_balance_exhausted",
    "insufficient credit",
    "allowance",
    "limit reached",
    "weekly limit",
    "5-hour",
    "five-hour",
    "too many requests",
)
AUTH_PATTERNS = (
    "not logged in",
    "login required",
    "sign in",
    "authentication",
    "unauthorized",
    "invalid credentials",
)

SAFE_ENV_KEYS = (
    "HOME",
    "USER",
    "LOGNAME",
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "NO_PROXY",
    "ALL_PROXY",
    "CODEX_HOME",
)

SYSTEM_TASK = """You are the embedded high-quality application drafting engine inside a local
job-application product. This is a quality-first workflow, not a high-volume generator.

Your ONLY task is to adapt the candidate's current CV and current application letter to the supplied
exact vacancy while obeying JAP's authority boundaries.

SOURCE AUTHORITY
- CURRENT VACANCY is the sole authority for the target employer, target role, requirements, named
  contacts and current application context.
- APPROVED CANDIDATE FACTS and CURRENT CV are factual candidate authority.
- CURRENT APPLICATION LETTER is a style, tone, structure and writing-quality reference. Its old
  employer, recipient, role, date, salutation and vacancy-specific claims are STALE and have zero
  factual authority for the new application.
- Never invent a contact person, address, qualification, employer, duration, metric, skill or
  professional experience.

EDIT AUTHORITY
- PIXEL-FROZEN: page geometry, graphics, portrait, signature image, lines, colors, non-editable
  typography regions and every pixel outside declared editable text zones. You have no authority
  to move, resize, add, delete or redesign them.
- JAP-DETERMINISTIC: recipient block, application date, subject and final metadata replacement.
  Do not try to position or overlay these fields; JAP replaces the existing source text in-place.
- SEMANTICALLY ADAPTABLE: CV short profile, CV competency profile, salutation and descriptive
  application-letter body paragraphs. These may be rewritten substantially when needed for a
  strong vacancy-specific application, but facts must remain grounded.
- PRESERVE-BY-DEFAULT: career history, education, projects, skills lists and other source content.
  Do not rewrite them merely for stylistic variation unless JAP explicitly exposes such a zone.

QUALITY BAR
- Match the current letter's professionalism, density and narrative coherence while writing a
  genuinely vacancy-specific new letter.
- Build a clear argument: why this role -> relevant proven experience -> current relevant practice
  -> value for this employer -> concise motivation/close.
- Prefer concrete evidence over generic self-description. Do not copy requirement lists or stuff
  keywords.
- Do not frame the candidate primarily as a learner when the same evidence supports an experienced
  engineering-transfer narrative.
- Every paragraph must be a complete, grammatically finished thought. No truncated phrases,
  malformed word joins, duplicated fragments or sentence debris.
- Preserve personalization when the vacancy names a contact and the exact template can fit it.
- Use the current CV and letter as reference material before drafting. Internally review the complete
  result for factual grounding, language quality, stale identities and coherence before returning it.

LAYOUT / FIT
- The CV short profile must be concise and targeted. Hard limit: 520 characters.
- The competency profile is a compact frozen side-panel. Hard limit: 180 characters total. Prefer
  4-6 short capability groups separated by " · ".
- Return between 4 and 6 coherent application-letter paragraphs. Each paragraph may use up to
  520 characters; JAP's exact renderer is the final physical-fit authority.
- Never solve fit by requesting smaller fonts, scaling, extra pages, moved zones or layout changes.
- When renderer feedback is supplied, rewrite only the named semantic zones and make them materially
  shorter while preserving the argument and facts.
- If renderer_compaction_targets are supplied, each hard_target_max_chars value is mandatory.
- JAP repairs deterministic metadata zones itself. Never alter facts merely to fit.

LANGUAGE / OUTPUT
- Prefer German when the vacancy is German or mixed German/English. Use English only when clearly
  appropriate.
- Return only the schema-constrained result. Human review remains mandatory. No application is ever
  submitted or sent by this task.
"""


class CodexApplicationDraftStop(ValueError):
    """Fail closed when an embedded Codex result cannot be trusted."""


@dataclass(frozen=True)
class CodexRuntimeStatus:
    status: str
    installed: bool
    chatgpt_authenticated: bool
    auth_mode: str
    executable: str | None
    version: str | None
    model: str
    reasoning_effort: str

    def to_json(self) -> dict[str, object]:
        return {
            "status": self.status,
            "installed": self.installed,
            "chatgpt_authenticated": self.chatgpt_authenticated,
            "auth_mode": self.auth_mode,
            "executable": self.executable,
            "version": self.version,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "billing_authority": "chatgpt_included_allowance_then_eligible_credits",
            "api_key_fallback": False,
            "automatic_credit_purchase": False,
        }


@dataclass(frozen=True)
class CodexApplicationDraftResult:
    status: str
    attempted: bool
    model: str
    reasoning_effort: str
    reason_code: str | None
    reason: str | None
    package: dict[str, object] | None
    codex_version: str | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "status": self.status,
            "attempted": self.attempted,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "package": self.package,
            "codex_version": self.codex_version,
        }


def _schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status",
            "language",
            "contact_name",
            "salutation",
            "cv_short_profile",
            "cv_competency_profile",
            "letter_paragraphs",
            "rationale",
        ],
        "properties": {
            "status": {"type": "string", "enum": ["draft_for_review"]},
            "language": {"type": "string", "enum": ["de", "en"]},
            "contact_name": {"type": "string", "maxLength": 120},
            "salutation": {"type": "string", "minLength": 2, "maxLength": 220},
            "cv_short_profile": {
                "type": "string",
                "minLength": 40,
                "maxLength": CV_SHORT_PROFILE_MAX_CHARS,
            },
            "cv_competency_profile": {
                "type": "string",
                "minLength": 20,
                "maxLength": CV_COMPETENCY_PROFILE_MAX_CHARS,
            },
            "letter_paragraphs": {
                "type": "array",
                "minItems": LETTER_PARAGRAPH_MIN_COUNT,
                "maxItems": LETTER_PARAGRAPH_MAX_COUNT,
                "items": {
                    "type": "string",
                    "minLength": 20,
                    "maxLength": LETTER_PARAGRAPH_MAX_CHARS,
                },
            },
            "rationale": {"type": "string", "maxLength": 600},
        },
    }


def _source_document_text(
    context: ProductV1ApplicationContext,
    *,
    document_type: str,
    max_chars: int,
) -> str:
    for document in context.source_documents:
        if document.document_type == document_type:
            text = str(document.content or "").strip()
            if text:
                return text[:max_chars]
    raise CodexApplicationDraftStop(
        f"approved {document_type} text is unavailable"
    )


def _base_cv_text(context: ProductV1ApplicationContext) -> str:
    return _source_document_text(
        context,
        document_type="base_cv",
        max_chars=MAX_CV_CHARS,
    )


def _base_application_letter_text(context: ProductV1ApplicationContext) -> str:
    return _source_document_text(
        context,
        document_type="base_application_letter",
        max_chars=MAX_LETTER_CHARS,
    )


def _prompt(
    context: ProductV1ApplicationContext,
    *,
    layout_feedback: tuple[str, ...] = (),
    previous_package: Mapping[str, object] | None = None,
) -> str:
    facts = [
        {
            "fact_key": item.fact_key,
            "statement": item.statement,
            "limitations": list(item.limitations),
        }
        for item in context.approved_candidate_facts
        if item.approval_status == "approved"
    ]
    packet = {
        "task": "adapt_cv_and_application_letter_only",
        "target": {
            "title": context.target.title,
            "company_name": context.target.company_name,
            "source_url": context.target.source_url,
            "vacancy_text": context.target.detail_text[:MAX_VACANCY_CHARS],
        },
        "approved_candidate_facts": facts,
        "current_documents": {
            "cv": {
                "content": _base_cv_text(context),
                "authority": "candidate_fact_and_style_reference",
                "layout_policy": "pixel_frozen_except_declared_semantic_text_zones",
            },
            "application_letter": {
                "content": _base_application_letter_text(context),
                "authority": "style_structure_quality_reference_only",
                "stale_fields": [
                    "employer",
                    "recipient",
                    "job_title",
                    "date",
                    "salutation",
                    "vacancy_specific_claims",
                ],
                "layout_policy": "pixel_frozen_except_declared_semantic_text_zones",
            },
        },
        "output_notes": {
            "recipient_block_is_built_deterministically_by_JAP": True,
            "subject_and_date_are_built_deterministically_by_JAP": True,
            "current_application_letter_is_style_reference_not_fact_authority": True,
            "current_cv_and_letter_and_vacancy_are_shared_with_codex": True,
            "human_review_required": True,
            "frozen_layout_text_budgets": {
                "cv_short_profile_max_chars": CV_SHORT_PROFILE_MAX_CHARS,
                "cv_competency_profile_max_chars": CV_COMPETENCY_PROFILE_MAX_CHARS,
                "letter_paragraph_min_count": LETTER_PARAGRAPH_MIN_COUNT,
                "letter_paragraph_max_count": LETTER_PARAGRAPH_MAX_COUNT,
                "letter_paragraph_max_chars": LETTER_PARAGRAPH_MAX_CHARS,
            },
            "renderer_feedback": list(layout_feedback),
            "renderer_feedback_policy": (
                "previous draft overflowed these exact frozen zones; compact them"
                if layout_feedback
                else "no exact-template overflow observed yet"
            ),
        },
    }
    if layout_feedback and previous_package:
        preview = previous_package.get("preview")
        if isinstance(preview, Mapping):
            packet["previous_review_draft"] = {
                "cv_short_profile": str(preview.get("cv_short_profile") or ""),
                "cv_competency_profile": str(
                    preview.get("cv_competency_profile") or ""
                ),
                "application_letter": str(preview.get("application_letter") or ""),
            }
        replacements = previous_package.get("zone_replacements")
        if isinstance(replacements, Mapping):
            failing_values: dict[str, str] = {}
            compaction_targets: dict[str, dict[str, int]] = {}
            for qualified_zone in layout_feedback:
                document_type, separator, zone_id = qualified_zone.partition(":")
                if not separator:
                    continue
                document = replacements.get(document_type)
                if not isinstance(document, Mapping):
                    continue
                value = str(document.get(zone_id) or "")
                failing_values[qualified_zone] = value
                minimum = (
                    40
                    if qualified_zone == "base_cv:p1.short_profile"
                    else 20
                    if qualified_zone == "base_cv:p1.competency_profile"
                    or ":body.paragraph_" in qualified_zone
                    else 2
                )
                target = max(minimum, int(len(value) * 0.65))
                compaction_targets[qualified_zone] = {
                    "previous_chars": len(value),
                    "hard_target_max_chars": target,
                }
            packet["previous_overflowing_zone_values"] = failing_values
            packet["renderer_compaction_targets"] = compaction_targets
    return SYSTEM_TASK + "\n\nINPUT PACKET:\n" + json.dumps(
        packet, ensure_ascii=False, sort_keys=True
    )


def _resolve_codex() -> str | None:
    override = os.environ.get("JAP_CODEX_EXECUTABLE", "").strip()
    if override:
        return override
    return shutil.which("codex") or shutil.which("codex.exe")


def _codex_environment() -> dict[str, str]:
    """Expose only the OS/auth context Codex needs; never inherit JAP secrets."""

    environment = {
        key: value
        for key in SAFE_ENV_KEYS
        if (value := os.environ.get(key))
    }
    environment["JAP_CODEX_EMBEDDED"] = "1"
    return environment


def _codex_version(executable: str) -> str | None:
    try:
        result = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env=_codex_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = " ".join((result.stdout or result.stderr or "").split())
    return text[:160] or None


def _codex_login_status(executable: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [executable, "login", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env=_codex_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = "\n".join((result.stdout or "", result.stderr or "")).strip()
    # JAP intentionally accepts only ChatGPT-backed Codex auth here. A stored API-key
    # login would move drafting onto API billing and violate the operator's requested
    # included-allowance / eligible-credit boundary.
    return (
        result.returncode == 0
        and "logged in using chatgpt" in output.casefold(),
        output,
    )


def inspect_codex_runtime_status(
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> CodexRuntimeStatus:
    selected_model = (
        model or os.environ.get("JAP_CODEX_DRAFT_MODEL") or DEFAULT_MODEL
    ).strip()
    selected_reasoning_effort = (
        reasoning_effort
        or os.environ.get("JAP_CODEX_REASONING_EFFORT")
        or DEFAULT_REASONING_EFFORT
    ).strip()
    executable = _resolve_codex()
    if not executable:
        return CodexRuntimeStatus(
            status="not_installed",
            installed=False,
            chatgpt_authenticated=False,
            auth_mode="none",
            executable=None,
            version=None,
            model=selected_model,
            reasoning_effort=selected_reasoning_effort,
        )

    version = _codex_version(executable)
    logged_in, login_output = _codex_login_status(executable)
    folded = login_output.casefold()
    auth_mode = (
        "chatgpt"
        if logged_in
        else "api_key"
        if "logged in using an api key" in folded
        else "workload_identity"
        if "logged in using workload identity" in folded
        else "access_token"
        if "logged in using access token" in folded
        else "none"
    )
    return CodexRuntimeStatus(
        status="ready" if logged_in else "auth_required",
        installed=True,
        chatgpt_authenticated=logged_in,
        auth_mode=auth_mode,
        executable=executable,
        version=version,
        model=selected_model,
        reasoning_effort=selected_reasoning_effort,
    )


def _safe_error(text: str) -> str:
    compact = " ".join(text.split())
    compact = re.sub(r"(?i)(bearer|token|api[_ -]?key)\s*[:=]?\s*\S+", r"\1 ***", compact)
    return compact[:600]


def _classify_failure(text: str) -> tuple[str, str]:
    folded = text.casefold()
    if any(pattern in folded for pattern in CAPACITY_PATTERNS):
        return (
            "codex_capacity_unavailable",
            "Codex usage capacity is unavailable. Retry after the included allowance resets "
            "or after usable Codex credits are available.",
        )
    if any(pattern in folded for pattern in AUTH_PATTERNS):
        return (
            "codex_auth_required",
            "Codex is installed but not authenticated for this runtime. Sign in to Codex with "
            "the ChatGPT account used for the included allowance/credits.",
        )
    return ("codex_execution_failed", _safe_error(text) or "Codex drafting failed closed.")


def _normalized(value: object) -> str:
    return " ".join(str(value or "").split())


def _validate_output(
    decoded: Mapping[str, object],
    *,
    context: ProductV1ApplicationContext,
    as_of_date: date,
) -> dict[str, object]:
    expected = {
        "status",
        "language",
        "contact_name",
        "salutation",
        "cv_short_profile",
        "cv_competency_profile",
        "letter_paragraphs",
        "rationale",
    }
    if set(decoded) != expected or decoded.get("status") != "draft_for_review":
        raise CodexApplicationDraftStop("Codex draft root does not match the F6 schema")

    language = _normalized(decoded.get("language"))
    contact_name = _normalized(decoded.get("contact_name"))
    salutation = _normalized(decoded.get("salutation"))
    cv_short = _normalized(decoded.get("cv_short_profile"))
    cv_competency = str(decoded.get("cv_competency_profile") or "").strip()
    rationale = _normalized(decoded.get("rationale"))
    raw_paragraphs = decoded.get("letter_paragraphs")
    if language not in {"de", "en"}:
        raise CodexApplicationDraftStop("Codex returned an unsupported application language")
    if (
        not isinstance(raw_paragraphs, list)
        or not LETTER_PARAGRAPH_MIN_COUNT
        <= len(raw_paragraphs)
        <= LETTER_PARAGRAPH_MAX_COUNT
    ):
        raise CodexApplicationDraftStop(
            "Codex letter paragraph count is outside the F6 quality range "
            f"{LETTER_PARAGRAPH_MIN_COUNT}-{LETTER_PARAGRAPH_MAX_COUNT}"
        )
    paragraphs = tuple(_normalized(item) for item in raw_paragraphs)
    if any(len(item) < 20 for item in paragraphs):
        raise CodexApplicationDraftStop("Codex returned an empty/undersized letter paragraph")
    if any(len(item) > LETTER_PARAGRAPH_MAX_CHARS for item in paragraphs):
        raise CodexApplicationDraftStop(
            "Codex letter paragraph exceeds the frozen F6 text budget"
        )
    if any(item[-1] not in ".!?;:" for item in paragraphs):
        raise CodexApplicationDraftStop(
            "Codex returned an unfinished application-letter paragraph"
        )

    detail_folded = context.target.detail_text.casefold()
    if contact_name and contact_name.casefold() not in detail_folded:
        raise CodexApplicationDraftStop("Codex invented a contact person not present in vacancy evidence")
    if not contact_name:
        allowed_generic = {
            "de": ("sehr geehrte damen und herren", "guten tag"),
            "en": ("dear hiring team", "dear recruitment team", "dear sir or madam"),
        }[language]
        if not any(salutation.casefold().startswith(item) for item in allowed_generic):
            raise CodexApplicationDraftStop("Codex used a non-grounded personal salutation")

    combined_letter = " ".join(paragraphs).casefold()
    if (
        context.target.company_name.casefold() not in combined_letter
        and context.target.title.casefold() not in combined_letter
    ):
        raise CodexApplicationDraftStop("Codex letter is not specific to the selected target")
    if len(cv_short) < 40 or len(cv_competency) < 20:
        raise CodexApplicationDraftStop("Codex CV adaptation is incomplete")
    if len(cv_short) > CV_SHORT_PROFILE_MAX_CHARS:
        raise CodexApplicationDraftStop(
            "Codex CV short profile exceeds the frozen F6 text budget"
        )
    if len(cv_competency) > CV_COMPETENCY_PROFILE_MAX_CHARS:
        raise CodexApplicationDraftStop(
            "Codex CV competency profile exceeds the frozen F6 text budget"
        )

    recipient = context.target.company_name
    if contact_name:
        recipient += f"\nz. Hd. {contact_name}" if language == "de" else f"\nAttn. {contact_name}"
    subject = (
        f"Bewerbung als {context.target.title}"
        if language == "de"
        else f"Application for {context.target.title}"
    )
    current_date = (
        as_of_date.strftime("%d.%m.%Y")
        if language == "de"
        else as_of_date.isoformat()
    )
    closing = "Mit freundlichen Grüßen" if language == "de" else "Kind regards"
    cv_footer_date = (
        f"Hannover, {as_of_date.day}. "
        + (
            (
                "Januar Februar März April Mai Juni Juli August September "
                "Oktober November Dezember"
            ).split()[as_of_date.month - 1]
            if language == "de"
            else as_of_date.strftime("%B")
        )
        + f" {as_of_date.year}"
    )

    letter_zones: dict[str, str] = {
        "recipient.block": recipient,
        "date": current_date,
        "subject": subject,
        "salutation": salutation,
        "closing.formula": closing,
    }
    for index in range(1, 7):
        letter_zones[f"body.paragraph_{index}"] = (
            paragraphs[index - 1] if index <= len(paragraphs) else ""
        )

    return {
        "status": "draft_for_review",
        "language": language,
        "rationale": rationale,
        "contact_name": contact_name,
        "preview": {
            "cv_short_profile": cv_short,
            "cv_competency_profile": cv_competency,
            "application_letter": "\n\n".join((salutation, *paragraphs, closing)),
        },
        "zone_replacements": {
            "base_cv": {
                "p1.short_profile": cv_short,
                "p1.competency_profile": cv_competency,
                "p2.footer.date": cv_footer_date,
            },
            "base_application_letter": letter_zones,
        },
        "draft_approval_authority": False,
        "application_authority": False,
        "submission_authority": False,
        "send_authority": False,
    }


def request_codex_application_adaptation(
    *,
    context: ProductV1ApplicationContext,
    as_of_date: date | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    layout_feedback: tuple[str, ...] = (),
    previous_package: Mapping[str, object] | None = None,
) -> CodexApplicationDraftResult:
    selected_model = (model or os.environ.get("JAP_CODEX_DRAFT_MODEL") or DEFAULT_MODEL).strip()
    selected_reasoning_effort = (
        reasoning_effort
        or os.environ.get("JAP_CODEX_REASONING_EFFORT")
        or DEFAULT_REASONING_EFFORT
    ).strip()
    if selected_reasoning_effort not in {"low", "medium", "high", "xhigh"}:
        return CodexApplicationDraftResult(
            status="failed_closed",
            attempted=False,
            model=selected_model,
            reasoning_effort=selected_reasoning_effort,
            reason_code="codex_reasoning_effort_invalid",
            reason="JAP Codex reasoning effort must be low, medium, high or xhigh.",
            package=None,
        )
    executable = _resolve_codex()
    if not executable:
        return CodexApplicationDraftResult(
            status="unavailable",
            attempted=False,
            model=selected_model,
            reasoning_effort=selected_reasoning_effort,
            reason_code="codex_not_installed",
            reason="Codex CLI is not available to the JAP runtime.",
            package=None,
        )
    version = _codex_version(executable)
    logged_in, login_output = _codex_login_status(executable)
    if not logged_in:
        folded_login = login_output.casefold()
        wrong_auth_mode = any(
            marker in folded_login
            for marker in (
                "logged in using an api key",
                "logged in using workload identity",
                "logged in using access token",
            )
        )
        return CodexApplicationDraftResult(
            status="unavailable",
            attempted=False,
            model=selected_model,
            reasoning_effort=selected_reasoning_effort,
            reason_code=(
                "codex_chatgpt_auth_required"
                if wrong_auth_mode
                else "codex_auth_required"
            ),
            reason=(
                "Bundled Codex is available, but JAP requires ChatGPT-backed Codex "
                "authentication so drafting uses the included allowance / eligible "
                "Codex credits rather than API billing. Sign in to Codex with ChatGPT "
                "for this WSL user, then retry drafting."
            ),
            package=None,
            codex_version=version,
        )

    try:
        prompt = _prompt(
            context,
            layout_feedback=layout_feedback,
            previous_package=previous_package,
        )
    except CodexApplicationDraftStop as exc:
        return CodexApplicationDraftResult(
            status="failed_closed",
            attempted=False,
            model=selected_model,
            reasoning_effort=selected_reasoning_effort,
            reason_code="candidate_source_unavailable",
            reason=str(exc),
            package=None,
            codex_version=version,
        )

    with tempfile.TemporaryDirectory(prefix="jap-codex-draft-") as tmp:
        root = Path(tmp)
        schema_path = root / "draft.schema.json"
        output_path = root / "draft.json"
        schema_path.write_text(
            json.dumps(_schema(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        command = [
            executable,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--model",
            selected_model,
            "-c",
            f'model_reasoning_effort="{selected_reasoning_effort}"',
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
            prompt,
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=_codex_environment(),
            )
        except subprocess.TimeoutExpired:
            return CodexApplicationDraftResult(
                status="unavailable",
                attempted=True,
                model=selected_model,
                reasoning_effort=selected_reasoning_effort,
                reason_code="codex_timeout",
                reason="Codex drafting timed out. No fallback prose was generated.",
                package=None,
                codex_version=version,
            )
        except OSError as exc:
            return CodexApplicationDraftResult(
                status="unavailable",
                attempted=True,
                model=selected_model,
                reasoning_effort=selected_reasoning_effort,
                reason_code="codex_launch_failed",
                reason=_safe_error(str(exc)),
                package=None,
                codex_version=version,
            )

        if completed.returncode != 0 or not output_path.is_file():
            reason_code, reason = _classify_failure(
                "\n".join((completed.stderr or "", completed.stdout or ""))
            )
            return CodexApplicationDraftResult(
                status="unavailable",
                attempted=True,
                model=selected_model,
                reasoning_effort=selected_reasoning_effort,
                reason_code=reason_code,
                reason=reason,
                package=None,
                codex_version=version,
            )
        try:
            decoded = json.loads(output_path.read_text(encoding="utf-8"))
            if not isinstance(decoded, Mapping):
                raise CodexApplicationDraftStop("Codex output root is not an object")
            package = _validate_output(
                decoded,
                context=context,
                as_of_date=as_of_date or date.today(),
            )
        except (json.JSONDecodeError, CodexApplicationDraftStop) as exc:
            return CodexApplicationDraftResult(
                status="failed_closed",
                attempted=True,
                model=selected_model,
                reasoning_effort=selected_reasoning_effort,
                reason_code="codex_output_validation_failed",
                reason=_safe_error(str(exc)),
                package=None,
                codex_version=version,
            )

    return CodexApplicationDraftResult(
        status="completed",
        attempted=True,
        model=selected_model,
        reasoning_effort=selected_reasoning_effort,
        reason_code=None,
        reason=None,
        package=package,
        codex_version=version,
    )


__all__ = [
    "CodexApplicationDraftResult",
    "CodexApplicationDraftStop",
    "CodexRuntimeStatus",
    "_codex_environment",
    "_codex_login_status",
    "inspect_codex_runtime_status",
    "request_codex_application_adaptation",
]
