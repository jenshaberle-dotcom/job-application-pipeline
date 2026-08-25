"""Pure bounded policy for visible runtime listing interactions.

The browser adapter remains outside this module. Callers provide only already-visible,
non-secret control metadata from an already-authorized public career/listing page.
The policy may select one next generic interaction at a time; it performs no browser,
network, provider, database, Product, lifecycle, source, ranking, or application
mutation.

Interaction authority is deliberately weaker than acquisition authority. Clicking a
visible control may reveal new runtime evidence, but it never authorizes a host,
source, job record, or Product outcome by itself. Newly observed structured responses
must still pass ACQ-RUNTIME-001 recognition and runtime job-record proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlparse

from src.search_intelligence.runtime_network_acquisition import sanitize_url

_ALLOWED_ROLES = {"a", "button", "link"}

_JOB_CONTEXT_TERMS = {
    "career",
    "careers",
    "job",
    "jobs",
    "opening",
    "openings",
    "position",
    "positions",
    "requisition",
    "requisitions",
    "vacancy",
    "vacancies",
}

_OPEN_JOBS_PHRASES = {
    "all jobs",
    "browse jobs",
    "find jobs",
    "job openings",
    "jobs",
    "open jobs",
    "open positions",
    "search jobs",
    "see jobs",
    "view jobs",
    "vacancies",
}

_LOAD_MORE_PHRASES = {
    "load more jobs",
    "more jobs",
    "more positions",
    "show more jobs",
    "show more positions",
    "view more jobs",
    "view more positions",
}

_GENERIC_LOAD_MORE_PHRASES = {"load more", "show more", "view more"}
_NEXT_PHRASES = {"next", "next jobs", "next page", "next positions"}

_REJECT_PHRASES = {
    "apply",
    "apply now",
    "contact",
    "cookie settings",
    "filter",
    "log in",
    "login",
    "newsletter",
    "privacy",
    "register",
    "sign in",
    "sign up",
    "sort",
    "submit",
    "terms",
    "upload",
}


@dataclass(frozen=True)
class VisibleListingControl:
    """Sanitized visible-control metadata; no selector or DOM snapshot is retained."""

    role: str
    text: str
    aria_label: str = ""
    href: str = ""
    context_text: str = ""
    visible: bool = True
    enabled: bool = True


@dataclass(frozen=True)
class InteractionBudget:
    """Hard per-page interaction cap for one bounded runtime observation case."""

    max_total_actions: int = 3
    max_click_actions: int = 2
    max_scroll_actions: int = 1


@dataclass(frozen=True)
class InteractionProgress:
    """Previously attempted actions for the current page/case."""

    total_actions: int = 0
    click_actions: int = 0
    scroll_actions: int = 0
    attempted_control_fingerprints: tuple[str, ...] = ()


@dataclass(frozen=True)
class InteractionDecision:
    """One next action or a fail-closed/no-action outcome."""

    action: str
    reason_code: str
    control_fingerprint: str = ""
    control_kind: str = ""
    no_product_authority: bool = True


def _normalized_phrase(value: object) -> str:
    return " ".join(str(value or "").casefold().replace("_", " ").replace("-", " ").split())


def _contains_job_context(value: str) -> bool:
    normalized = _normalized_phrase(value)
    tokens = set(normalized.replace("/", " ").split())
    return bool(tokens & _JOB_CONTEXT_TERMS)


def _safe_href(value: str) -> str:
    href = str(value or "").strip()
    if not href:
        return ""
    parsed = urlparse(href)
    if parsed.scheme and parsed.scheme.casefold() != "https":
        return ""
    return sanitize_url(href)


def control_fingerprint(control: VisibleListingControl) -> str:
    """Return a stable fingerprint without persisting selectors or secret query values."""

    safe_href = _safe_href(control.href)
    material = "\n".join(
        (
            _normalized_phrase(control.role),
            _normalized_phrase(control.text),
            _normalized_phrase(control.aria_label),
            _normalized_phrase(control.context_text),
            safe_href,
        )
    )
    return sha256(material.encode("utf-8")).hexdigest()


def _control_label(control: VisibleListingControl) -> str:
    return _normalized_phrase(control.aria_label or control.text)


def _rejected_control(control: VisibleListingControl) -> bool:
    if not control.visible or not control.enabled:
        return True
    if _normalized_phrase(control.role) not in _ALLOWED_ROLES:
        return True
    if control.href and not _safe_href(control.href):
        return True

    label = _control_label(control)
    if not label:
        return True
    if label in _REJECT_PHRASES:
        return True
    return any(label.startswith(f"{phrase} ") for phrase in _REJECT_PHRASES)


def _classify_control(
    control: VisibleListingControl,
    *,
    page_url: str,
) -> tuple[str, int] | None:
    if _rejected_control(control):
        return None

    label = _control_label(control)
    context_has_jobs = _contains_job_context(control.context_text) or _contains_job_context(
        urlparse(page_url).path
    )

    if label in _LOAD_MORE_PHRASES:
        return "load_more", 300
    if label in _GENERIC_LOAD_MORE_PHRASES and context_has_jobs:
        return "load_more", 290
    if label in _NEXT_PHRASES and (label != "next" or context_has_jobs):
        return "next_page", 250
    if label in _OPEN_JOBS_PHRASES:
        return "open_jobs", 200
    return None


def _validate_budget(budget: InteractionBudget) -> None:
    if budget.max_total_actions < 1:
        raise ValueError("max_total_actions must be >= 1")
    if budget.max_click_actions < 0 or budget.max_scroll_actions < 0:
        raise ValueError("interaction sub-budgets must be >= 0")
    if budget.max_click_actions + budget.max_scroll_actions < budget.max_total_actions:
        raise ValueError("sub-budgets cannot be smaller than max_total_actions")


def _valid_progress(progress: InteractionProgress) -> bool:
    if min(progress.total_actions, progress.click_actions, progress.scroll_actions) < 0:
        return False
    if progress.click_actions + progress.scroll_actions != progress.total_actions:
        return False
    return len(set(progress.attempted_control_fingerprints)) == len(
        progress.attempted_control_fingerprints
    )


def select_next_listing_interaction(
    *,
    page_authorized: bool,
    page_url: str,
    controls: tuple[VisibleListingControl, ...],
    progress: InteractionProgress = InteractionProgress(),
    budget: InteractionBudget = InteractionBudget(),
) -> InteractionDecision:
    """Select one bounded generic listing interaction from fresh visible controls.

    The caller should re-scan visible controls after every selected action and call
    this function again with updated progress. This permits a bounded multi-step
    sequence without planning clicks against stale DOM state.
    """

    _validate_budget(budget)
    if not _valid_progress(progress):
        return InteractionDecision(action="stop", reason_code="invalid_interaction_progress")
    if not page_authorized:
        return InteractionDecision(action="stop", reason_code="page_not_authorized")
    if progress.total_actions >= budget.max_total_actions:
        return InteractionDecision(action="stop", reason_code="interaction_budget_exhausted")

    attempted = set(progress.attempted_control_fingerprints)
    eligible: list[tuple[int, str, str]] = []
    if progress.click_actions < budget.max_click_actions:
        for control in controls:
            classification = _classify_control(control, page_url=page_url)
            if classification is None:
                continue
            control_kind, priority = classification
            fingerprint = control_fingerprint(control)
            if fingerprint in attempted:
                continue
            eligible.append((priority, fingerprint, control_kind))

    if eligible:
        priority, fingerprint, control_kind = sorted(
            eligible,
            key=lambda item: (-item[0], item[1], item[2]),
        )[0]
        del priority
        return InteractionDecision(
            action="click",
            reason_code=f"visible_{control_kind}_control",
            control_fingerprint=fingerprint,
            control_kind=control_kind,
        )

    if progress.scroll_actions < budget.max_scroll_actions:
        return InteractionDecision(
            action="scroll",
            reason_code="bounded_listing_scroll_probe",
            control_kind="scroll",
        )

    return InteractionDecision(action="stop", reason_code="no_eligible_visible_listing_interaction")
