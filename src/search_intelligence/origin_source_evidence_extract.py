"""Deterministic extraction and classification helpers for origin evidence."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from typing import Iterable, Mapping, Sequence
from urllib.parse import parse_qs, urljoin, urlparse

from src.search_intelligence.origin_source_discovery_agent import (
    ascii_fold,
    is_known_ats_provider_domain,
    normalize_candidate_url,
    tokenize,
)
from src.search_intelligence.origin_source_evidence_models import (
    CAREER_TERMS,
    DETAIL_PATH_MARKERS,
    LEGAL_FORM_TOKENS,
    SOCIAL_HOSTS,
    LinkEvidence,
    PageEvidence,
    _PageParser,
)

def normalize_org_name(value: str | None) -> str:
    tokens = [
        token
        for token in tokenize(value)
        if token not in LEGAL_FORM_TOKENS and token not in CAREER_TERMS
    ]
    return " ".join(tokens)


def _normalized_host(host: str | None) -> str:
    value = str(host or "").lower().strip(".")
    return value[4:] if value.startswith("www.") else value


def _host_matches(host: str, expected: str) -> bool:
    return host == expected or host.endswith("." + expected)


def is_social_host(host: str | None) -> bool:
    normalized = _normalized_host(host)
    return any(_host_matches(normalized, item) for item in SOCIAL_HOSTS)


def validate_public_https_url(url: str) -> tuple[bool, str | None]:
    normalized = normalize_candidate_url(url)
    if normalized is None:
        return False, "invalid_url"
    parsed = urlparse(normalized)
    if parsed.scheme != "https":
        return False, "https_required"
    host = str(parsed.hostname or "").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False, "local_host_blocked"
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        return False, "non_public_ip_blocked"
    return True, None


def resolves_to_public_addresses(host: str) -> tuple[bool, str | None]:
    """Reject DNS answers that could reach loopback, private or metadata networks."""

    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False, "dns_resolution_failed"
    addresses = {str(item[4][0]) for item in infos if item[4]}
    if not addresses:
        return False, "dns_resolution_empty"
    for raw in addresses:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            return False, "dns_address_invalid"
        if not address.is_global:
            return False, "dns_non_public_address_blocked"
    return True, None


def _walk_json(value: object) -> Iterable[Mapping[str, object]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            yield from _walk_json(child)


def _json_ld_jobposting_count(body: str) -> int:
    count = 0
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        body or "",
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            payload = json.loads(match.group(1).strip())
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _walk_json(payload):
            raw_type = item.get("@type")
            types = raw_type if isinstance(raw_type, list) else [raw_type]
            if any(str(current or "").lower() == "jobposting" for current in types):
                count += 1
    return count


def page_evidence_from_html(
    *,
    requested_url: str,
    final_url: str,
    status_code: int | None,
    body: str,
    failure_class: str | None = None,
) -> PageEvidence:
    parser = _PageParser()
    try:
        parser.feed(body or "")
    except (ValueError, TypeError):
        failure_class = failure_class or "html_parse_failed"
    links = tuple(parser.links)
    return PageEvidence(
        requested_url=requested_url,
        final_url=final_url,
        status_code=status_code,
        reachable=status_code is not None and 200 <= status_code < 400,
        title=parser.title,
        html_lang=parser.html_lang,
        text=parser.text[:200_000],
        links=links,
        embedded_urls=_embedded_urls(body),
        json_ld_jobposting_count=_json_ld_jobposting_count(body),
        failure_class=failure_class,
    )


def failed_page_evidence(url: str, failure_class: str) -> PageEvidence:
    return PageEvidence(
        requested_url=url,
        final_url=url,
        status_code=None,
        reachable=False,
        title="",
        html_lang=None,
        text="",
        links=(),
        embedded_urls=(),
        json_ld_jobposting_count=0,
        failure_class=failure_class,
    )


def _is_job_detail_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    query = {key.lower() for key in parse_qs(parsed.query)}
    if query & {"jobid", "job_id", "jobreqid", "requisitionid", "rid"}:
        return True
    for marker in DETAIL_PATH_MARKERS:
        position = path.find(marker)
        if position < 0:
            continue
        tail = path[position + len(marker) :].strip("/")
        if tail and tail not in {"search", "stellenangebote", "vacancies"}:
            return True
    return False


def _embedded_urls(body: str) -> tuple[str, ...]:
    normalized = (body or "").replace("\\/", "/")
    matches: list[str] = list(
        re.findall(r"https?://[^\s\"'<>\\]+", normalized, flags=re.IGNORECASE)
    )
    quoted_values = re.findall(r"[\"']([^\"']{3,500})[\"']", normalized)
    for value in quoted_values:
        lowered = value.lower()
        if any(marker in lowered for marker in DETAIL_PATH_MARKERS):
            matches.append(value)
    return tuple(dict.fromkeys(matches[:400]))


def extract_job_links(page: PageEvidence, *, max_links: int = 20) -> tuple[LinkEvidence, ...]:
    base = page.final_url
    base_host = _normalized_host(urlparse(base).hostname)
    raw_links = list(page.links)
    raw_links.extend(LinkEvidence(url=item) for item in page.embedded_urls)
    result: list[LinkEvidence] = []
    seen: set[str] = set()
    for item in raw_links:
        absolute = urljoin(base, item.url).split("#", 1)[0]
        detail_shape = _is_job_detail_url(absolute)
        normalized = normalize_candidate_url(absolute)
        if normalized is None:
            continue
        parsed = urlparse(normalized)
        host = _normalized_host(parsed.hostname)
        allowed_host = host == base_host or is_known_ats_provider_domain(host)
        if not allowed_host or not detail_shape:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(LinkEvidence(url=normalized, text=item.text[:300]))
        if len(result) >= max_links:
            break
    return tuple(result)


def detect_locale(page: PageEvidence, url: str) -> str:
    lang = str(page.html_lang or "").lower()
    if lang.startswith("de"):
        return "de"
    if lang.startswith("en"):
        return "en"
    path = urlparse(url).path.lower()
    if re.search(r"/(de|de-de)(/|$)", path):
        return "de"
    if re.search(r"/(en|en-us|en-gb)(/|$)", path):
        return "en"
    folded = ascii_fold(page.text[:20_000])
    german_hits = sum(term in folded for term in ("bewerbung", "karriere", "stellenangebote"))
    english_hits = sum(term in folded for term in ("application", "careers", "vacancies"))
    if german_hits > english_hits:
        return "de"
    if english_hits > german_hits:
        return "en"
    return "neutral"


def _ats_family(url: str, page: PageEvidence) -> str | None:
    haystack = ascii_fold(f"{url} {page.title} {page.text[:30_000]}")
    checks = (
        ("workday", "Workday"),
        ("successfactors", "SAP SuccessFactors"),
        ("personio", "Personio"),
        ("softgarden", "Softgarden"),
        ("smartrecruiters", "SmartRecruiters"),
        ("greenhouse", "Greenhouse"),
        ("lever.co", "Lever"),
        ("onlyfy", "Onlyfy"),
        ("rexx", "Rexx"),
        ("dvinci", "d.vinci"),
    )
    for marker, family in checks:
        if marker in haystack:
            return family
    return None
