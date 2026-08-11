from __future__ import annotations

import json
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Iterable

from src.search_intelligence.product_v1_contenders import (
    is_germany_country,
    normalize_text,
)


GEOGRAPHY_IDENTITY_VERSION = "GEO-ID-001"
_LOCATION_LABELS = {
    "location",
    "job location",
    "standort",
    "arbeitsort",
    "einsatzort",
}
_REMOTE_TERMS = (
    "remote",
    "telecommute",
    "home office",
    "homeoffice",
)
_GERMANY_LOCATION_TERMS = (
    "germany",
    "deutschland",
)


@dataclass(frozen=True)
class LocationEvidence:
    value: str
    source: str

    def to_json(self) -> dict[str, str]:
        return {"value": self.value, "source": self.source}


@dataclass(frozen=True)
class GeographyIdentityAssessment:
    status: str
    reason: str
    evidence: tuple[LocationEvidence, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "version": GEOGRAPHY_IDENTITY_VERSION,
            "status": self.status,
            "reason": self.reason,
            "location_evidence": [item.to_json() for item in self.evidence],
        }


class _JobLocationParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_nodes: list[str] = []
        self.json_ld_chunks: list[str] = []
        self._inside_json_ld = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "script":
            return
        attributes = {key.casefold(): (value or "") for key, value in attrs}
        self._inside_json_ld = (
            attributes.get("type", "").casefold() == "application/ld+json"
        )

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script":
            self._inside_json_ld = False

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split()).strip()
        if not value:
            return
        if self._inside_json_ld:
            self.json_ld_chunks.append(value)
        else:
            self.text_nodes.append(value)


def _country_name(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("name", "addressCountry"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return ""


def _location_from_address(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    address = value.get("address") if isinstance(value.get("address"), dict) else value
    parts: list[str] = []
    for key in ("addressLocality", "addressRegion"):
        part = address.get(key)
        if isinstance(part, str) and part.strip():
            parts.append(part.strip())
    country = _country_name(address.get("addressCountry"))
    if country:
        parts.append(country)
    return ", ".join(dict.fromkeys(parts))


def _walk_json(value: object) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_json(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_json(nested)


def _structured_location_evidence(chunks: Iterable[str]) -> list[LocationEvidence]:
    evidence: list[LocationEvidence] = []
    for chunk in chunks:
        try:
            payload = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        for node in _walk_json(payload):
            node_type = node.get("@type")
            types = {node_type} if isinstance(node_type, str) else set(node_type or ())
            if "JobPosting" not in types:
                continue

            locations = node.get("jobLocation")
            if not isinstance(locations, list):
                locations = [locations] if locations is not None else []
            for location in locations:
                value = _location_from_address(location)
                if value:
                    evidence.append(LocationEvidence(value=value, source="json_ld_job_location"))

            applicant_locations = node.get("applicantLocationRequirements")
            if not isinstance(applicant_locations, list):
                applicant_locations = (
                    [applicant_locations]
                    if applicant_locations is not None
                    else []
                )
            for location in applicant_locations:
                value = _country_name(location)
                if value:
                    evidence.append(
                        LocationEvidence(
                            value=value,
                            source="json_ld_applicant_location_requirement",
                        )
                    )

            location_type = node.get("jobLocationType")
            if isinstance(location_type, str) and location_type.strip():
                evidence.append(
                    LocationEvidence(
                        value=location_type.strip(),
                        source="json_ld_job_location_type",
                    )
                )
    return evidence


def extract_job_location_evidence(response_text: str) -> tuple[LocationEvidence, ...]:
    parser = _JobLocationParser()
    try:
        parser.feed(response_text)
    except Exception:  # HTMLParser is best-effort evidence extraction only.
        parser = _JobLocationParser()

    evidence = _structured_location_evidence(parser.json_ld_chunks)
    nodes = parser.text_nodes
    for index, node in enumerate(nodes[:-1]):
        if normalize_text(node) not in _LOCATION_LABELS:
            continue
        candidate = nodes[index + 1].strip()
        if 1 < len(candidate) <= 160:
            evidence.append(LocationEvidence(value=candidate, source="labelled_page_location"))

    deduplicated: list[LocationEvidence] = []
    seen: set[tuple[str, str]] = set()
    for item in evidence:
        key = (normalize_text(item.value), item.source)
        if not key[0] or key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)
    return tuple(deduplicated)


def _contains_phrase(value: str, phrase: str) -> bool:
    normalized = normalize_text(value)
    target = normalize_text(phrase)
    return bool(target and f" {target} " in f" {normalized} ")


def _city_aliases(city: str | None) -> tuple[str, ...]:
    normalized = normalize_text(city)
    if not normalized:
        return ()
    if normalized == "hannover":
        return ("hannover", "hanover")
    if normalized == "hanover":
        return ("hanover", "hannover")
    return (normalized,)


def _has_germany_signal(value: str) -> bool:
    normalized = normalize_text(value)
    if normalized == "de":
        return True
    return any(_contains_phrase(normalized, term) for term in _GERMANY_LOCATION_TERMS)


def _has_remote_signal(value: str) -> bool:
    return any(_contains_phrase(value, term) for term in _REMOTE_TERMS)


def assess_current_geography_identity(
    *,
    city: str | None,
    country: str | None,
    geography_bucket: str,
    response_text: str,
) -> GeographyIdentityAssessment:
    evidence = extract_job_location_evidence(response_text)
    if not evidence:
        return GeographyIdentityAssessment(
            status="evidence_required",
            reason="current_detail_has_no_explicit_job_location_evidence",
            evidence=(),
        )

    city_aliases = _city_aliases(city)
    expected_germany = is_germany_country(country) or geography_bucket in {
        "hannover_explicit",
        "germany_remote",
        "commute_observed_acceptable",
        "commute_or_geography_review_required",
    }

    saw_ambiguous_remote = False
    for item in evidence:
        value = item.value
        if any(_contains_phrase(value, alias) for alias in city_aliases):
            return GeographyIdentityAssessment(
                status="compatible",
                reason="current_detail_location_matches_persisted_city",
                evidence=evidence,
            )

        has_germany = _has_germany_signal(value)
        has_remote = _has_remote_signal(value)
        if geography_bucket == "germany_remote" and (has_germany or has_remote):
            return GeographyIdentityAssessment(
                status="compatible",
                reason="current_detail_location_compatible_with_germany_remote_policy",
                evidence=evidence,
            )
        if expected_germany and has_germany and has_remote:
            return GeographyIdentityAssessment(
                status="compatible",
                reason="current_detail_explicit_germany_remote_is_product_admissible",
                evidence=evidence,
            )
        if has_remote and not has_germany:
            saw_ambiguous_remote = True

    if saw_ambiguous_remote:
        return GeographyIdentityAssessment(
            status="evidence_required",
            reason="current_detail_remote_location_lacks_country_identity",
            evidence=evidence,
        )

    return GeographyIdentityAssessment(
        status="conflict",
        reason="current_detail_explicit_location_conflicts_with_persisted_geography",
        evidence=evidence,
    )
