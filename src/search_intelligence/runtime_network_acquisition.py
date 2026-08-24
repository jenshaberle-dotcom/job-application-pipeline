"""Pure runtime-network evidence recognition for dynamic job acquisition.

The browser/runtime adapter is intentionally outside this module. Callers may pass
one transient JSON payload at a time; the recognizer returns bounded, sanitized
hypotheses only. It performs no network, provider, database, product, lifecycle, or
source mutation and never establishes genuine-job or employer authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

SENSITIVE_QUERY_KEYS = {
    "access_token",
    "apikey",
    "api_key",
    "auth",
    "authorization",
    "code",
    "credential",
    "key",
    "password",
    "secret",
    "session",
    "sessionid",
    "sig",
    "signature",
    "token",
}

JOB_CONTEXT_MARKERS = {
    "career",
    "careers",
    "job",
    "jobs",
    "jobposting",
    "jobpostings",
    "opening",
    "openings",
    "position",
    "positions",
    "requisition",
    "requisitions",
    "vacancy",
    "vacancies",
}

TITLE_KEYS = {
    "jobtitle",
    "positiontitle",
    "requisitiontitle",
    "title",
}
IDENTITY_KEYS = {
    "id",
    "jobid",
    "jobreqid",
    "positionid",
    "requisitionid",
    "reqid",
    "slug",
}
URL_KEYS = {
    "applyurl",
    "detailurl",
    "externalurl",
    "joburl",
    "url",
}
LOCATION_KEYS = {
    "city",
    "joblocation",
    "location",
    "locations",
}
EXPLICIT_JOB_KEYS = {
    "applyurl",
    "jobid",
    "joblocation",
    "jobreqid",
    "jobtitle",
    "joburl",
    "positionid",
    "positiontitle",
    "requisitionid",
    "requisitiontitle",
}


@dataclass(frozen=True)
class NetworkObservation:
    """Sanitized metadata for one transient structured response observation."""

    request_method: str
    request_url: str
    response_url: str
    status_code: int
    content_type: str
    resource_type: str


@dataclass(frozen=True)
class JobPayloadCandidate:
    """One provider-agnostic job-object hypothesis extracted from observed JSON."""

    evidence_path: str
    score: int
    title: str
    identity: str
    candidate_url: str
    location: str
    host_authorized: bool
    explicit_job_key: bool
    job_context: bool


@dataclass(frozen=True)
class NetworkRecognitionResult:
    """Bounded recognition output that intentionally excludes the raw payload."""

    observation: NetworkObservation
    nodes_examined: int
    traversal_truncated: bool
    candidates: tuple[JobPayloadCandidate, ...]
    no_product_authority: bool = True


def _normalized_key(value: object) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def _normalized_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return " ".join(str(value).split()).strip()
    return ""


def _first_scalar(mapping: dict[str, Any], keys: set[str]) -> tuple[str, str]:
    for raw_key, value in mapping.items():
        key = _normalized_key(raw_key)
        if key in keys:
            text = _normalized_text(value)
            if text:
                return key, text
    return "", ""


def _location_text(mapping: dict[str, Any]) -> str:
    for raw_key, value in mapping.items():
        if _normalized_key(raw_key) not in LOCATION_KEYS:
            continue
        direct = _normalized_text(value)
        if direct:
            return direct
        if isinstance(value, dict):
            pieces = [
                _normalized_text(item)
                for key, item in value.items()
                if _normalized_key(key) in {"city", "country", "name", "region"}
            ]
            joined = ", ".join(piece for piece in pieces if piece)
            if joined:
                return joined
        if isinstance(value, list):
            pieces = [_normalized_text(item) for item in value]
            joined = ", ".join(piece for piece in pieces if piece)
            if joined:
                return joined
    return ""


def sanitize_url(value: str) -> str:
    """Redact secret-like query values while preserving endpoint shape."""

    parsed = urlparse(str(value or ""))
    query: list[tuple[str, str]] = []
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        normalized = _normalized_key(key)
        query.append((key, "<redacted>" if normalized in SENSITIVE_QUERY_KEYS else item))
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query, doseq=True),
            "",
        )
    )


def sanitize_observation(observation: NetworkObservation) -> NetworkObservation:
    """Return metadata safe for evidence persistence; no headers/body are retained."""

    return NetworkObservation(
        request_method=str(observation.request_method or "").upper(),
        request_url=sanitize_url(observation.request_url),
        response_url=sanitize_url(observation.response_url),
        status_code=int(observation.status_code),
        content_type=str(observation.content_type or "").split(";", 1)[0].strip().casefold(),
        resource_type=str(observation.resource_type or "").casefold(),
    )


def _allowed_host(url: str, allowed_hosts: Iterable[str]) -> bool:
    hostname = (urlparse(url).hostname or "").casefold()
    normalized = {str(item).casefold().strip(".") for item in allowed_hosts if str(item)}
    return bool(hostname and hostname in normalized)


def _job_context(path: tuple[str, ...]) -> bool:
    for item in path:
        normalized = _normalized_key(item)
        if normalized in JOB_CONTEXT_MARKERS:
            return True
        if any(marker in normalized for marker in JOB_CONTEXT_MARKERS if len(marker) >= 4):
            return True
    return False


def _walk_dict_nodes(
    payload: Any,
    *,
    max_nodes: int,
    max_depth: int,
) -> tuple[list[tuple[tuple[str, ...], dict[str, Any]]], bool]:
    if max_nodes < 1:
        raise ValueError("max_nodes must be >= 1")
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")

    found: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    stack: list[tuple[tuple[str, ...], Any, int]] = [((), payload, 0)]
    examined = 0
    truncated = False

    while stack:
        path, value, depth = stack.pop()
        examined += 1
        if examined > max_nodes:
            truncated = True
            break
        if isinstance(value, dict):
            found.append((path, value))
            if depth >= max_depth:
                continue
            for key, child in reversed(list(value.items())):
                stack.append(((*path, str(key)), child, depth + 1))
        elif isinstance(value, list):
            if depth >= max_depth:
                continue
            for index in range(len(value) - 1, -1, -1):
                stack.append(((*path, f"[{index}]"), value[index], depth + 1))
    return found, truncated


def _candidate_from_mapping(
    *,
    path: tuple[str, ...],
    mapping: dict[str, Any],
    base_url: str,
    allowed_hosts: Iterable[str],
) -> JobPayloadCandidate | None:
    title_key, title = _first_scalar(mapping, TITLE_KEYS)
    identity_key, identity = _first_scalar(mapping, IDENTITY_KEYS)
    url_key, raw_url = _first_scalar(mapping, URL_KEYS)
    location = _location_text(mapping)
    normalized_keys = {_normalized_key(key) for key in mapping}
    explicit_job_key = bool(normalized_keys & EXPLICIT_JOB_KEYS)
    job_context = _job_context(path)

    if not title or not (identity or raw_url):
        return None
    if not (explicit_job_key or job_context):
        return None

    candidate_url = ""
    if raw_url:
        resolved = urljoin(base_url, raw_url)
        if urlparse(resolved).scheme.casefold() == "https":
            candidate_url = sanitize_url(resolved)

    score = 2
    if identity:
        score += 1
    if candidate_url:
        score += 2
    if location:
        score += 1
    if explicit_job_key:
        score += 2
    if job_context:
        score += 2
    if title_key != "title":
        score += 1
    if identity_key not in {"", "id", "slug"}:
        score += 1
    if url_key not in {"", "url"}:
        score += 1

    if score < 5:
        return None

    return JobPayloadCandidate(
        evidence_path=".".join(path) or "$",
        score=score,
        title=title,
        identity=identity,
        candidate_url=candidate_url,
        location=location,
        host_authorized=bool(candidate_url and _allowed_host(candidate_url, allowed_hosts)),
        explicit_job_key=explicit_job_key,
        job_context=job_context,
    )


def recognize_job_payload(
    observation: NetworkObservation,
    payload: Any,
    *,
    allowed_hosts: Iterable[str],
    max_nodes: int = 500,
    max_depth: int = 8,
    max_candidates: int = 50,
) -> NetworkRecognitionResult:
    """Recognize bounded job-object hypotheses in one observed structured response."""

    if max_candidates < 1:
        raise ValueError("max_candidates must be >= 1")

    safe_observation = sanitize_observation(observation)
    content_type = safe_observation.content_type
    structured = "json" in content_type or safe_observation.resource_type in {"fetch", "xhr"}
    if safe_observation.status_code >= 400 or not structured:
        return NetworkRecognitionResult(safe_observation, 0, False, ())

    nodes, truncated = _walk_dict_nodes(payload, max_nodes=max_nodes, max_depth=max_depth)
    candidates: list[JobPayloadCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    base_url = safe_observation.response_url or safe_observation.request_url

    for path, mapping in nodes:
        candidate = _candidate_from_mapping(
            path=path,
            mapping=mapping,
            base_url=base_url,
            allowed_hosts=allowed_hosts,
        )
        if candidate is None:
            continue
        identity = (candidate.identity, candidate.candidate_url, candidate.title.casefold())
        if identity in seen:
            continue
        seen.add(identity)
        candidates.append(candidate)
        if len(candidates) >= max_candidates:
            truncated = truncated or len(nodes) > len(candidates)
            break

    candidates.sort(
        key=lambda item: (
            not item.host_authorized,
            -item.score,
            item.evidence_path,
            item.title.casefold(),
        )
    )
    return NetworkRecognitionResult(
        observation=safe_observation,
        nodes_examined=len(nodes),
        traversal_truncated=truncated,
        candidates=tuple(candidates),
    )
