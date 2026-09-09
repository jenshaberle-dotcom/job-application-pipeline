"""Generic, local-only job-detail evidence extraction.

This module intentionally knows nothing about individual employers or job portals.
It projects public job-detail HTML into a bounded normalized evidence record using
local open-source parsers only:

* ``extruct`` for schema.org JSON-LD / Microdata;
* ``trafilatura`` for a bounded main-text fallback when structured description
  evidence is absent.

No source HTML is returned or persisted by this module. The caller receives only
normalized fields and a bounded text excerpt suitable for downstream evidence
and relevance processing.
"""

from __future__ import annotations

from copy import deepcopy
from html import unescape
from html.parser import HTMLParser
from typing import Any, Iterable

import extruct
from trafilatura import extract as extract_main_text

EVIDENCE_SCHEMA = "generic_job_detail_evidence_v1"
MAX_SCALAR_CHARS = 1_000
MAX_DESCRIPTION_CHARS = 4_000
MAX_SKILLS_CHARS = 2_000
MAX_LOCATION_CHARS = 500


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in {"script", "style", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _normalize_space(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(unescape(value).split()).strip()


def _bounded(value: object, limit: int = MAX_SCALAR_CHARS) -> str:
    text = _normalize_space(value)
    if not text:
        return ""
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0].strip()
    return clipped or text[:limit]


def _html_to_text(value: object, *, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    parser = _VisibleTextParser()
    try:
        parser.feed(value)
    except Exception:
        return _bounded(value, limit)
    return _bounded(" ".join(parser.parts), limit)


def _iter_mappings(value: object) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_mappings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_mappings(nested)


def _type_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _is_job_posting(value: dict[str, Any]) -> bool:
    raw_types = value.get("@type", value.get("type"))
    for raw_type in _type_values(raw_types):
        normalized = raw_type.rstrip("/").rsplit("/", 1)[-1].casefold()
        if normalized == "jobposting":
            return True
    return False


def _properties(value: dict[str, Any]) -> dict[str, Any]:
    props = value.get("properties")
    if isinstance(props, dict):
        return props
    return value


def _first_scalar(value: object, *, limit: int = MAX_SCALAR_CHARS) -> str:
    if isinstance(value, list):
        for item in value:
            result = _first_scalar(item, limit=limit)
            if result:
                return result
        return ""
    if isinstance(value, dict):
        for key in ("@value", "value", "name"):
            if key in value:
                result = _first_scalar(value[key], limit=limit)
                if result:
                    return result
        return ""
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return _bounded(str(value), limit)
    return ""


def _schema_value(value: dict[str, Any], key: str) -> object:
    props = _properties(value)
    return props.get(key)


def _organization_name(value: object) -> str:
    if isinstance(value, list):
        for item in value:
            result = _organization_name(item)
            if result:
                return result
        return ""
    if isinstance(value, dict):
        return _first_scalar(_schema_value(value, "name"))
    return _first_scalar(value)


def _country_text(value: object) -> str:
    if isinstance(value, dict):
        return _first_scalar(_schema_value(value, "name")) or _first_scalar(value)
    return _first_scalar(value)


def _location_strings(value: object) -> list[str]:
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_location_strings(item))
        return list(dict.fromkeys(item for item in result if item))
    if isinstance(value, str):
        text = _bounded(value, MAX_LOCATION_CHARS)
        return [text] if text else []
    if not isinstance(value, dict):
        return []

    props = _properties(value)
    name = _first_scalar(props.get("name"), limit=MAX_LOCATION_CHARS)
    address = props.get("address")
    address_props = _properties(address) if isinstance(address, dict) else {}

    components = [
        _first_scalar(address_props.get("addressLocality"), limit=MAX_LOCATION_CHARS),
        _first_scalar(address_props.get("addressRegion"), limit=MAX_LOCATION_CHARS),
        _first_scalar(address_props.get("postalCode"), limit=MAX_LOCATION_CHARS),
        _country_text(address_props.get("addressCountry")),
    ]
    components = list(dict.fromkeys(item for item in components if item))
    combined = " | ".join(components)

    result: list[str] = []
    if name:
        result.append(name)
    if combined and combined not in result:
        result.append(combined)
    return result


def _string_list(value: object, *, limit: int = MAX_SCALAR_CHARS) -> list[str]:
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_string_list(item, limit=limit))
        return list(dict.fromkeys(item for item in result if item))
    if isinstance(value, dict):
        scalar = _first_scalar(value, limit=limit)
        return [scalar] if scalar else []
    scalar = _first_scalar(value, limit=limit)
    if not scalar:
        return []
    if "," in scalar:
        values = [_bounded(item, limit) for item in scalar.split(",")]
        return list(dict.fromkeys(item for item in values if item))
    return [scalar]


def _remote_from_job_location_type(value: object) -> bool | None:
    values = _string_list(value)
    if not values:
        return None
    normalized = " ".join(values).casefold()
    if any(marker in normalized for marker in ("telecommute", "remote", "home office")):
        return True
    return False


def _candidate_score(value: dict[str, Any]) -> int:
    score = 0
    if _first_scalar(_schema_value(value, "title")):
        score += 4
    if _first_scalar(_schema_value(value, "description")):
        score += 3
    if _organization_name(_schema_value(value, "hiringOrganization")):
        score += 2
    if _location_strings(_schema_value(value, "jobLocation")):
        score += 2
    if _first_scalar(_schema_value(value, "datePosted")):
        score += 1
    return score


def _structured_job_posting(html: str, url: str) -> tuple[str | None, dict[str, Any] | None]:
    try:
        extracted = extruct.extract(
            html,
            base_url=url,
            syntaxes=["json-ld", "microdata"],
            uniform=False,
        )
    except Exception:
        return None, None

    candidates: list[tuple[int, int, str, dict[str, Any]]] = []
    syntax_order = {"json-ld": 0, "microdata": 1}
    for syntax in ("json-ld", "microdata"):
        for mapping in _iter_mappings(extracted.get(syntax, [])):
            if _is_job_posting(mapping):
                candidates.append(
                    (
                        -_candidate_score(mapping),
                        syntax_order[syntax],
                        syntax,
                        mapping,
                    )
                )
    if not candidates:
        return None, None
    candidates.sort(key=lambda row: (row[0], row[1]))
    _, _, syntax, mapping = candidates[0]
    return syntax, mapping


def extract_generic_job_detail_evidence(
    *,
    html: str,
    url: str,
    page_title: str = "",
) -> dict[str, Any]:
    """Extract bounded provider-neutral job evidence from already-fetched HTML."""

    syntax, posting = _structured_job_posting(html, url)
    methods: list[str] = []
    if syntax:
        methods.append(f"extruct:{syntax}")

    title = ""
    company_name = ""
    description = ""
    locations: list[str] = []
    applicant_locations: list[str] = []
    remote: bool | None = None
    employment_types: list[str] = []
    skills: list[str] = []
    date_posted = ""
    valid_through = ""
    identifier = ""

    if posting is not None:
        title = _first_scalar(_schema_value(posting, "title"))
        company_name = _organization_name(_schema_value(posting, "hiringOrganization"))
        description = _html_to_text(
            _first_scalar(_schema_value(posting, "description"), limit=50_000),
            limit=MAX_DESCRIPTION_CHARS,
        )
        locations = _location_strings(_schema_value(posting, "jobLocation"))
        applicant_locations = _location_strings(
            _schema_value(posting, "applicantLocationRequirements")
        )
        remote = _remote_from_job_location_type(
            _schema_value(posting, "jobLocationType")
        )
        employment_types = _string_list(_schema_value(posting, "employmentType"))
        skills = _string_list(
            _schema_value(posting, "skills"),
            limit=MAX_SKILLS_CHARS,
        )
        date_posted = _first_scalar(_schema_value(posting, "datePosted"))
        valid_through = _first_scalar(_schema_value(posting, "validThrough"))
        identifier = _first_scalar(_schema_value(posting, "identifier"))

    description_source = syntax if description else None
    if not description:
        try:
            extracted_text = extract_main_text(
                html,
                url=url,
                output_format="txt",
                include_comments=False,
                include_tables=True,
                include_links=False,
                include_images=False,
                favor_precision=True,
                deduplicate=True,
            )
        except Exception:
            extracted_text = None
        description = _bounded(extracted_text, MAX_DESCRIPTION_CHARS)
        if description:
            methods.append("trafilatura:main_text")
            description_source = "trafilatura"

    if not title:
        title = _bounded(page_title)

    return {
        "schema": EVIDENCE_SCHEMA,
        "methods": methods,
        "structured_jobposting_found": posting is not None,
        "structured_source": syntax,
        "title": title or None,
        "company_name": company_name or None,
        "description_excerpt": description or None,
        "description_source": description_source,
        "locations": locations,
        "applicant_locations": applicant_locations,
        "remote": remote,
        "employment_types": employment_types,
        "skills": skills,
        "date_posted": date_posted or None,
        "valid_through": valid_through or None,
        "identifier": identifier or None,
        "raw_html_persisted": False,
    }


def project_detail_evidence_into_raw_data(
    raw_data: dict[str, Any],
    evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Project generic evidence into the existing canonical raw-job shape."""

    normalized = deepcopy(raw_data)
    if not isinstance(evidence, dict) or evidence.get("schema") != EVIDENCE_SCHEMA:
        return normalized

    job = normalized.get("job")
    if not isinstance(job, dict):
        job = {}
        normalized["job"] = job

    result_card = normalized.get("result_card")
    if not isinstance(result_card, dict):
        result_card = {}
        normalized["result_card"] = result_card

    title = _bounded(evidence.get("title"))
    if title:
        job["title"] = title
        result_card["title"] = title

    company_name = _bounded(evidence.get("company_name"))
    if company_name:
        job["company_name"] = company_name
        result_card["company_name"] = company_name

    description = _bounded(evidence.get("description_excerpt"), MAX_DESCRIPTION_CHARS)
    if description:
        job["description"] = description

    locations = _string_list(evidence.get("locations"), limit=MAX_LOCATION_CHARS)
    applicant_locations = _string_list(
        evidence.get("applicant_locations"), limit=MAX_LOCATION_CHARS
    )
    if locations:
        job["location"] = " | ".join(locations)
        job["locations"] = locations
    if applicant_locations:
        job["applicant_locations"] = applicant_locations

    skills = _string_list(evidence.get("skills"), limit=MAX_SKILLS_CHARS)
    if skills:
        job["skills"] = skills

    metadata = job.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    remote = evidence.get("remote")
    if remote is True:
        metadata["workplace_type"] = "remote"
    elif remote is False:
        metadata["workplace_type"] = "onsite_or_unspecified"
    employment_types = _string_list(evidence.get("employment_types"))
    if employment_types:
        metadata["employment_types"] = employment_types
    for source_key, target_key in (
        ("date_posted", "date_posted"),
        ("valid_through", "valid_through"),
        ("identifier", "structured_identifier"),
    ):
        value = _bounded(evidence.get(source_key))
        if value:
            metadata[target_key] = value
    if metadata:
        job["metadata"] = metadata

    normalized["detail_evidence"] = deepcopy(evidence)
    return normalized


__all__ = [
    "EVIDENCE_SCHEMA",
    "extract_generic_job_detail_evidence",
    "project_detail_evidence_into_raw_data",
]
