"""Adaptive origin job-page observation helpers.

This module is deliberately a learning-input layer. It observes heterogeneous
job pages, extracts structural/signal candidates and scores marginal learning
value. It must not pass candidate gates, activate sources, write Bronze/Silver
records or replace the explicit gate agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
import re
from typing import Iterable, Sequence
from urllib.parse import urlparse

OBSERVATION_BOUNDARY = {
    "learning_input_only": True,
    "no_gate_decision": True,
    "no_candidate_status_mutation": True,
    "no_connector_artifact_generation": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_bronze_write": True,
    "no_silver_write": True,
    "no_scheduler_change": True,
    "no_csv_or_export_input": True,
    "adaptive_stop_or_extend": True,
}

REMOTE_SIGNAL_TERMS = (
    "remote",
    "remote deutschland",
    "remote germany",
    "homeoffice",
    "home office",
    "home-office",
    "mobiles arbeiten",
    "mobile work",
    "work from home",
    "work from anywhere in germany",
)

LOCATION_SIGNAL_TERMS = (
    "hannover",
    "deutschlandweit",
    "bundesweit",
    "germany-wide",
    "germany wide",
    "standort deutschlandweit",
    "standort: deutschlandweit",
    "+ weitere",
    "+ weitere standorte",
)

PROFILE_SIGNAL_TERMS = (
    "data engineer",
    "data engineering",
    "analytics engineer",
    "databricks",
    "data & analytics",
    "python",
    "sql",
    "bi",
)

URL_PATTERN_MARKERS = (
    "/job/",
    "/jobs/",
    "/stellenangebote/",
    "/stellen/",
    "/vacancy/",
    "/vacancies/",
    "/career/",
    "/careers/",
    "/search/",
)


@dataclass(frozen=True)
class ObservationConfig:
    min_observations: int = 20
    soft_cap: int = 40
    hard_cap: int = 75
    saturation_window: int = 5
    low_learning_threshold: float = 0.10
    high_learning_threshold: float = 0.60
    medium_learning_threshold: float = 0.40
    extension_size: int = 5

    def __post_init__(self) -> None:
        if self.min_observations < 1:
            raise ValueError("min_observations must be >= 1")
        if self.soft_cap < self.min_observations:
            raise ValueError("soft_cap must be >= min_observations")
        if self.hard_cap < self.soft_cap:
            raise ValueError("hard_cap must be >= soft_cap")
        if self.saturation_window < 1:
            raise ValueError("saturation_window must be >= 1")


@dataclass(frozen=True)
class PageObservationInput:
    source_url: str
    final_url: str | None
    status_code: int | None
    title: str | None
    body: str
    source_family_guess: str | None = None


@dataclass(frozen=True)
class JobPageObservation:
    source_url: str
    final_url: str | None
    host: str | None
    source_family_guess: str | None
    status_code: int | None
    page_type_guess: str
    title: str | None
    ats_family_guess: str | None
    has_json_ld_jobposting: bool
    visible_job_link_count: int
    detail_url_patterns: tuple[str, ...]
    location_signal_candidates: tuple[str, ...]
    remote_signal_candidates: tuple[str, ...]
    profile_signal_candidates: tuple[str, ...]
    structural_markers: tuple[str, ...]
    learning_value: float
    novelty_reasons: tuple[str, ...]
    storage_class: str

    @property
    def pattern_candidates(self) -> tuple[tuple[str, str], ...]:
        items: list[tuple[str, str]] = []
        if self.page_type_guess:
            items.append(("page_type", self.page_type_guess))
        if self.ats_family_guess:
            items.append(("ats_family", self.ats_family_guess))
        if self.has_json_ld_jobposting:
            items.append(("json_ld_jobposting", "present"))
        items.extend(("url_path_pattern", value) for value in self.detail_url_patterns)
        items.extend(("location_signal", value) for value in self.location_signal_candidates)
        items.extend(("remote_signal", value) for value in self.remote_signal_candidates)
        items.extend(("profile_signal", value) for value in self.profile_signal_candidates)
        items.extend(("structural_marker", value) for value in self.structural_markers)
        seen: set[tuple[str, str]] = set()
        unique: list[tuple[str, str]] = []
        for pattern_type, value in items:
            normalized = normalize_text(value)
            if not normalized:
                continue
            key = (pattern_type, normalized)
            if key in seen:
                continue
            seen.add(key)
            unique.append((pattern_type, value))
        return tuple(unique)

    @property
    def summary(self) -> dict[str, object]:
        return {
            "boundary": OBSERVATION_BOUNDARY,
            "learning_input_only": True,
            "page_type_guess": self.page_type_guess,
            "ats_family_guess": self.ats_family_guess,
            "has_json_ld_jobposting": self.has_json_ld_jobposting,
            "visible_job_link_count": self.visible_job_link_count,
            "learning_value": self.learning_value,
            "novelty_reasons": list(self.novelty_reasons),
        }


class _JobPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self._inside_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower == "title":
            self._inside_title = True
        if lower != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title and data.strip():
            self.title_parts.append(data.strip())

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def canonical_url_key(url: str) -> str:
    """Return a stable key for observation de-duplication across runs."""

    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return normalize_text(url)
    scheme = parsed.scheme.lower()
    host = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = parsed.query
    return f"{scheme}://{host}{path}" + (f"?{query}" if query else "")


def url_host(url: str) -> str | None:
    parsed = urlparse(str(url or "").strip())
    return parsed.netloc.lower() or None


@dataclass(frozen=True)
class SeedObservationDecision:
    should_observe: bool
    reason: str
    url_key: str
    host: str | None


def decide_seed_observation(
    url: str,
    *,
    seen_url_keys: set[str],
    known_url_keys: set[str],
    saturated_hosts: set[str],
    saturated_host_counts: dict[str, int] | None = None,
    saturated_host_budget: int = 1,
    revalidate_known: bool = False,
) -> SeedObservationDecision:
    """Decide whether observing a seed is likely to add learning value.

    The decision is intentionally conservative: exact duplicates and already-known
    URLs should not consume observation budget during normal learning runs.
    Saturated providers/hosts may still be sampled with a tiny bounded budget to
    support drift detection without turning repeated seeds into DB noise.
    """

    key = canonical_url_key(url)
    host = url_host(url)
    if key in seen_url_keys:
        return SeedObservationDecision(False, "duplicate_in_run", key, host)
    if not revalidate_known and key in known_url_keys:
        return SeedObservationDecision(False, "known_seed_url", key, host)
    if not revalidate_known and host and host in saturated_hosts:
        counts = saturated_host_counts if saturated_host_counts is not None else {}
        if counts.get(host, 0) >= saturated_host_budget:
            return SeedObservationDecision(False, "saturated_provider_host", key, host)
    return SeedObservationDecision(True, "observe", key, host)


def term_hits(text: str, terms: Iterable[str]) -> tuple[str, ...]:
    normalized = normalize_text(text)
    hits: list[str] = []
    for term in terms:
        normalized_term = normalize_text(term)
        if normalized_term and normalized_term in normalized and term not in hits:
            hits.append(term)
    if re.search(r"\+\s*\d+\s+weitere", normalized) and "+ weitere" not in hits:
        hits.append("+ weitere")
    return tuple(hits)


def has_json_ld_jobposting(body: str) -> bool:
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        body or "",
        flags=re.IGNORECASE | re.DOTALL,
    ):
        payload = match.group(1).strip()
        if not payload:
            continue
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        normalized = normalize_text(json.dumps(parsed, ensure_ascii=False))
        if "jobposting" in normalized or "hiringorganization" in normalized:
            return True
    return False


def detail_url_patterns_from_urls(urls: Iterable[str]) -> tuple[str, ...]:
    patterns: list[str] = []
    for url in urls:
        path = urlparse(url).path.lower()
        for marker in URL_PATTERN_MARKERS:
            if marker in path and marker not in patterns:
                if marker in {"/job/", "/jobs/"}:
                    patterns.append(marker + "...")
                elif marker in {"/stellen/", "/stellenangebote/"}:
                    patterns.append("/stellen/...")
                elif marker in {"/vacancy/", "/vacancies/"}:
                    patterns.append("/vacancy/...")
                elif marker in {"/career/", "/careers/"}:
                    patterns.append("/career/...")
                elif marker == "/search/":
                    patterns.append("/search/...")
                else:
                    patterns.append(marker)
    return tuple(dict.fromkeys(patterns))


def detect_ats_family(text: str, urls: Sequence[str]) -> str | None:
    normalized = normalize_text(" ".join([text, *urls]))
    checks = (
        ("workday", "Workday"),
        ("successfactors", "SAP SuccessFactors"),
        ("personio", "Personio"),
        ("greenhouse", "Greenhouse"),
        ("smartrecruiters", "SmartRecruiters"),
        ("lever.co", "Lever"),
        ("phenom", "Phenom"),
        ("jobvite", "Jobvite"),
    )
    for marker, family in checks:
        if marker in normalized:
            return family
    return None


def guess_page_type(*, url: str, body: str, visible_job_link_count: int, json_ld_jobposting: bool) -> str:
    parsed = urlparse(url)
    path = parsed.path.lower()
    normalized = normalize_text(body)
    if json_ld_jobposting or any(marker in path for marker in ("/job/", "/stellen/", "/vacancy/")):
        return "job_detail"
    if "/search/" in path or "?q=" in url.lower() or visible_job_link_count >= 5:
        return "search_listing"
    if any(term in normalized for term in ("stellenportal", "karriere", "career", "jobs", "offene stellen")):
        return "career_landing"
    if any(term in normalized for term in ("workday", "successfactors", "personio", "greenhouse", "smartrecruiters")):
        return "ats_jobboard"
    if parsed.scheme not in {"http", "https"}:
        return "error_or_blocked"
    return "unknown"


def structural_markers_for(
    *,
    page_type: str,
    ats_family: str | None,
    has_json_ld: bool,
    visible_job_link_count: int,
) -> tuple[str, ...]:
    markers = [f"page_type:{page_type}"]
    if ats_family:
        markers.append(f"ats:{ats_family}")
    if has_json_ld:
        markers.append("json_ld:jobposting")
    if visible_job_link_count >= 10:
        markers.append("many_visible_job_links")
    elif visible_job_link_count > 0:
        markers.append("visible_job_links")
    return tuple(markers)


def score_learning_value(
    *,
    pattern_candidates: tuple[tuple[str, str], ...],
    known_patterns: set[tuple[str, str]],
) -> tuple[float, tuple[str, ...]]:
    weights = {
        "url_path_pattern": 0.25,
        "ats_family": 0.22,
        "json_ld_jobposting": 0.20,
        "remote_signal": 0.18,
        "location_signal": 0.18,
        "page_type": 0.12,
        "structural_marker": 0.08,
        "profile_signal": 0.05,
    }
    score = 0.0
    reasons: list[str] = []
    for pattern_type, value in pattern_candidates:
        normalized = normalize_text(value)
        key = (pattern_type, normalized)
        if key in known_patterns:
            continue
        score += weights.get(pattern_type, 0.05)
        reasons.append(f"new {pattern_type}: {value}")
    return round(min(score, 1.0), 4), tuple(reasons)


def storage_class_for(learning_value: float, *, has_json_ld: bool, page_type: str) -> str:
    if learning_value >= 0.35 or has_json_ld or page_type == "job_detail":
        return "full_observation"
    if learning_value >= 0.10:
        return "summary_only"
    return "discard_after_run"



def extract_job_like_urls(*, base_url: str, body: str, max_links: int = 12) -> tuple[str, ...]:
    """Extract bounded same-host job/search/detail links for observation expansion."""

    parser = _JobPageParser()
    parser.feed(body or "")
    base = urlparse(base_url)
    base_host = base.netloc.lower()
    urls: list[str] = []
    seen: set[str] = set()
    for href in parser.links:
        # urljoin is intentionally imported lazily to keep the public helpers compact.
        from urllib.parse import urljoin

        absolute = urljoin(base_url, href).split("#", 1)[0]
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc.lower() != base_host:
            continue
        lowered = absolute.lower()
        if not any(marker in lowered for marker in URL_PATTERN_MARKERS):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        urls.append(absolute)
        if len(urls) >= max_links:
            break
    return tuple(urls)


def build_observation(raw: PageObservationInput, *, known_patterns: set[tuple[str, str]] | None = None) -> JobPageObservation:
    known = known_patterns or set()
    parser = _JobPageParser()
    parser.feed(raw.body or "")
    title = raw.title or parser.title or None
    final_url = raw.final_url or raw.source_url
    parsed = urlparse(final_url)
    body_with_title = " ".join(value for value in (title, raw.body) if value)
    json_ld = has_json_ld_jobposting(raw.body)
    urls = tuple(parser.links)
    visible_job_link_count = sum(1 for url in urls if any(marker in url.lower() for marker in URL_PATTERN_MARKERS))
    ats_family = detect_ats_family(body_with_title, urls)
    detail_patterns = detail_url_patterns_from_urls([final_url, *urls])
    page_type = guess_page_type(url=final_url, body=body_with_title, visible_job_link_count=visible_job_link_count, json_ld_jobposting=json_ld)
    location_hits = term_hits(body_with_title, LOCATION_SIGNAL_TERMS)
    remote_hits = term_hits(body_with_title, REMOTE_SIGNAL_TERMS)
    profile_hits = term_hits(body_with_title, PROFILE_SIGNAL_TERMS)
    markers = structural_markers_for(
        page_type=page_type,
        ats_family=ats_family,
        has_json_ld=json_ld,
        visible_job_link_count=visible_job_link_count,
    )

    prototype = JobPageObservation(
        source_url=raw.source_url,
        final_url=final_url,
        host=parsed.netloc.lower() or None,
        source_family_guess=raw.source_family_guess,
        status_code=raw.status_code,
        page_type_guess=page_type,
        title=title,
        ats_family_guess=ats_family,
        has_json_ld_jobposting=json_ld,
        visible_job_link_count=visible_job_link_count,
        detail_url_patterns=detail_patterns,
        location_signal_candidates=location_hits,
        remote_signal_candidates=remote_hits,
        profile_signal_candidates=profile_hits,
        structural_markers=markers,
        learning_value=0.0,
        novelty_reasons=(),
        storage_class="discard_after_run",
    )
    value, reasons = score_learning_value(pattern_candidates=prototype.pattern_candidates, known_patterns=known)
    return JobPageObservation(
        source_url=prototype.source_url,
        final_url=prototype.final_url,
        host=prototype.host,
        source_family_guess=prototype.source_family_guess,
        status_code=prototype.status_code,
        page_type_guess=prototype.page_type_guess,
        title=prototype.title,
        ats_family_guess=prototype.ats_family_guess,
        has_json_ld_jobposting=prototype.has_json_ld_jobposting,
        visible_job_link_count=prototype.visible_job_link_count,
        detail_url_patterns=prototype.detail_url_patterns,
        location_signal_candidates=prototype.location_signal_candidates,
        remote_signal_candidates=prototype.remote_signal_candidates,
        profile_signal_candidates=prototype.profile_signal_candidates,
        structural_markers=prototype.structural_markers,
        learning_value=value,
        novelty_reasons=reasons,
        storage_class=storage_class_for(value, has_json_ld=json_ld, page_type=page_type),
    )


@dataclass
class AdaptiveObservationLoop:
    config: ObservationConfig = field(default_factory=ObservationConfig)
    observed_count: int = 0
    current_cap: int = 40
    learning_values: list[float] = field(default_factory=list)
    stop_reason: str | None = None

    def __post_init__(self) -> None:
        self.current_cap = self.config.soft_cap

    def record(self, observation: JobPageObservation) -> None:
        self.observed_count += 1
        self.learning_values.append(observation.learning_value)
        if observation.learning_value >= self.config.high_learning_threshold and self.current_cap < self.config.hard_cap:
            self.current_cap = min(self.config.hard_cap, self.current_cap + self.config.extension_size)

    def rolling_average(self) -> float:
        values = self.learning_values[-self.config.saturation_window :]
        if not values:
            return 0.0
        return round(sum(values) / len(values), 4)

    def should_continue(self) -> bool:
        if self.observed_count < self.config.min_observations:
            return True
        if self.observed_count >= self.config.hard_cap:
            self.stop_reason = "hard_cap_reached"
            return False
        recent = self.learning_values[-self.config.saturation_window :]
        if len(recent) >= self.config.saturation_window:
            avg = self.rolling_average()
            if avg < self.config.low_learning_threshold and max(recent) < self.config.medium_learning_threshold:
                self.stop_reason = "learning_saturation"
                return False
            if self.observed_count >= self.current_cap and avg < self.config.medium_learning_threshold:
                self.stop_reason = "adaptive_cap_reached"
                return False
        return True


def summarize_learning_values(values: Sequence[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "total": 0.0, "max": 0.0, "average": 0.0}
    total = round(sum(values), 4)
    return {
        "count": len(values),
        "total": total,
        "max": round(max(values), 4),
        "average": round(total / len(values), 4),
    }
