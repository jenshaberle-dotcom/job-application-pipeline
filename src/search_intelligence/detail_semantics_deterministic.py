"""Generic deterministic Detail Semantics extraction.

This module owns the provider-free D0 station for already-supported job-detail
pages. It prefers same-page structured JobPosting evidence and strong title or
label context before bounded lexical fallbacks. It never grants product
authority and never uses employer-specific branches.
"""

from __future__ import annotations

from html.parser import HTMLParser
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from src.search_intelligence.detail_semantics_gap import SemanticEvidenceReference

ROLE_TERMS = (
    "data engineer",
    "analytics engineer",
    "data analyst",
    "business analyst",
    "business intelligence analyst",
    "business intelligence",
    "data scientist",
    "data architect",
    "machine learning engineer",
    "ml engineer",
    "ai engineer",
    "software engineer",
    "software developer",
    "product owner",
    "product manager",
)
SENIORITY_TERMS = (
    "junior",
    "senior",
    "lead",
    "principal",
    "staff",
    "graduate",
    "entry level",
    "berufseinsteiger",
)
SKILL_TERMS = (
    "python",
    "sql",
    "databricks",
    "spark",
    "pyspark",
    "azure",
    "aws",
    "gcp",
    "power bi",
    "tableau",
    "snowflake",
    "dbt",
    "airflow",
    "kafka",
    "docker",
    "kubernetes",
    "terraform",
    "pytorch",
    "tensorflow",
    "scikit-learn",
    "machine learning",
    "generative ai",
    "genai",
)
REMOTE_TERMS = (
    "remote",
    "hybrid",
    "homeoffice",
    "home office",
    "mobiles arbeiten",
    "mobile work",
    "work from home",
    "remote work",
    "telearbeit",
)
WIDE_LOCATION_TERMS = ("deutschland", "germany", "bundesweit", "deutschlandweit")


class _JsonLdExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self._parts: list[str] = []
        self.documents: list[object] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        attrs_map = {str(key).casefold(): str(value or "") for key, value in attrs}
        if attrs_map.get("type", "").split(";", 1)[0].strip().casefold() == "application/ld+json":
            self._capture = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "script" or not self._capture:
            return
        raw = "".join(self._parts).strip()
        self._capture = False
        self._parts = []
        if not raw:
            return
        try:
            self.documents.append(json.loads(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            return


def _iter_objects(value: object) -> Iterable[Mapping[str, object]]:
    if isinstance(value, Mapping):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _iter_objects(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_objects(item)


def _is_job_posting(value: Mapping[str, object]) -> bool:
    raw_type = value.get("@type")
    if isinstance(raw_type, str):
        return raw_type.casefold() == "jobposting"
    if isinstance(raw_type, list):
        return any(str(item).casefold() == "jobposting" for item in raw_type)
    return False


def extract_job_postings(html: str) -> tuple[Mapping[str, object], ...]:
    parser = _JsonLdExtractor()
    parser.feed(str(html or ""))
    return tuple(
        item
        for document in parser.documents
        for item in _iter_objects(document)
        if _is_job_posting(item)
    )


def _pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(str(term).strip())
    if not escaped:
        return re.compile(r"(?!)")
    prefix = r"(?<![\w])" if str(term)[0].isalnum() else ""
    suffix = r"(?![\w])" if str(term)[-1].isalnum() else ""
    return re.compile(prefix + escaped + suffix, re.IGNORECASE)


def _reference_for_term(
    *, field: str, term: str, text: str, detail_url: str
) -> SemanticEvidenceReference | None:
    match = _pattern(term).search(text)
    if match is None:
        return None
    evidence = text[match.start() : match.end()]
    return SemanticEvidenceReference(
        field=field,
        source_url=detail_url,
        evidence=evidence,
        value=evidence,
        span_start=match.start(),
        span_end=match.end(),
    )


def _reference_for_exact_value(
    *, field: str, value: str, text: str, detail_url: str
) -> SemanticEvidenceReference | None:
    cleaned = " ".join(str(value or "").split()).strip()
    if not cleaned:
        return None
    return _reference_for_term(field=field, term=cleaned, text=text, detail_url=detail_url)


def _first_reference(
    *, field: str, terms: Sequence[str], text: str, detail_url: str
) -> SemanticEvidenceReference | None:
    for term in terms:
        reference = _reference_for_term(field=field, term=term, text=text, detail_url=detail_url)
        if reference is not None:
            return reference
    return None


def _string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        cleaned = " ".join(value.split()).strip()
        return (cleaned,) if cleaned else ()
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_string_values(item))
        return tuple(result)
    return ()


def _job_location_values(job: Mapping[str, object]) -> tuple[str, ...]:
    locations = job.get("jobLocation")
    items = locations if isinstance(locations, list) else [locations]
    values: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        for key in ("name",):
            values.extend(_string_values(item.get(key)))
        address = item.get("address")
        if isinstance(address, Mapping):
            for key in ("addressLocality", "addressRegion", "addressCountry"):
                values.extend(_string_values(address.get(key)))
    return tuple(dict.fromkeys(value for value in values if value))


def _structured_skill_values(job: Mapping[str, object]) -> tuple[str, ...]:
    result: list[str] = []
    for raw in _string_values(job.get("skills")):
        pieces = [piece.strip() for piece in re.split(r"[,;\n]", raw) if piece.strip()]
        result.extend(pieces if len(pieces) > 1 else [raw])
    return tuple(dict.fromkeys(value for value in result if len(value) <= 120))


def _contextual_reference(
    *,
    field: str,
    terms: Sequence[str],
    text: str,
    detail_url: str,
    labels: Sequence[str],
    max_distance: int = 100,
) -> SemanticEvidenceReference | None:
    for term in terms:
        term_pattern = _pattern(term).pattern
        label_pattern = "|".join(re.escape(label) for label in labels)
        match = re.search(
            rf"(?:\b(?:{label_pattern})\b.{{0,{max_distance}}}?({term_pattern})|({term_pattern}).{{0,{max_distance}}}?\b(?:{label_pattern})\b)",
            text,
            re.IGNORECASE,
        )
        if match is None:
            continue
        group = 1 if match.group(1) is not None else 2
        start, end = match.span(group)
        evidence = text[start:end]
        return SemanticEvidenceReference(
            field=field,
            source_url=detail_url,
            evidence=evidence,
            value=evidence,
            span_start=start,
            span_end=end,
        )
    return None


def _title_reference(
    *, field: str, terms: Sequence[str], page_title: str, text: str, detail_url: str
) -> SemanticEvidenceReference | None:
    for term in terms:
        if _pattern(term).search(page_title or "") is None:
            continue
        reference = _reference_for_term(field=field, term=term, text=text, detail_url=detail_url)
        if reference is not None:
            return reference
    return None


def _put_scalar(
    fields: dict[str, object],
    references: list[SemanticEvidenceReference],
    field: str,
    reference: SemanticEvidenceReference | None,
) -> None:
    if reference is None or field in fields:
        return
    fields[field] = reference.value
    references.append(reference)


def deterministic_detail_semantics(
    *,
    html: str,
    text: str,
    page_title: str,
    detail_url: str,
    target_location: str,
    requested_fields: Sequence[str],
) -> tuple[dict[str, object], tuple[SemanticEvidenceReference, ...]]:
    """Extract strongly grounded semantics from one already-supported detail page."""

    requested = tuple(dict.fromkeys(str(item).strip().casefold() for item in requested_fields))
    fields: dict[str, object] = {}
    references: list[SemanticEvidenceReference] = []
    job_postings = extract_job_postings(html)

    if "role" in requested:
        for job in job_postings:
            titles = _string_values(job.get("title"))
            if not titles:
                continue
            reference = _reference_for_exact_value(
                field="role", value=titles[0], text=text, detail_url=detail_url
            )
            if reference is not None:
                _put_scalar(fields, references, "role", reference)
                break
        if "role" not in fields:
            _put_scalar(
                fields,
                references,
                "role",
                _title_reference(
                    field="role",
                    terms=ROLE_TERMS,
                    page_title=page_title,
                    text=text,
                    detail_url=detail_url,
                ),
            )
        if "role" not in fields:
            _put_scalar(
                fields,
                references,
                "role",
                _contextual_reference(
                    field="role",
                    terms=ROLE_TERMS,
                    text=text,
                    detail_url=detail_url,
                    labels=("position", "rolle", "role", "jobtitel", "job title", "stelle"),
                ),
            )

    if "seniority" in requested:
        _put_scalar(
            fields,
            references,
            "seniority",
            _title_reference(
                field="seniority",
                terms=SENIORITY_TERMS,
                page_title=page_title,
                text=text,
                detail_url=detail_url,
            ),
        )
        if "seniority" not in fields:
            _put_scalar(
                fields,
                references,
                "seniority",
                _contextual_reference(
                    field="seniority",
                    terms=SENIORITY_TERMS,
                    text=text,
                    detail_url=detail_url,
                    labels=(
                        "seniority",
                        "career level",
                        "karrierestufe",
                        "level",
                        "erfahrungslevel",
                    ),
                ),
            )

    if "skills" in requested:
        skill_values: list[str] = []
        for job in job_postings:
            for value in _structured_skill_values(job):
                reference = _reference_for_exact_value(
                    field="skills", value=value, text=text, detail_url=detail_url
                )
                if reference is None or reference.value is None:
                    continue
                normalized = str(reference.value).casefold()
                if normalized in {item.casefold() for item in skill_values}:
                    continue
                skill_values.append(str(reference.value))
                references.append(reference)
        for term in SKILL_TERMS:
            reference = _reference_for_term(
                field="skills", term=term, text=text, detail_url=detail_url
            )
            if reference is None or reference.value is None:
                continue
            normalized = str(reference.value).casefold()
            if normalized in {item.casefold() for item in skill_values}:
                continue
            skill_values.append(str(reference.value))
            references.append(reference)
        if skill_values:
            fields["skills"] = tuple(skill_values)

    if "location" in requested:
        for job in job_postings:
            for value in _job_location_values(job):
                reference = _reference_for_exact_value(
                    field="location", value=value, text=text, detail_url=detail_url
                )
                if reference is not None:
                    _put_scalar(fields, references, "location", reference)
                    break
            if "location" in fields:
                break
        if "location" not in fields:
            location_terms = tuple(
                item
                for item in (str(target_location or "").strip(), *WIDE_LOCATION_TERMS)
                if item
            )
            _put_scalar(
                fields,
                references,
                "location",
                _contextual_reference(
                    field="location",
                    terms=location_terms,
                    text=text,
                    detail_url=detail_url,
                    labels=(
                        "standort",
                        "arbeitsort",
                        "ort",
                        "location",
                        "city",
                        "office",
                        "workplace",
                    ),
                ),
            )
            if "location" not in fields:
                _put_scalar(
                    fields,
                    references,
                    "location",
                    _title_reference(
                        field="location",
                        terms=location_terms,
                        page_title=page_title,
                        text=text,
                        detail_url=detail_url,
                    ),
                )

    if "remote" in requested:
        for job in job_postings:
            for value in _string_values(job.get("jobLocationType")):
                if "telecommute" not in value.casefold() and "remote" not in value.casefold():
                    continue
                reference = _reference_for_exact_value(
                    field="remote", value=value, text=text, detail_url=detail_url
                )
                if reference is not None:
                    _put_scalar(fields, references, "remote", reference)
                    break
            if "remote" in fields:
                break
        if "remote" not in fields:
            _put_scalar(
                fields,
                references,
                "remote",
                _first_reference(
                    field="remote",
                    terms=REMOTE_TERMS,
                    text=text,
                    detail_url=detail_url,
                ),
            )

    return fields, tuple(references)


__all__ = [
    "ROLE_TERMS",
    "SENIORITY_TERMS",
    "SKILL_TERMS",
    "REMOTE_TERMS",
    "WIDE_LOCATION_TERMS",
    "deterministic_detail_semantics",
    "extract_job_postings",
]
