from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
from html import unescape
import re
from typing import Any, Mapping


REFRESH_KEY = "EON-PRODUCT-V1-SOURCE-EVIDENCE-REFRESH-001"
APPROVAL_TOKEN = REFRESH_KEY
DEFAULT_ASSESSED_BY = "deterministic_eon_source_evidence_refresh"
EXPECTED_READINESS = "hard_filter_evidence_required"
EXPECTED_HARD_FILTER_STATUS = "unknown"
EXPECTED_REQUIRED_LANGUAGES = ("de", "en")

ASSESSMENT_COLUMNS = (
    "silver_job_id",
    "origin_validation_status",
    "activity_status",
    "hard_filter_status",
    "profile_direction_score",
    "data_focus_score",
    "reliability_focus_score",
    "evidence_quality_score",
    "overall_quality_score",
    "work_model",
    "commute_minutes",
    "public_transport_quality",
    "ranking_factors",
    "explanations",
    "uncertainties",
    "policy_key",
    "policy_version",
    "assessed_by",
    "employment_type",
    "employment_evidence_status",
    "required_languages",
    "language_evidence_status",
    "weekly_hours_min",
    "weekly_hours_max",
    "weekly_hours_evidence_status",
    "salary_min_gross_eur",
    "salary_max_gross_eur",
    "salary_evidence_status",
    "title_seniority",
    "requirements_seniority",
    "capability_fit_status",
    "seniority_evidence_status",
)

SCORE_COLUMNS = (
    "profile_direction_score",
    "data_focus_score",
    "reliability_focus_score",
    "evidence_quality_score",
    "overall_quality_score",
)

ALLOWED_CHANGED_FIELDS = frozenset(
    {
        "work_model",
        "explanations",
        "uncertainties",
        "assessed_by",
        "required_languages",
        "language_evidence_status",
        "requirements_seniority",
        "seniority_evidence_status",
    }
)

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_LANGUAGE_WORD_RE = re.compile(r"\b(?:english|german)\b", re.IGNORECASE)
_FLUENCY_RE = re.compile(
    r"\b(?:fluent|fluently|fluency|business[- ]fluent|very good|"
    r"verhandlungssicher|fließend)\b",
    re.IGNORECASE,
)
_HYBRID_PATTERNS = (
    re.compile(r"\bhybrid\s+(?:work|working|model|setup|arrangement)s?\b", re.IGNORECASE),
    re.compile(r"\bwork(?:ing)?\s+(?:in\s+)?(?:a\s+)?hybrid\b", re.IGNORECASE),
)
_SENIORITY_PATTERNS = (
    re.compile(
        r"\b(?:several|multiple)\s+years(?:\s+of)?\s+"
        r"(?:relevant\s+|professional\s+|hands-on\s+)*experience\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bmany\s+years(?:\s+of)?\s+(?:professional\s+)?experience\b", re.IGNORECASE),
    re.compile(r"\bmehrjährig\w*\s+(?:relevant\w*\s+|beruflich\w*\s+)*erfahrung\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class EonSourceEvidence:
    required_languages: tuple[str, ...]
    language_evidence_text: str
    work_model: str
    work_model_evidence_text: str
    requirements_seniority: str
    seniority_evidence_text: str
    description_sha256: str

    def canonical_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_languages"] = list(self.required_languages)
        return payload


@dataclass(frozen=True)
class AssessmentRefresh:
    previous_payload: Mapping[str, Any]
    next_payload: Mapping[str, Any]
    source_evidence: EonSourceEvidence
    changed_fields: tuple[str, ...]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _list_of_mappings(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{label}[{index}] must be an object")
        result.append(dict(item))
    return result


def normalize_description(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("stored E.ON description is missing")
    text = unescape(value)
    text = _TAG_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    if not text:
        raise ValueError("stored E.ON description is empty after normalization")
    return text


def _context(text: str, start: int, end: int, radius: int = 140) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right].strip()


def _extract_language_evidence(text: str) -> str:
    lowered = text.casefold()
    english_positions = [match.start() for match in re.finditer(r"\benglish\b", lowered)]
    german_positions = [match.start() for match in re.finditer(r"\bgerman\b", lowered)]

    for english in english_positions:
        for german in german_positions:
            left = min(english, german)
            right = max(english, german) + len("german")
            if right - left > 180:
                continue
            window_left = max(0, left - 100)
            window_right = min(len(text), right + 100)
            window = text[window_left:window_right]
            if _LANGUAGE_WORD_RE.search(window) and _FLUENCY_RE.search(window):
                return window.strip()

    raise ValueError(
        "stored E.ON description does not explicitly evidence fluent German and English"
    )


def _extract_pattern_evidence(
    text: str,
    *,
    patterns: tuple[re.Pattern[str], ...],
    missing_message: str,
) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match is not None:
            return _context(text, match.start(), match.end())
    raise ValueError(missing_message)


def extract_eon_source_evidence(
    *,
    description: object,
    title: object,
) -> EonSourceEvidence:
    _require(isinstance(title, str) and bool(title.strip()), "stored E.ON title is missing")
    _require("(senior)" in title.casefold(), "bounded E.ON senior title marker is missing")
    text = normalize_description(description)

    language_text = _extract_language_evidence(text)
    hybrid_text = _extract_pattern_evidence(
        text,
        patterns=_HYBRID_PATTERNS,
        missing_message="stored E.ON description does not explicitly evidence hybrid work",
    )
    seniority_text = _extract_pattern_evidence(
        text,
        patterns=_SENIORITY_PATTERNS,
        missing_message=(
            "stored E.ON description does not explicitly evidence several years "
            "of professional experience"
        ),
    )

    return EonSourceEvidence(
        required_languages=EXPECTED_REQUIRED_LANGUAGES,
        language_evidence_text=language_text,
        work_model="hybrid",
        work_model_evidence_text=hybrid_text,
        requirements_seniority="senior",
        seniority_evidence_text=seniority_text,
        description_sha256=sha256(text.encode("utf-8")).hexdigest(),
    )


def canonical_assessment_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = {column: deepcopy(value.get(column)) for column in ASSESSMENT_COLUMNS}
    payload["ranking_factors"] = dict(
        _mapping(payload["ranking_factors"], "assessment.ranking_factors")
    )
    payload["explanations"] = _list_of_mappings(
        payload["explanations"],
        "assessment.explanations",
    )
    payload["uncertainties"] = _list_of_mappings(
        payload["uncertainties"],
        "assessment.uncertainties",
    )
    languages = payload["required_languages"]
    if not isinstance(languages, (list, tuple)) or not all(
        isinstance(item, str) for item in languages
    ):
        raise ValueError("assessment.required_languages must be a string array")
    payload["required_languages"] = list(languages)
    return payload


def _validate_preserved_boundaries(payload: Mapping[str, Any]) -> None:
    _require(payload.get("origin_validation_status") == "validated", "origin validation drift")
    _require(payload.get("activity_status") == "active", "activity status drift")
    _require(payload.get("hard_filter_status") == EXPECTED_HARD_FILTER_STATUS, "hard-filter status drift")
    _require(payload.get("employment_type") == "permanent", "employment type drift")
    _require(
        payload.get("employment_evidence_status") == "observed",
        "employment evidence drift",
    )
    _require(payload.get("weekly_hours_min") is None, "weekly hours minimum was inferred")
    _require(payload.get("weekly_hours_max") is None, "weekly hours maximum was inferred")
    _require(
        payload.get("weekly_hours_evidence_status") == "unknown",
        "weekly hours evidence must remain unknown",
    )
    _require(
        payload.get("capability_fit_status") == "unknown",
        "capability fit must remain unknown",
    )
    for column in SCORE_COLUMNS:
        _require(payload.get(column) is None, f"ranking score must remain absent: {column}")


def _replace_explanations(
    explanations: list[dict[str, Any]],
    evidence: EonSourceEvidence,
) -> list[dict[str, Any]]:
    replaced_factors = {"required_languages", "work_model", "requirements_seniority"}
    result = [
        item
        for item in explanations
        if str(item.get("factor") or "") not in replaced_factors
    ]
    result.extend(
        [
            {
                "factor": "required_languages",
                "status": "observed",
                "required_languages": list(evidence.required_languages),
                "evidence": evidence.language_evidence_text,
            },
            {
                "factor": "work_model",
                "status": evidence.work_model,
                "evidence": evidence.work_model_evidence_text,
            },
            {
                "factor": "requirements_seniority",
                "status": evidence.requirements_seniority,
                "evidence": evidence.seniority_evidence_text,
            },
        ]
    )
    return result


def _remove_resolved_uncertainties(
    uncertainties: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    resolved = {"required_languages", "work_model", "requirements_seniority"}
    result = [
        item
        for item in uncertainties
        if str(item.get("factor") or "") not in resolved
    ]
    remaining = {str(item.get("factor") or "") for item in result}
    _require("weekly_hours" in remaining, "weekly-hours uncertainty disappeared")
    _require(
        "candidate_capability_fit" in remaining,
        "candidate capability-fit uncertainty disappeared",
    )
    _require("ranking_scores" in remaining, "ranking-score uncertainty disappeared")
    return result


def build_eon_assessment_refresh(
    *,
    existing_assessment: Mapping[str, Any],
    raw_data: Mapping[str, Any],
    assessed_by: str = DEFAULT_ASSESSED_BY,
) -> AssessmentRefresh:
    assessor = assessed_by.strip()
    _require(bool(assessor), "assessed_by must not be blank")

    previous = canonical_assessment_payload(existing_assessment)
    _validate_preserved_boundaries(previous)

    job = _mapping(raw_data.get("job"), "raw_data.job")
    evidence = extract_eon_source_evidence(
        description=job.get("description"),
        title=job.get("title"),
    )

    current_languages = tuple(previous["required_languages"])
    _require(
        current_languages in ((), EXPECTED_REQUIRED_LANGUAGES),
        "existing required-language evidence conflicts with bounded refresh",
    )
    _require(
        previous.get("language_evidence_status") in ("unknown", "observed"),
        "existing language evidence status conflicts",
    )
    _require(
        previous.get("work_model") in ("unknown", "hybrid"),
        "existing work model conflicts",
    )
    _require(
        previous.get("requirements_seniority") in ("unknown", "senior"),
        "existing requirements seniority conflicts",
    )
    _require(
        previous.get("seniority_evidence_status") in ("unknown", "observed"),
        "existing seniority evidence status conflicts",
    )

    next_payload = deepcopy(previous)
    next_payload["required_languages"] = list(evidence.required_languages)
    next_payload["language_evidence_status"] = "observed"
    next_payload["work_model"] = evidence.work_model
    next_payload["requirements_seniority"] = evidence.requirements_seniority
    next_payload["seniority_evidence_status"] = "observed"
    next_payload["explanations"] = _replace_explanations(
        previous["explanations"],
        evidence,
    )
    next_payload["uncertainties"] = _remove_resolved_uncertainties(
        previous["uncertainties"],
    )
    next_payload["assessed_by"] = assessor

    _validate_preserved_boundaries(next_payload)

    changed = tuple(
        column
        for column in ASSESSMENT_COLUMNS
        if previous.get(column) != next_payload.get(column)
    )
    unexpected = set(changed) - ALLOWED_CHANGED_FIELDS
    _require(not unexpected, f"refresh changed fields outside boundary: {sorted(unexpected)}")

    return AssessmentRefresh(
        previous_payload=previous,
        next_payload=next_payload,
        source_evidence=evidence,
        changed_fields=changed,
    )


def assessment_is_refreshed(payload: Mapping[str, Any]) -> bool:
    canonical = canonical_assessment_payload(payload)
    return (
        tuple(canonical["required_languages"]) == EXPECTED_REQUIRED_LANGUAGES
        and canonical["language_evidence_status"] == "observed"
        and canonical["work_model"] == "hybrid"
        and canonical["requirements_seniority"] == "senior"
        and canonical["seniority_evidence_status"] == "observed"
        and canonical["capability_fit_status"] == "unknown"
        and canonical["weekly_hours_evidence_status"] == "unknown"
        and all(canonical[column] is None for column in SCORE_COLUMNS)
    )
