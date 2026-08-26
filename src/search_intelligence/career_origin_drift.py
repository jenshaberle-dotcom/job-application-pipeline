"""Pure employer-backed career-origin / ATS drift candidate discovery.

This contract is intentionally weaker than source or job authority. It may only
nominate a new public career/ATS host when the transition is explicitly evidenced
by an already-authorized employer-origin page or by a verified redirect from that
page. A nominated host must still be fetched and pass the existing deterministic
identity, listing/detail and genuine-job proof contracts before any downstream
use.

No company-specific host, tenant, route, selector, provider token or job identifier
is encoded here.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re
from urllib.parse import urljoin, urlparse

from src.search_intelligence.ats_provider_registry import recognize_ats_provider
from src.search_intelligence.origin_source_discovery import is_known_aggregator_domain


_ANCHOR = re.compile(
    r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)
_IFRAME = re.compile(
    r"<iframe\b[^>]*src=[\"']([^\"'#]+)[\"'][^>]*>",
    flags=re.IGNORECASE | re.DOTALL,
)
_TAG = re.compile(r"<[^>]+>")

_RECRUITING_LABELS = frozenset(
    {
        "job",
        "jobs",
        "career",
        "careers",
        "karriere",
        "recruiting",
        "recruitment",
    }
)
_CAREER_TEXT_MARKERS = (
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "stellen",
    "stellenangebote",
    "open positions",
    "open roles",
    "vacancies",
    "opportunities",
    "join us",
)
_BLOCKED_TEXT_MARKERS = (
    "apply now",
    "bewerben",
    "application",
    "privacy",
    "datenschutz",
    "login",
    "sign in",
    "register",
    "contact",
    "cookie",
)
_BLOCKED_PATH_MARKERS = (
    "/apply",
    "/application",
    "/login",
    "/signin",
    "/register",
    "/privacy",
    "/datenschutz",
)


@dataclass(frozen=True)
class CareerOriginDriftCandidate:
    candidate_url: str
    candidate_host: str
    evidence_kind: str
    provider: str | None
    source_host: str
    host_authority: bool = False
    product_authority: bool = False

    def __post_init__(self) -> None:
        if self.host_authority:
            raise ValueError("career-origin drift discovery may not grant host authority")
        if self.product_authority:
            raise ValueError("career-origin drift discovery may not grant product authority")


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").casefold().strip(".")


def _host_is_authorized(value: str, allowed_hosts: tuple[str, ...] | set[str]) -> bool:
    normalized = {str(item).casefold().strip(".") for item in allowed_hosts if str(item)}
    return bool(_host(value) and _host(value) in normalized)


def _normalized_https_candidate(page_url: str, raw_url: str) -> str | None:
    candidate = urljoin(page_url, unescape(str(raw_url or "")).strip())
    parsed = urlparse(candidate)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    host = parsed.hostname.casefold().strip(".")
    if is_known_aggregator_domain(host):
        return None
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if any(marker in path.casefold() for marker in _BLOCKED_PATH_MARKERS):
        return None
    if path != "/":
        path = path.rstrip("/")
    return parsed._replace(
        scheme="https",
        netloc=host,
        path=path,
        params="",
        query="",
        fragment="",
    ).geturl()


def _normalized_text(value: str) -> str:
    text = unescape(_TAG.sub(" ", str(value or ""))).casefold()
    return re.sub(r"\s+", " ", text).strip()


def _career_context(*values: str) -> bool:
    text = " ".join(_normalized_text(value) for value in values if value)
    if not text or any(marker in text for marker in _BLOCKED_TEXT_MARKERS):
        return False
    return any(marker in text for marker in _CAREER_TEXT_MARKERS)


def _employer_parent_host(host: str) -> str:
    parts = [part for part in host.casefold().strip(".").split(".") if part]
    if len(parts) >= 3 and parts[0] in ({"www"} | set(_RECRUITING_LABELS)):
        return ".".join(parts[1:])
    return ".".join(parts)


def _recruiting_sibling(source_host: str, candidate_host: str) -> bool:
    source_parent = _employer_parent_host(source_host)
    if not source_parent or candidate_host == source_host:
        return False
    if not candidate_host.endswith("." + source_parent):
        return False
    prefix = candidate_host[: -(len(source_parent) + 1)].split(".")[0]
    return prefix in _RECRUITING_LABELS


def _candidate_from_explicit_transition(
    *,
    page_url: str,
    raw_url: str,
    label_or_context: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> CareerOriginDriftCandidate | None:
    if not _host_is_authorized(page_url, allowed_hosts):
        return None
    normalized = _normalized_https_candidate(page_url, raw_url)
    if normalized is None:
        return None

    source_host = _host(page_url)
    candidate_host = _host(normalized)
    if not candidate_host or candidate_host == source_host:
        return None

    parsed = urlparse(normalized)
    provider_recognition = recognize_ats_provider(normalized)
    path_context = (parsed.path or "").replace("-", " ").replace("_", " ")
    if not _career_context(label_or_context, candidate_host, path_context):
        return None

    if provider_recognition is not None:
        return CareerOriginDriftCandidate(
            candidate_url=normalized,
            candidate_host=candidate_host,
            evidence_kind="explicit_ats_career_transition",
            provider=provider_recognition.provider,
            source_host=source_host,
        )

    if _recruiting_sibling(source_host, candidate_host):
        return CareerOriginDriftCandidate(
            candidate_url=normalized,
            candidate_host=candidate_host,
            evidence_kind="explicit_recruiting_sibling_transition",
            provider=None,
            source_host=source_host,
        )
    return None


def career_origin_drift_candidates(
    *,
    page_url: str,
    html: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 8,
) -> tuple[CareerOriginDriftCandidate, ...]:
    """Nominate bounded cross-host career/ATS transitions explicitly exposed by a page.

    The source page must already be authorized. Only visible anchors and iframe
    ``src`` values are considered; provider text, a guessed hostname or form/apply
    target cannot create a candidate. Known aggregators are excluded. Returned
    candidates carry zero host or Product authority.
    """

    if limit < 1 or not _host_is_authorized(page_url, allowed_hosts):
        return ()

    transitions: list[tuple[str, str]] = []
    transitions.extend((raw_url, raw_label) for raw_url, raw_label in _ANCHOR.findall(html or ""))
    transitions.extend((raw_url, "career jobs iframe") for raw_url in _IFRAME.findall(html or ""))

    result: list[CareerOriginDriftCandidate] = []
    seen: set[str] = set()
    for raw_url, context in transitions:
        candidate = _candidate_from_explicit_transition(
            page_url=page_url,
            raw_url=raw_url,
            label_or_context=context,
            allowed_hosts=allowed_hosts,
        )
        if candidate is None or candidate.candidate_url in seen:
            continue
        seen.add(candidate.candidate_url)
        result.append(candidate)
        if len(result) >= limit:
            break
    return tuple(result)


def redirected_career_origin_candidate(
    *,
    source_url: str,
    final_url: str,
    allowed_hosts: tuple[str, ...] | set[str],
    employer_identity_confirmed: bool,
    career_like_confirmed: bool,
) -> CareerOriginDriftCandidate | None:
    """Nominate a cross-domain redirect only after existing identity/career probes agree.

    Redirect transport alone is insufficient. The caller must provide the result
    of the existing deterministic employer-identity and career-page checks. This
    supports genuine domain migration without encoding old/new company domains in
    product code.
    """

    if not _host_is_authorized(source_url, allowed_hosts):
        return None
    if not employer_identity_confirmed or not career_like_confirmed:
        return None
    normalized = _normalized_https_candidate(source_url, final_url)
    if normalized is None:
        return None

    source_host = _host(source_url)
    candidate_host = _host(normalized)
    if not candidate_host or candidate_host == source_host:
        return None
    provider = recognize_ats_provider(normalized)
    return CareerOriginDriftCandidate(
        candidate_url=normalized,
        candidate_host=candidate_host,
        evidence_kind="verified_career_redirect_transition",
        provider=None if provider is None else provider.provider,
        source_host=source_host,
    )


__all__ = [
    "CareerOriginDriftCandidate",
    "career_origin_drift_candidates",
    "redirected_career_origin_candidate",
]
