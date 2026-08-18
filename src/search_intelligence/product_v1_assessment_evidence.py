"""Source-neutral deterministic evidence extraction for Product V1 assessment.

This module converts exact bounded employer-origin job text into conservative
assessment evidence. It deliberately separates the observed source phrase from
the canonical Product V1 value. No provider/model output, Candidate Fact,
ranking score, hard-filter pass or product authority is created here.

Unsupported or contradictory evidence remains ``unknown``. In particular,
years of experience or qualitative experience wording such as ``extensive
professional experience`` never becomes a seniority label by itself.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from html import unescape
import re
from typing import Any, Iterable, Mapping


ASSESSMENT_EVIDENCE_FIELDS = (
    "employment_type",
    "required_languages",
    "weekly_hours",
    "work_model",
    "title_seniority",
    "requirements_seniority",
)

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class AssessmentEvidenceReference:
    """One exact observed source phrase and its deterministic canonical value."""

    field: str
    source_url: str
    observed_value: str
    canonical_value: str
    evidence: str
    span_start: int
    span_end: int

    def canonical_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProductV1AssessmentEvidence:
    """Conservative source-grounded evidence for Product V1 hard-filter inputs."""

    source_url: str
    description_sha256: str
    employment_type: str
    required_languages: tuple[str, ...]
    weekly_hours_min: float | None
    weekly_hours_max: float | None
    work_model: str
    title_seniority: str
    requirements_seniority: str
    references: tuple[AssessmentEvidenceReference, ...]
    conflicted_fields: tuple[str, ...]

    @property
    def unresolved_fields(self) -> tuple[str, ...]:
        unresolved: list[str] = []
        if self.employment_type == "unknown":
            unresolved.append("employment_type")
        if not self.required_languages:
            unresolved.append("required_languages")
        if self.weekly_hours_min is None and self.weekly_hours_max is None:
            unresolved.append("weekly_hours")
        if self.work_model == "unknown":
            unresolved.append("work_model")
        if self.title_seniority == "unknown":
            unresolved.append("title_seniority")
        if self.requirements_seniority == "unknown":
            unresolved.append("requirements_seniority")
        return tuple(unresolved)

    def assessment_patch(self) -> dict[str, Any]:
        """Return only Product V1 assessment columns owned by source evidence.

        The patch is safe for a new/unknown assessment row. A persistence layer
        that merges with an existing assessment must still reject conflicting
        observed state instead of overwriting it.
        """

        hours_observed = self.weekly_hours_min is not None or self.weekly_hours_max is not None
        seniority_observed = self.requirements_seniority != "unknown"
        return {
            "employment_type": self.employment_type,
            "employment_evidence_status": (
                "observed" if self.employment_type != "unknown" else "unknown"
            ),
            "required_languages": list(self.required_languages),
            "language_evidence_status": (
                "observed" if self.required_languages else "unknown"
            ),
            "weekly_hours_min": self.weekly_hours_min,
            "weekly_hours_max": self.weekly_hours_max,
            "weekly_hours_evidence_status": (
                "observed" if hours_observed else "unknown"
            ),
            "work_model": self.work_model,
            "title_seniority": self.title_seniority,
            "requirements_seniority": self.requirements_seniority,
            "seniority_evidence_status": (
                "observed" if seniority_observed else "unknown"
            ),
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "source_url": self.source_url,
            "description_sha256": self.description_sha256,
            "employment_type": self.employment_type,
            "required_languages": list(self.required_languages),
            "weekly_hours_min": self.weekly_hours_min,
            "weekly_hours_max": self.weekly_hours_max,
            "work_model": self.work_model,
            "title_seniority": self.title_seniority,
            "requirements_seniority": self.requirements_seniority,
            "references": [reference.canonical_payload() for reference in self.references],
            "conflicted_fields": list(self.conflicted_fields),
            "unresolved_fields": list(self.unresolved_fields),
            "assessment_patch": self.assessment_patch(),
            "authority": {
                "source_evidence_only": True,
                "candidate_fact_authority": False,
                "capability_fit_authority": False,
                "hard_filter_authority": False,
                "ranking_authority": False,
                "product_authority": False,
            },
        }


def normalize_job_text(value: object) -> str:
    """Normalize stored employer-origin text without adding semantic content."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("job description is missing")
    text = unescape(value)
    text = _TAG_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    if not text:
        raise ValueError("job description is empty after normalization")
    return text


def _reference(
    *,
    field: str,
    source_url: str,
    text: str,
    match: re.Match[str],
    canonical_value: str,
    observed_group: str | None = None,
) -> AssessmentEvidenceReference:
    observed_value = (
        match.group(observed_group) if observed_group is not None else match.group(0)
    )
    return AssessmentEvidenceReference(
        field=field,
        source_url=source_url,
        observed_value=observed_value,
        canonical_value=canonical_value,
        evidence=match.group(0),
        span_start=match.start(),
        span_end=match.end(),
    )


def _collect_pattern_references(
    *,
    field: str,
    source_url: str,
    text: str,
    patterns: Iterable[tuple[str, re.Pattern[str]]],
) -> list[AssessmentEvidenceReference]:
    references: list[AssessmentEvidenceReference] = []
    occupied: set[tuple[int, int, str]] = set()
    for canonical_value, pattern in patterns:
        for match in pattern.finditer(text):
            key = (match.start(), match.end(), canonical_value)
            if key in occupied:
                continue
            occupied.add(key)
            references.append(
                _reference(
                    field=field,
                    source_url=source_url,
                    text=text,
                    match=match,
                    canonical_value=canonical_value,
                )
            )
    return references


def _resolve_scalar(
    references: Iterable[AssessmentEvidenceReference],
) -> tuple[str, bool]:
    values = {reference.canonical_value for reference in references}
    if not values:
        return "unknown", False
    if len(values) != 1:
        return "unknown", True
    return next(iter(values)), False


_EMPLOYMENT_PATTERNS = (
    (
        "permanent",
        re.compile(
            r"\b(?:permanent\s+(?:employment|position|contract|role)|"
            r"unbefristet(?:e[rsnm]?\s+(?:anstellung|vertrag|position))?|festanstellung)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "fixed_term",
        re.compile(
            r"\b(?:fixed[- ]term\s+(?:employment|position|contract|role)|"
            r"befristet(?:e[rsnm]?\s+(?:anstellung|vertrag|position))?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "temporary",
        re.compile(r"\b(?:temporary\s+(?:employment|position|contract|role)|zeitarbeit)\b", re.IGNORECASE),
    ),
    (
        "freelance",
        re.compile(r"\b(?:freelance|freelancer|freiberuflich)\b", re.IGNORECASE),
    ),
    (
        "internship",
        re.compile(r"\b(?:internship|intern|praktikum|praktikant(?:in)?)\b", re.IGNORECASE),
    ),
    (
        "trainee",
        re.compile(r"\btrainee(?:programm|program)?\b", re.IGNORECASE),
    ),
)

_LANGUAGE_PATTERNS: Mapping[str, tuple[re.Pattern[str], ...]] = {
    "de": (
        re.compile(
            r"\b(?:fluent|business[- ]fluent|very good|excellent)\s+(?:written\s+and\s+spoken\s+)?german\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bgerman\s+(?:language\s+)?(?:skills?\s+)?(?:at\s+)?(?:level\s+)?(?:b2|c1|c2)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:fließend(?:e[rsnm]?)?|verhandlungssicher(?:e[rsnm]?)?|sehr\s+gute[rsnm]?)\s+deutsch(?:kenntnisse)?\b",
            re.IGNORECASE,
        ),
        re.compile(r"\bdeutsch(?:kenntnisse)?\s+(?:auf\s+)?(?:b2|c1|c2)[- ]?niveau\b", re.IGNORECASE),
    ),
    "en": (
        re.compile(
            r"\b(?:fluent|business[- ]fluent|very good|excellent)\s+(?:written\s+and\s+spoken\s+)?english\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\benglish\s+(?:language\s+)?(?:skills?\s+)?(?:at\s+)?(?:level\s+)?(?:b2|c1|c2)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:fließend(?:e[rsnm]?)?|verhandlungssicher(?:e[rsnm]?)?|sehr\s+gute[rsnm]?)\s+englisch(?:kenntnisse)?\b",
            re.IGNORECASE,
        ),
        re.compile(r"\benglisch(?:kenntnisse)?\s+(?:auf\s+)?(?:b2|c1|c2)[- ]?niveau\b", re.IGNORECASE),
    ),
}

_LANGUAGE_PAIR_PATTERNS = (
    re.compile(
        r"\b(?:fluent|business[- ]fluent|very good|excellent)\s+(?:in\s+)?(?:german\s+(?:and|&)\s+english|english\s+(?:and|&)\s+german)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:fließend(?:e[rsnm]?)?|verhandlungssicher(?:e[rsnm]?)?|sehr\s+gute[rsnm]?)\s+(?:deutsch\s+(?:und|&)\s+englisch|englisch\s+(?:und|&)\s+deutsch)\b",
        re.IGNORECASE,
    ),
)

_WORK_MODEL_PATTERNS = (
    (
        "hybrid",
        re.compile(r"\bhybrid(?:\s+(?:work|working|model|setup|arrangement))?\b", re.IGNORECASE),
    ),
    (
        "remote",
        re.compile(
            r"\b(?:(?:fully|100\s*%)\s+remote|remote\s+(?:work|working|position|role))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "onsite",
        re.compile(r"\b(?:on[- ]?site|onsite|vor\s+ort)\b", re.IGNORECASE),
    ),
)

_TITLE_SENIORITY_PATTERNS = (
    ("principal", re.compile(r"\bprincipal\b", re.IGNORECASE)),
    ("lead", re.compile(r"\blead\b", re.IGNORECASE)),
    ("senior", re.compile(r"\b(?:senior|sr\.)\b", re.IGNORECASE)),
    ("junior", re.compile(r"\b(?:junior|jr\.)\b", re.IGNORECASE)),
    ("mid", re.compile(r"\b(?:mid[- ]level|intermediate)\b", re.IGNORECASE)),
)

_REQUIREMENTS_SENIORITY_PATTERNS = (
    (
        "principal",
        re.compile(
            r"\bprincipal[- ]level\b|\bprincipal\s+(?:profile|candidate|professional|engineer|developer|specialist|role)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "lead",
        re.compile(
            r"\blead[- ]level\b|\blead\s+(?:profile|candidate|professional|engineer|developer|specialist|role)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "senior",
        re.compile(
            r"\bsenior[- ]level\b|\bsenior\s+(?:profile|candidate|professional|engineer|developer|specialist|role)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "junior",
        re.compile(
            r"\bjunior[- ]level\b|\bjunior\s+(?:profile|candidate|professional|engineer|developer|specialist|role)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "mid",
        re.compile(r"\bmid[- ]level\b", re.IGNORECASE),
    ),
)

_WEEKLY_HOURS_PATTERNS = (
    re.compile(
        r"\b(?P<min>\d{1,2}(?:[.,]\d+)?)\s*(?:-|–|—|to|bis)\s*"
        r"(?P<max>\d{1,2}(?:[.,]\d+)?)\s*(?:hours?|hrs?|stunden|wochenstunden)"
        r"(?:\s*(?:per\s+week|weekly|pro\s+woche|wöchentlich|/\s*woche))?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<single>\d{1,2}(?:[.,]\d+)?)\s*(?:hours?|hrs?|stunden)\s*"
        r"(?:per\s+week|weekly|pro\s+woche|wöchentlich|/\s*woche)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?P<single>\d{1,2}(?:[.,]\d+)?)\s*wochenstunden\b", re.IGNORECASE),
)


def _number(value: str) -> float:
    return float(value.replace(",", "."))


def _extract_weekly_hours(
    *,
    source_url: str,
    text: str,
) -> tuple[float | None, float | None, list[AssessmentEvidenceReference], bool]:
    candidates: list[tuple[float, float, AssessmentEvidenceReference]] = []
    occupied: set[tuple[int, int]] = set()
    for pattern in _WEEKLY_HOURS_PATTERNS:
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if span in occupied:
                continue
            occupied.add(span)
            if match.groupdict().get("single") is not None:
                minimum = maximum = _number(match.group("single"))
            else:
                minimum = _number(match.group("min"))
                maximum = _number(match.group("max"))
            if minimum <= 0 or maximum < minimum or maximum > 80:
                continue
            canonical = f"{minimum:g}-{maximum:g}"
            candidates.append(
                (
                    minimum,
                    maximum,
                    _reference(
                        field="weekly_hours",
                        source_url=source_url,
                        text=text,
                        match=match,
                        canonical_value=canonical,
                    ),
                )
            )
    values = {(minimum, maximum) for minimum, maximum, _ in candidates}
    references = [reference for _, _, reference in candidates]
    if not values:
        return None, None, references, False
    if len(values) != 1:
        return None, None, references, True
    minimum, maximum = next(iter(values))
    return minimum, maximum, references, False


def extract_product_v1_assessment_evidence(
    *,
    description: object,
    title: object,
    source_url: str,
) -> ProductV1AssessmentEvidence:
    """Extract generic deterministic Product V1 assessment evidence.

    ``source_url`` identifies the already-authoritative employer-origin detail
    source. This function performs no network request and does not validate URL
    authority itself.
    """

    if not isinstance(title, str) or not title.strip():
        raise ValueError("job title is missing")
    if not isinstance(source_url, str) or not source_url.strip():
        raise ValueError("source_url is missing")

    text = normalize_job_text(description)
    references: list[AssessmentEvidenceReference] = []
    conflicts: set[str] = set()

    employment_references = _collect_pattern_references(
        field="employment_type",
        source_url=source_url,
        text=text,
        patterns=_EMPLOYMENT_PATTERNS,
    )
    employment_type, employment_conflict = _resolve_scalar(employment_references)
    references.extend(employment_references)
    if employment_conflict:
        conflicts.add("employment_type")

    language_references: list[AssessmentEvidenceReference] = []
    languages: set[str] = set()
    for pair_pattern in _LANGUAGE_PAIR_PATTERNS:
        for match in pair_pattern.finditer(text):
            for language in ("de", "en"):
                languages.add(language)
                language_references.append(
                    _reference(
                        field="required_languages",
                        source_url=source_url,
                        text=text,
                        match=match,
                        canonical_value=language,
                    )
                )
    for language, patterns in _LANGUAGE_PATTERNS.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                languages.add(language)
                language_references.append(
                    _reference(
                        field="required_languages",
                        source_url=source_url,
                        text=text,
                        match=match,
                        canonical_value=language,
                    )
                )
    references.extend(language_references)

    weekly_min, weekly_max, weekly_references, weekly_conflict = _extract_weekly_hours(
        source_url=source_url,
        text=text,
    )
    references.extend(weekly_references)
    if weekly_conflict:
        conflicts.add("weekly_hours")

    work_model_references = _collect_pattern_references(
        field="work_model",
        source_url=source_url,
        text=text,
        patterns=_WORK_MODEL_PATTERNS,
    )
    work_model, work_model_conflict = _resolve_scalar(work_model_references)
    references.extend(work_model_references)
    if work_model_conflict:
        conflicts.add("work_model")

    title_references = _collect_pattern_references(
        field="title_seniority",
        source_url=source_url,
        text=title.strip(),
        patterns=_TITLE_SENIORITY_PATTERNS,
    )
    title_seniority, title_conflict = _resolve_scalar(title_references)
    # Title evidence has offsets in the title, not the normalized description.
    # Keep it separately grounded by replacing the evidence reference source text
    # semantics with the exact title phrase; consumers must use the field marker.
    references.extend(title_references)
    if title_conflict:
        conflicts.add("title_seniority")

    requirements_references = _collect_pattern_references(
        field="requirements_seniority",
        source_url=source_url,
        text=text,
        patterns=_REQUIREMENTS_SENIORITY_PATTERNS,
    )
    requirements_seniority, requirements_conflict = _resolve_scalar(
        requirements_references
    )
    references.extend(requirements_references)
    if requirements_conflict:
        conflicts.add("requirements_seniority")

    # Deliberately no fallback from years/extensive experience to seniority.

    return ProductV1AssessmentEvidence(
        source_url=source_url.strip(),
        description_sha256=sha256(text.encode("utf-8")).hexdigest(),
        employment_type=employment_type,
        required_languages=tuple(sorted(languages)),
        weekly_hours_min=weekly_min,
        weekly_hours_max=weekly_max,
        work_model=work_model,
        title_seniority=title_seniority,
        requirements_seniority=requirements_seniority,
        references=tuple(references),
        conflicted_fields=tuple(sorted(conflicts)),
    )
