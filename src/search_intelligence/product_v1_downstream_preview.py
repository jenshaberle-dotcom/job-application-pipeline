"""Read-only downstream Product V1 evidence preview for the Control Center.

The preview fetches one already-validated employer-origin HTTPS detail page,
materializes deterministic Assessment + Ranking evidence, and compares that
preview with the currently stored Product V1 assessment row. It never writes to
the database, calls an LLM/provider, decides capability fit, changes hard-filter
or Top-5 authority, or persists raw HTML.
"""

from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
import ipaddress
import socket
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlparse

import requests

from src.search_intelligence.product_v1_assessment_evidence import (
    extract_product_v1_assessment_evidence,
)
from src.search_intelligence.product_v1_ranking_evidence import (
    build_product_v1_ranking_evidence,
)


MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 2_000_000
FETCH_TIMEOUT_SECONDS = 15.0
USER_AGENT = "DeepOceanProductV1EvidencePreview/1.0"


class DownstreamPreviewStop(RuntimeError):
    """Fail closed when preview source/evidence boundaries are not satisfied."""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._title_depth = 0
        self._title_parts: list[str] = []
        self._parts: list[str] = []
        self._suppressed_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        if normalized in {"script", "style", "noscript", "svg"}:
            self._suppressed_depth += 1
        if normalized == "title":
            self._title_depth += 1

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized == "title" and self._title_depth:
            self._title_depth -= 1
        if normalized in {"script", "style", "noscript", "svg"} and self._suppressed_depth:
            self._suppressed_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._suppressed_depth:
            return
        value = " ".join(data.split())
        if not value:
            return
        self._parts.append(value)
        if self._title_depth:
            self._title_parts.append(value)

    @property
    def text(self) -> str:
        return " ".join(self._parts)

    @property
    def title(self) -> str:
        return " ".join(self._title_parts)


Resolver = Callable[..., Sequence[tuple[Any, ...]]]


def _public_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_https_url(
    url: str,
    *,
    resolver: Resolver = socket.getaddrinfo,
) -> str:
    """Require credential-free HTTPS whose DNS answers are all public IPs."""

    parsed = urlparse(str(url or "").strip())
    if parsed.scheme.casefold() != "https":
        raise DownstreamPreviewStop("preview source must use HTTPS")
    if not parsed.hostname:
        raise DownstreamPreviewStop("preview source hostname is missing")
    if parsed.username is not None or parsed.password is not None:
        raise DownstreamPreviewStop("preview source credentials are forbidden")
    try:
        infos = resolver(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise DownstreamPreviewStop("preview source DNS resolution failed") from exc
    addresses = {
        str(info[4][0])
        for info in infos
        if len(info) >= 5 and info[4] and len(info[4]) >= 1
    }
    if not addresses or any(not _public_ip(address) for address in addresses):
        raise DownstreamPreviewStop("preview source resolved to a non-public address")
    return parsed.geturl()


def fetch_public_https_detail_text(
    url: str,
    *,
    session: requests.Session | None = None,
    resolver: Resolver = socket.getaddrinfo,
    max_redirects: int = MAX_REDIRECTS,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
    timeout_seconds: float = FETCH_TIMEOUT_SECONDS,
) -> tuple[str, str, str]:
    """Fetch bounded detail HTML without persisting it; return final URL/title/text."""

    client = session or requests.Session()
    current_url = validate_public_https_url(url, resolver=resolver)
    for redirect_index in range(max_redirects + 1):
        try:
            response = client.get(
                current_url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9"},
                timeout=timeout_seconds,
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            raise DownstreamPreviewStop("preview detail fetch failed") from exc

        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            if not location or redirect_index >= max_redirects:
                raise DownstreamPreviewStop("preview redirect boundary exceeded")
            current_url = validate_public_https_url(
                urljoin(current_url, location),
                resolver=resolver,
            )
            response.close()
            continue
        if response.status_code != 200:
            raise DownstreamPreviewStop(
                f"preview detail returned HTTP {response.status_code}"
            )

        content_type = str(response.headers.get("Content-Type") or "").casefold()
        if content_type and not (
            content_type.startswith("text/html") or content_type.startswith("text/plain")
        ):
            raise DownstreamPreviewStop("preview source is not HTML/text")

        chunks: list[bytes] = []
        total = 0
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_response_bytes:
                    raise DownstreamPreviewStop("preview detail exceeds response-size bound")
                chunks.append(bytes(chunk))
        finally:
            response.close()
        encoding = response.encoding or "utf-8"
        html = b"".join(chunks).decode(encoding, errors="replace")
        extractor = _TextExtractor()
        extractor.feed(html)
        detail_text = extractor.text.strip()
        if not detail_text:
            raise DownstreamPreviewStop("preview detail text is empty")
        return current_url, extractor.title.strip(), detail_text

    raise DownstreamPreviewStop("preview redirect boundary exceeded")


_STORED_ASSESSMENT_FIELDS = (
    "employment_type",
    "employment_evidence_status",
    "required_languages",
    "language_evidence_status",
    "weekly_hours_min",
    "weekly_hours_max",
    "weekly_hours_evidence_status",
    "work_model",
    "title_seniority",
    "requirements_seniority",
    "seniority_evidence_status",
    "capability_fit_status",
    "capability_fit_evidence_status",
    "profile_direction_score",
    "data_focus_score",
    "reliability_focus_score",
    "evidence_quality_score",
)


def _stored_snapshot(row: Mapping[str, object]) -> dict[str, object]:
    return {field: row.get(field) for field in _STORED_ASSESSMENT_FIELDS}


def _delta(
    *,
    stored: Mapping[str, object],
    deterministic: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for field, preview_value in deterministic.items():
        if field not in stored:
            continue
        stored_value = stored.get(field)
        if stored_value != preview_value:
            result[field] = {"stored": stored_value, "preview": preview_value}
    return result


def build_product_v1_downstream_preview(
    *,
    row: Mapping[str, object],
    final_url: str,
    fetched_title: str,
    detail_text: str,
) -> dict[str, object]:
    """Build deterministic Assessment/Ranking preview for one DB-authoritative job."""

    if str(row.get("canonical_source_type") or "") != "employer_origin":
        raise DownstreamPreviewStop("employer-origin source authority is required")
    if str(row.get("origin_validation_status") or "") != "validated":
        raise DownstreamPreviewStop("validated origin authority is required")
    if str(row.get("activity_status") or "") != "active":
        raise DownstreamPreviewStop("current active vacancy authority is required")
    source_url = str(row.get("source_url") or "")
    if not source_url:
        raise DownstreamPreviewStop("source URL is missing")
    title = str(row.get("title") or fetched_title or "").strip()
    if not title:
        raise DownstreamPreviewStop("job title is missing")

    assessment = extract_product_v1_assessment_evidence(
        description=detail_text,
        title=title,
        source_url=final_url,
    )
    ranking = build_product_v1_ranking_evidence(
        title=title,
        description=detail_text,
        origin_validation_status="validated",
        activity_status="active",
        assessment_evidence=assessment,
    )
    stored = _stored_snapshot(row)
    assessment_patch = assessment.assessment_patch()
    score_patch = ranking.ranking_scores_patch()
    deterministic_patch = {**assessment_patch, **score_patch}
    capability_status = str(row.get("capability_fit_status") or "unknown")
    capability_evidence_status = str(
        row.get("capability_fit_evidence_status") or "unknown"
    )

    return {
        "schema_version": "product_v1.downstream_evidence_preview.v1",
        "status": "preview_ready",
        "target": {
            "silver_job_id": int(row.get("silver_job_id") or 0),
            "title": title,
            "company_name": row.get("company_name"),
            "source_url": source_url,
            "final_url": final_url,
            "canonical_source_type": row.get("canonical_source_type"),
            "origin_validation_status": row.get("origin_validation_status"),
            "activity_status": row.get("activity_status"),
            "product_readiness_status": row.get("product_readiness_status"),
            "detail_sha256": sha256(detail_text.encode("utf-8")).hexdigest(),
            "raw_html_persisted": False,
        },
        "assessment": assessment.canonical_payload(),
        "ranking": ranking.canonical_payload(),
        "stored_assessment": stored,
        "deterministic_patch_preview": deterministic_patch,
        "delta": _delta(stored=stored, deterministic=deterministic_patch),
        "capability_fit_review": {
            "status": capability_status,
            "evidence_status": capability_evidence_status,
            "review_required": capability_status != "passed",
            "reason": (
                "candidate_fact_or_operator_evidence_required"
                if capability_status != "passed"
                else "existing_capability_fit_evidence_present"
            ),
            "auto_pass_from_tag_overlap": False,
        },
        "boundaries": {
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
            "database_writes": 0,
            "hard_filter_writes": 0,
            "ranking_writes": 0,
            "application_writes": 0,
            "hard_filter_authority": False,
            "ranking_authority": False,
            "top5_authority": False,
            "application_authority": False,
            "product_authority": False,
        },
    }


__all__ = [
    "DownstreamPreviewStop",
    "build_product_v1_downstream_preview",
    "fetch_public_https_detail_text",
    "validate_public_https_url",
]
