"""Deterministic Listing Discovery evidence fusion for LLM-BOOST-001.

This module does not fetch, search, call a model, or mutate product state.  It
combines already-bounded HTTP evidence with the existing connector-feasibility
link classifiers so Listing Discovery can distinguish a real external
information gap from a deterministic projection/follow-up task.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from html import unescape
import json
import re
from typing import Iterable, Mapping
from urllib.parse import urljoin, urlparse

from src.search_intelligence.connector_feasibility import (
    KNOWN_AGGREGATOR_DOMAINS,
    SOCIAL_OR_EXTERNAL_NOISE_DOMAINS,
    ProbeFetchResult,
    classify_evidence_links,
    html_has_structural_job_evidence,
    is_public_https_origin_url,
    is_technical_or_asset_url,
)
from src.search_intelligence.connector_feasibility_query_runtime import (
    extract_trusted_query_job_detail_links,
)
from src.search_intelligence.connector_feasibility_runtime import (
    extract_trusted_delegated_job_board_urls,
)
from src.search_intelligence.llm_booster_policy import (
    BoosterPlan,
    BoosterSurface,
    TavilyState,
    build_booster_plan,
)

LISTING_EVIDENCE_CONTRACT_VERSION = "LLM-BOOST-001.listing-evidence.v1"

_JOB_ROUTE_PARTS = {
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "search",
    "job-search",
    "jobsearch",
    "stellen",
    "stellenangebote",
    "jobsuche",
    "vacancies",
    "positions",
    "open-positions",
    "iframe",
}
_JOB_HOST_LABELS = {
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "recruiting",
    "recruitment",
}
_LOCALE_PARTS = {"de", "de-de", "en", "en-gb", "en-us", "at", "ch"}
_JSON_LD_SCRIPT = re.compile(
    r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    flags=re.IGNORECASE | re.DOTALL,
)
_IFRAME_SRC = re.compile(
    r"<iframe\b[^>]*\bsrc=[\"']([^\"'#]+)[\"']",
    flags=re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class ListingSurfaceEvidence:
    contract_version: str
    origin_url: str | None
    final_url: str | None
    http_status: int | None
    classification: str
    current_job_urls: tuple[str, ...]
    route_candidates: tuple[str, ...]
    delegated_route_candidates: tuple[str, ...]
    jsonld_types: tuple[str, ...]
    structural_html: bool
    same_host_redirect: bool
    external_search_gap: bool
    next_action: str
    reason_codes: tuple[str, ...]
    evidence_fingerprint: str
    product_authority: bool = False

    @property
    def booster_eligible(self) -> bool:
        return self.external_search_gap

    def to_json(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "origin_url": self.origin_url,
            "final_url": self.final_url,
            "http_status": self.http_status,
            "classification": self.classification,
            "current_job_urls": list(self.current_job_urls),
            "current_job_url_count": len(self.current_job_urls),
            "route_candidates": list(self.route_candidates),
            "delegated_route_candidates": list(self.delegated_route_candidates),
            "jsonld_types": list(self.jsonld_types),
            "structural_html": self.structural_html,
            "same_host_redirect": self.same_host_redirect,
            "external_search_gap": self.external_search_gap,
            "booster_eligible": self.booster_eligible,
            "next_action": self.next_action,
            "reason_codes": list(self.reason_codes),
            "evidence_fingerprint": self.evidence_fingerprint,
            "product_authority": self.product_authority,
        }


def _registered_domain(url_or_host: str | None) -> str:
    if not url_or_host:
        return ""
    host = urlparse(url_or_host).hostname or url_or_host
    host = host.lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) < 2:
        return host
    return ".".join(parts[-2:])


def _same_registered_domain(left: str | None, right: str | None) -> bool:
    left_domain = _registered_domain(left)
    return bool(left_domain and left_domain == _registered_domain(right))


def _job_host(url: str) -> bool:
    labels = {
        part
        for part in (urlparse(url).hostname or "").lower().split(".")
        if part
    }
    return bool(labels.intersection(_JOB_HOST_LABELS))


def _job_route_path(url: str) -> bool:
    parts = {
        part.replace("_", "-").lower()
        for part in urlparse(url).path.strip("/").split("/")
        if part
    }
    if parts.intersection(_JOB_ROUTE_PARTS):
        return True
    return len(parts) <= 1 and (not parts or next(iter(parts)) in _LOCALE_PARTS)


def _safe_route_candidate(
    origin_url: str,
    reference_url: str,
    candidate_url: str,
) -> bool:
    parsed = urlparse(candidate_url)
    host = (parsed.hostname or "").lower()
    if not is_public_https_origin_url(candidate_url):
        return False
    if host in KNOWN_AGGREGATOR_DOMAINS or host in SOCIAL_OR_EXTERNAL_NOISE_DOMAINS:
        return False
    if is_technical_or_asset_url(candidate_url):
        return False
    related = _same_registered_domain(origin_url, candidate_url) or _same_registered_domain(
        reference_url, candidate_url
    )
    if not (related or _job_host(candidate_url)):
        return False
    return _job_route_path(candidate_url)


def _iframe_route_candidates(
    origin_url: str,
    final_url: str,
    html: str,
    *,
    limit: int = 10,
) -> tuple[str, ...]:
    found: list[str] = []
    for raw_src in _IFRAME_SRC.findall(html):
        absolute = urljoin(final_url, unescape(raw_src).strip())
        if not _safe_route_candidate(origin_url, final_url, absolute):
            continue
        if absolute not in found:
            found.append(absolute)
        if len(found) >= limit:
            break
    return tuple(found)


def _jsonld_type_values(value: object) -> Iterable[str]:
    if isinstance(value, Mapping):
        raw_type = value.get("@type")
        if isinstance(raw_type, str):
            yield raw_type
        elif isinstance(raw_type, list):
            for item in raw_type:
                if isinstance(item, str):
                    yield item
        for nested in value.values():
            yield from _jsonld_type_values(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _jsonld_type_values(item)


def extract_jsonld_types(html: str) -> tuple[str, ...]:
    types: set[str] = set()
    for raw in _JSON_LD_SCRIPT.findall(html):
        try:
            payload = json.loads(unescape(raw).strip())
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        for value in _jsonld_type_values(payload):
            normalized = value.strip()
            if normalized:
                types.add(normalized)
    return tuple(sorted(types, key=str.lower))


def _dedupe_sorted(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}))


def _fingerprint(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def analyze_listing_surface(
    *,
    origin_url: str | None,
    fetch_result: ProbeFetchResult | None,
) -> ListingSurfaceEvidence:
    """Fuse bounded listing evidence into one deterministic escalation decision."""

    if not origin_url:
        base = {
            "origin_url": None,
            "final_url": None,
            "http_status": None,
            "classification": "missing_origin_url",
            "current_job_urls": (),
            "route_candidates": (),
            "delegated_route_candidates": (),
            "jsonld_types": (),
            "structural_html": False,
            "same_host_redirect": False,
            "external_search_gap": False,
            "next_action": "resolve_origin_first",
            "reason_codes": ("origin_url_missing",),
        }
        return ListingSurfaceEvidence(
            contract_version=LISTING_EVIDENCE_CONTRACT_VERSION,
            evidence_fingerprint=_fingerprint(base),
            product_authority=False,
            **base,
        )

    if fetch_result is None:
        base = {
            "origin_url": origin_url,
            "final_url": origin_url,
            "http_status": None,
            "classification": "fetch_evidence_missing",
            "current_job_urls": (),
            "route_candidates": (),
            "delegated_route_candidates": (),
            "jsonld_types": (),
            "structural_html": False,
            "same_host_redirect": False,
            "external_search_gap": False,
            "next_action": "obtain_bounded_fetch_evidence",
            "reason_codes": ("fetch_evidence_missing",),
        }
        return ListingSurfaceEvidence(
            contract_version=LISTING_EVIDENCE_CONTRACT_VERSION,
            evidence_fingerprint=_fingerprint(base),
            product_authority=False,
            **base,
        )

    final_url = fetch_result.final_url or origin_url
    html = fetch_result.body or ""
    same_host_redirect = (
        final_url.rstrip("/") != origin_url.rstrip("/")
        and _same_registered_domain(origin_url, final_url)
    )

    classification = classify_evidence_links(final_url, html)
    current_job_urls = list(classification.job_detail_candidate_urls)
    current_job_urls.extend(
        link.url
        for link in extract_trusted_query_job_detail_links(final_url, html)
    )
    current_job_urls_tuple = _dedupe_sorted(current_job_urls)

    delegated = extract_trusted_delegated_job_board_urls(final_url, html)
    iframe_routes = _iframe_route_candidates(origin_url, final_url, html)
    route_candidates: list[str] = list(iframe_routes)
    if same_host_redirect and _safe_route_candidate(origin_url, origin_url, final_url):
        route_candidates.append(final_url)
    route_candidates_tuple = _dedupe_sorted(route_candidates)
    delegated_tuple = _dedupe_sorted(delegated)

    jsonld_types = extract_jsonld_types(html)
    jsonld_job_structure = any(
        value.lower() in {"jobposting", "itemlist", "searchresultspage"}
        for value in jsonld_types
    )
    structural_html = html_has_structural_job_evidence(html)
    reachable = bool(fetch_result.http_status and 200 <= fetch_result.http_status < 400)

    reason_codes: list[str] = []
    if current_job_urls_tuple:
        surface_class = "current_listing_route_proven"
        next_action = "use_current_listing_route"
        external_search_gap = False
        reason_codes.append("concrete_current_job_links_present")
        if same_host_redirect:
            reason_codes.append("same_registered_domain_redirect")
    elif route_candidates_tuple or delegated_tuple:
        surface_class = "deterministic_listing_route_candidate"
        next_action = "bounded_follow_route_candidate"
        external_search_gap = False
        reason_codes.append("trusted_route_candidate_present")
        if same_host_redirect:
            reason_codes.append("same_registered_domain_redirect")
    elif jsonld_job_structure or structural_html or classification.structural_count > 0:
        surface_class = "dynamic_listing_structure"
        next_action = "improve_bounded_detail_projection"
        external_search_gap = False
        if jsonld_job_structure:
            reason_codes.append("jsonld_job_structure_present")
        if structural_html:
            reason_codes.append("html_job_structure_present")
        if classification.structural_count > 0:
            reason_codes.append("classified_job_structure_present")
    elif fetch_result.blocked_by_site:
        surface_class = "blocked_listing_surface"
        next_action = "external_search_eligible"
        external_search_gap = True
        reason_codes.append("site_blocked_bounded_listing_inspection")
    elif not reachable:
        surface_class = "operational_fetch_failure"
        next_action = "recover_bounded_fetch_before_booster"
        external_search_gap = False
        reason_codes.append("listing_fetch_not_reachable")
    else:
        surface_class = "external_listing_information_gap"
        next_action = "external_search_eligible"
        external_search_gap = True
        reason_codes.append("reachable_surface_without_listing_evidence")

    fingerprint_payload = {
        "origin_url": origin_url,
        "final_url": final_url,
        "http_status": fetch_result.http_status,
        "classification": surface_class,
        "current_job_urls": current_job_urls_tuple,
        "route_candidates": route_candidates_tuple,
        "delegated_route_candidates": delegated_tuple,
        "jsonld_types": jsonld_types,
        "structural_html": structural_html,
        "same_host_redirect": same_host_redirect,
        "external_search_gap": external_search_gap,
        "next_action": next_action,
        "reason_codes": tuple(sorted(reason_codes)),
    }
    return ListingSurfaceEvidence(
        contract_version=LISTING_EVIDENCE_CONTRACT_VERSION,
        origin_url=origin_url,
        final_url=final_url,
        http_status=fetch_result.http_status,
        classification=surface_class,
        current_job_urls=current_job_urls_tuple,
        route_candidates=route_candidates_tuple,
        delegated_route_candidates=delegated_tuple,
        jsonld_types=jsonld_types,
        structural_html=structural_html,
        same_host_redirect=same_host_redirect,
        external_search_gap=external_search_gap,
        next_action=next_action,
        reason_codes=tuple(sorted(reason_codes)),
        evidence_fingerprint=_fingerprint(fingerprint_payload),
        product_authority=False,
    )


def build_listing_booster_plan(
    evidence: ListingSurfaceEvidence,
    *,
    tavily_state: TavilyState,
) -> BoosterPlan:
    """Map deterministic Listing evidence into the canonical booster policy."""

    return build_booster_plan(
        surface=BoosterSurface.LISTING_DISCOVERY,
        tavily_state=tavily_state,
        deterministic_resolved=not evidence.booster_eligible,
        external_information_gap=evidence.external_search_gap,
    )


__all__ = [
    "LISTING_EVIDENCE_CONTRACT_VERSION",
    "ListingSurfaceEvidence",
    "analyze_listing_surface",
    "build_listing_booster_plan",
    "extract_jsonld_types",
]
