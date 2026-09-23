"""Shared deterministic identity helpers for F5 application/job reconciliation.

These helpers are deliberately conservative. They may establish an automatic
identity only when the employer is exact and the role title is exact or a strong
prefix-family match. Short generic role names therefore remain review-only.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit


LEGAL_COMPANY_TOKENS = frozenset(
    {
        "ag",
        "gmbh",
        "mbh",
        "kg",
        "kgaa",
        "se",
        "inc",
        "ltd",
        "llc",
        "co",
        "company",
        "holding",
        "holdings",
    }
)
TITLE_NOISE_TOKENS = frozenset(
    {
        "m",
        "w",
        "d",
        "f",
        "x",
        "all",
        "genders",
        "gender",
        "divers",
        "diverse",
    }
)


VACANCY_REFERENCE_PREFIX = re.compile(
    r"^\s*(?=[A-Za-z0-9/_-]*\d)[A-Za-z0-9]+(?:[/-][A-Za-z0-9]+)*\s*[-–—:]\s*",
    re.IGNORECASE,
)


def _ascii_words(value: object) -> list[str]:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.findall(r"[a-z0-9]+", text)


def normalize_company(value: object) -> str:
    return " ".join(
        token for token in _ascii_words(value) if token not in LEGAL_COMPANY_TOKENS
    )


def normalize_title(value: object) -> str:
    raw = str(value or "").strip()
    # Employer mail and ATS subjects often prepend a vacancy/reference code
    # (for example "E362/B -").  A digit-bearing reference before a clear
    # separator is transport metadata, not role identity.  Strip only that
    # bounded shape; normal title prefixes such as "Senior -" remain intact.
    raw = VACANCY_REFERENCE_PREFIX.sub("", raw, count=1)
    return " ".join(
        token for token in _ascii_words(raw) if token not in TITLE_NOISE_TOKENS
    )


def normalize_url(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw.rstrip("/").casefold()
    if not parts.scheme or not parts.netloc:
        return raw.rstrip("/").casefold()
    host = parts.netloc.casefold()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.casefold(), host, path, parts.query, ""))


def strong_title_family_match(left: object, right: object) -> bool:
    """Return True only for exact or sufficiently specific prefix-family titles.

    Example admitted:
      "AI Automation Architect Software Development Lifecycle"
      ->
      "AI Automation Architect Software Development Lifecycle Germany ..."

    Example intentionally not admitted:
      "Data Engineer" -> "Senior Data Engineer Platform"
    """

    left_norm = normalize_title(left)
    right_norm = normalize_title(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True

    left_tokens = left_norm.split()
    right_tokens = right_norm.split()
    if len(left_tokens) <= len(right_tokens):
        shorter, longer = left_tokens, right_tokens
    else:
        shorter, longer = right_tokens, left_tokens

    if len(shorter) < 3:
        return False
    if len(shorter) / len(longer) < 0.45:
        return False
    return longer[: len(shorter)] == shorter


@dataclass(frozen=True)
class ExistingApplicationIdentity:
    application_key: str
    employer_name: str | None
    job_title: str | None
    source_url: str | None
    counterparty_domain: str | None = None
    thread_reference: str | None = None


def match_existing_application_identity(
    *,
    employer_name: object,
    job_title: object,
    source_url: object,
    applications: list[ExistingApplicationIdentity],
    counterparty_domain: object = None,
    thread_reference: object = None,
) -> tuple[str | None, bool, str | None]:
    """Resolve a unique existing application conservatively.

    Returns (application_key, ambiguous, basis). URL identity wins. Otherwise
    company must be exact after legal-form normalization and the title must pass
    the strong title-family rule. Ambiguity never selects a record.
    """

    url_norm = normalize_url(source_url)
    if url_norm:
        url_matches = [
            item
            for item in applications
            if item.source_url and normalize_url(item.source_url) == url_norm
        ]
        if len(url_matches) == 1:
            return url_matches[0].application_key, False, "exact_source_url"
        if len(url_matches) > 1:
            return None, True, "ambiguous_exact_source_url"

    thread = str(thread_reference or "").strip()
    if thread:
        thread_matches = [
            item for item in applications
            if item.thread_reference and item.thread_reference == thread
        ]
        if len(thread_matches) == 1:
            return thread_matches[0].application_key, False, "exact_mailbox_thread"
        if len(thread_matches) > 1:
            return None, True, "ambiguous_mailbox_thread"

    domain = str(counterparty_domain or "").casefold().strip(" .")
    if domain:
        domain_matches = [
            item for item in applications
            if item.counterparty_domain
            and item.counterparty_domain.casefold().strip(" .") == domain
        ]
        if len(domain_matches) == 1:
            return domain_matches[0].application_key, False, "unique_counterparty_domain"
        if len(domain_matches) > 1 and not normalize_title(job_title):
            return None, True, "ambiguous_counterparty_domain"

    employer_norm = normalize_company(employer_name)
    if not employer_norm or not normalize_title(job_title):
        return None, False, None

    title_matches = [
        item
        for item in applications
        if normalize_company(item.employer_name) == employer_norm
        and strong_title_family_match(item.job_title, job_title)
    ]
    if len(title_matches) == 1:
        return title_matches[0].application_key, False, "exact_company_title_family"
    if len(title_matches) > 1:
        return None, True, "ambiguous_company_title_family"
    return None, False, None
