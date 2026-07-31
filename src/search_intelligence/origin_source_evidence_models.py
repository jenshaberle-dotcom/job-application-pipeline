"""Data models and bounded HTML parsing for origin-source evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from html.parser import HTMLParser
import re

SOURCE_GRADE_SCORES = {
    "ats_job_listing": 1.00,
    "company_job_listing": 0.94,
    "career_landing": 0.56,
    "job_detail": 0.46,
    "corporate_page": 0.20,
    "social_profile": 0.05,
    "aggregator": 0.00,
    "unknown": 0.10,
}

ENTITY_FIDELITY_SCORES = {
    "exact_legal_entity": 1.00,
    "brand_match": 0.86,
    "parent_group_match": 0.72,
    "related_entity": 0.55,
    "ambiguous": 0.25,
    "unknown": 0.10,
}

JOB_INVENTORY_SCORES = {
    "job_bearing_proven": 1.00,
    "job_bearing_currently_empty": 0.65,
    "job_bearing_unknown": 0.25,
    "not_job_bearing": 0.00,
    "fetch_failed": 0.05,
}

SOCIAL_HOSTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "x.com",
    "xing.com",
    "youtube.com",
}

LEGAL_FORM_TOKENS = {
    "ag",
    "aktiengesellschaft",
    "co",
    "eg",
    "ev",
    "gbr",
    "gmbh",
    "kg",
    "kgaa",
    "ltd",
    "mbh",
    "plc",
    "se",
}

CAREER_TERMS = {
    "career",
    "careers",
    "job",
    "jobs",
    "karriere",
    "recruiting",
    "stellen",
    "stellenangebote",
    "vacancies",
    "vacancy",
}

EMPTY_INVENTORY_PHRASES = (
    "aktuell keine offenen stellen",
    "derzeit keine offenen stellen",
    "keine passenden stellenangebote",
    "keine stellen gefunden",
    "no current openings",
    "no jobs found",
    "no open positions",
    "there are no jobs available",
)

DETAIL_PATH_MARKERS = (
    "/job/",
    "/jobs/",
    "/jobdetail/",
    "/job-details/",
    "/position/",
    "/positions/",
    "/requisition/",
    "/stellenangebot/",
    "/stellenangebote/",
    "/stellen/",
    "/vacancies/",
    "/vacancy/",
)

LISTING_PATH_MARKERS = (
    "/career",
    "/careers",
    "/jobs",
    "/job-search",
    "/jobsearch",
    "/karriere",
    "/search",
    "/stellenangebote",
    "/vacancies",
)

DEFAULT_TARGET_TERMS = (
    "ai engineer",
    "ai platform",
    "ai reliability",
    "analytics engineer",
    "data engineer",
    "data engineering",
    "data platform",
    "data quality",
    "machine learning engineer",
    "ml engineer",
    "mlops",
    "python",
    "reliability",
    "sql",
)


@dataclass(frozen=True)
class ArtifactCandidate:
    url: str
    provider: str = "unknown"
    provider_reason: str = ""
    title: str = ""
    snippet: str = ""
    prior_decision: str = ""
    prior_identity_score: float = 0.0
    prior_total_score: float = 0.0
    prior_reachable: bool | None = None


@dataclass(frozen=True)
class LinkEvidence:
    url: str
    text: str = ""


@dataclass(frozen=True)
class PageEvidence:
    requested_url: str
    final_url: str
    status_code: int | None
    reachable: bool
    title: str
    html_lang: str | None
    text: str
    links: tuple[LinkEvidence, ...]
    embedded_urls: tuple[str, ...]
    json_ld_jobposting_count: int
    failure_class: str | None = None


@dataclass(frozen=True)
class OriginEvidenceAssessment:
    candidate_id: str
    url: str
    final_url: str
    provider: str
    source_grade: str
    entity_fidelity: str
    job_inventory_state: str
    page_type: str
    ats_family: str | None
    http_status: int | None
    reachable: bool
    locale: str
    observed_job_count: int
    target_signal_job_count: int
    sample_job_urls: tuple[str, ...]
    identity_score: float
    source_grade_score: float
    entity_fidelity_score: float
    job_bearing_score: float
    locale_preference_score: float
    target_relevance_score: float
    evidence_completeness: float
    ranking_score: float
    reasons: tuple[str, ...]
    failure_class: str | None = None

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["sample_job_urls"] = list(self.sample_job_urls)
        payload["reasons"] = list(self.reasons)
        return payload


@dataclass(frozen=True)
class OriginEvidenceDecision:
    company_key: str
    company_name: str
    deterministic_decision: str
    selected_candidate_id: str | None
    selected_url: str | None
    confidence_score: float
    confidence_band: str
    selection_margin: float
    manual_review_required: bool
    adjudication_reasons: tuple[str, ...]
    assessments: tuple[OriginEvidenceAssessment, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "company_key": self.company_key,
            "company_name": self.company_name,
            "deterministic_decision": self.deterministic_decision,
            "selected_candidate_id": self.selected_candidate_id,
            "selected_url": self.selected_url,
            "confidence_score": self.confidence_score,
            "confidence_band": self.confidence_band,
            "selection_margin": self.selection_margin,
            "manual_review_required": self.manual_review_required,
            "adjudication_reasons": list(self.adjudication_reasons),
            "assessments": [item.to_json() for item in self.assessments],
        }


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.html_lang: str | None = None
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[LinkEvidence] = []
        self._inside_title = False
        self._current_href: str | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        values = {name.lower(): value for name, value in attrs}
        if lower == "html" and values.get("lang"):
            self.html_lang = str(values["lang"]).strip().lower()
        if lower == "title":
            self._inside_title = True
        if lower == "a" and values.get("href"):
            self._current_href = str(values["href"]).strip()
            self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower == "title":
            self._inside_title = False
        if lower == "a" and self._current_href:
            self.links.append(
                LinkEvidence(
                    url=self._current_href,
                    text=" ".join(self._current_link_text).strip(),
                )
            )
            self._current_href = None
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        cleaned = re.sub(r"\s+", " ", data).strip()
        if not cleaned:
            return
        self.text_parts.append(cleaned)
        if self._inside_title:
            self.title_parts.append(cleaned)
        if self._current_href:
            self._current_link_text.append(cleaned)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()[:300]

    @property
    def text(self) -> str:
        return " ".join(self.text_parts).strip()


