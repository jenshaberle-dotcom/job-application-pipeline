from __future__ import annotations

from dataclasses import dataclass, field
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import re
import socket
from typing import Iterable

KNOWN_AGGREGATOR_DOMAINS = {
    "stepstone.de",
    "www.stepstone.de",
    "linkedin.com",
    "www.linkedin.com",
    "xing.com",
    "www.xing.com",
    "indeed.com",
    "de.indeed.com",
    "glassdoor.de",
    "www.glassdoor.de",
}

SOCIAL_OR_EXTERNAL_NOISE_DOMAINS = {
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "tiktok.com",
    "www.tiktok.com",
    "twitter.com",
    "x.com",
    "www.x.com",
    "kununu.com",
    "www.kununu.com",
}

ASSET_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".css", ".js",
    ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".zip", ".xml", ".json",
)

TECHNICAL_PATH_MARKERS = (
    "/favicon", "/feed/", "/comments/feed", "/wp-json", "/oembed", "/resource/crblob/",
    "/assets/", "/static/", "/media/", "/images/", "/img/", "/fonts/", "/api/",
)

MARKETING_OR_PRESS_MARKERS = (
    "/news", "/presse", "/press", "/media", "/download", "/downloads", "/pressebilder",
    "/ueber-uns", "/about", "/unternehmen", "/kontakt", "/contact", "/impressum", "/datenschutz",
)

CAREER_CONTEXT_ONLY_MARKERS = (
    "ausbildung", "schueler", "schüler", "pupil", "pupils", "student", "students",
    "working_students", "praktikum", "trainee", "dual", "duales-studium", "vocational_training",
)

JOB_LIST_HINTS = (
    "jobs", "job-board", "job_board", "stellenangebote", "stellenangebot", "stellen", "jobsuche",
    "jobsearch", "vacancies", "positions", "offene-stellen", "karriere/jobs", "career/jobs",
)

JOB_DETAIL_HINTS = (
    "data", "daten", "engineer", "analytics", "analyst", "cloud", "platform", "devops",
    "software", "developer", "entwickler", "architect", "architekt", "ki", "ai", "bi",
    "database", "etl", "manager", "consultant", "product", "application", "backend",
    "frontend", "fullstack", "machine-learning", "mlops",
)

CAREER_HINTS = (
    "karriere", "career", "careers", "jobs", "stellen", "stellenangebote", "job_board", "offene-stellen",
)

JOB_STRUCTURE_HTML_HINTS = (
    "job-title", "jobtitle", "job-list", "joblist", "job-card", "jobcard", "jobsearch", "job search",
    "stellenanzeige", "stellenangebot", "stellenangebote", "offene stellen", "vacancy", "vacancies",
    "data-job", "jobid", "job-id", "posting", "job posting", "apply now", "jetzt bewerben",
    "bewerben", "location", "standort", "remote", "vollzeit", "teilzeit",
)


@dataclass(frozen=True)
class OriginCandidate:
    candidate_id: int
    company_key: str
    company_name: str
    origin_url: str | None
    source_name_candidate: str | None = None
    status: str | None = None
    risk_level: str | None = None


@dataclass(frozen=True)
class ProbeFetchResult:
    final_url: str | None
    http_status: int | None
    body: str
    error: str | None = None
    blocked_by_site: bool = False


@dataclass(frozen=True)
class UrlQualityFeedback:
    status: str
    code: str | None
    repair_candidate_url: str | None
    message: str


@dataclass(frozen=True)
class EvidenceLink:
    url: str
    label: str
    evidence_type: str
    reason: str


@dataclass(frozen=True)
class EvidenceClassification:
    accepted: tuple[EvidenceLink, ...]
    rejected: tuple[EvidenceLink, ...]

    @property
    def job_search_page_count(self) -> int:
        return sum(1 for item in self.accepted if item.evidence_type == "job_search_page_evidence")

    @property
    def job_detail_candidate_count(self) -> int:
        return sum(1 for item in self.accepted if item.evidence_type == "job_detail_candidate_evidence")

    @property
    def career_context_count(self) -> int:
        return sum(1 for item in self.accepted if item.evidence_type == "career_context_evidence")

    @property
    def structural_count(self) -> int:
        return self.job_search_page_count + self.job_detail_candidate_count

    @property
    def rejected_noise_count(self) -> int:
        return len(self.rejected)

    @property
    def structural_urls(self) -> tuple[str, ...]:
        return tuple(item.url for item in self.accepted if item.evidence_type in {"job_search_page_evidence", "job_detail_candidate_evidence"})

    @property
    def job_detail_candidate_urls(self) -> tuple[str, ...]:
        return tuple(item.url for item in self.accepted if item.evidence_type == "job_detail_candidate_evidence")

    def as_dict(self) -> dict:
        return {
            "accepted": [item.__dict__ for item in self.accepted],
            "rejected": [item.__dict__ for item in self.rejected],
            "counts": {
                "job_search_page_evidence": self.job_search_page_count,
                "job_detail_candidate_evidence": self.job_detail_candidate_count,
                "career_context_evidence": self.career_context_count,
                "rejected_noise": self.rejected_noise_count,
                "structural_job_evidence": self.structural_count,
            },
        }


@dataclass(frozen=True)
class ConnectorFeasibilityItem:
    candidate: OriginCandidate
    http_status: int | None
    reachable: bool
    page_type: str
    sample_job_urls: tuple[str, ...]
    structural_job_evidence_count: int
    feasibility_status: str
    decision: str
    blocker_code: str | None
    reason: str
    recommended_next_action: str
    url_quality: UrlQualityFeedback
    evidence_classification: EvidenceClassification = field(default_factory=lambda: EvidenceClassification((), ()))
    evidence: dict = field(default_factory=dict)

    @property
    def sample_job_count(self) -> int:
        return len(self.sample_job_urls)

    @property
    def job_search_page_evidence_count(self) -> int:
        return self.evidence_classification.job_search_page_count

    @property
    def job_detail_candidate_evidence_count(self) -> int:
        return self.evidence_classification.job_detail_candidate_count

    @property
    def career_context_evidence_count(self) -> int:
        return self.evidence_classification.career_context_count

    @property
    def rejected_noise_count(self) -> int:
        return self.evidence_classification.rejected_noise_count


@dataclass(frozen=True)
class ConnectorFeasibilityReview:
    items: tuple[ConnectorFeasibilityItem, ...]
    fetch_enabled: bool
    reviewed_by: str

    @property
    def candidate_count(self) -> int:
        return len(self.items)

    @property
    def likely_feasible_count(self) -> int:
        return sum(1 for item in self.items if item.feasibility_status == "likely_feasible")

    @property
    def manual_review_count(self) -> int:
        return sum(1 for item in self.items if item.feasibility_status == "manual_review_required")

    @property
    def blocked_count(self) -> int:
        return sum(1 for item in self.items if item.feasibility_status == "blocked")

    @property
    def missing_origin_url_count(self) -> int:
        return sum(1 for item in self.items if item.feasibility_status == "missing_origin_url")


def _host(url: str | None) -> str:
    if not url:
        return ""
    return urlparse(url.strip()).hostname or ""


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
    return bool(_registered_domain(left) and _registered_domain(left) == _registered_domain(right))


def is_public_https_origin_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    host = parsed.hostname or ""
    if host in KNOWN_AGGREGATOR_DOMAINS:
        return False
    if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return False
    if not re.search(r"[a-zA-Z]", host) or "." not in host:
        return False
    return True


def is_technical_or_asset_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if path.endswith(ASSET_EXTENSIONS):
        return True
    return any(marker in path for marker in TECHNICAL_PATH_MARKERS)


def _is_root_homepage(origin_url: str, url: str) -> bool:
    parsed = urlparse(url)
    if not _same_registered_domain(origin_url, url):
        return False
    normalized_path = parsed.path.strip("/")
    return normalized_path == ""


def _contains_any(value: str, tokens: tuple[str, ...]) -> bool:
    return any(token in value for token in tokens)


def is_job_list_url(url: str | None) -> bool:
    if not url:
        return False
    haystack = url.lower()
    return any(hint in haystack for hint in JOB_LIST_HINTS)


def infer_page_type(url: str | None, html: str = "") -> str:
    haystack = f"{url or ''} {html[:50000]}".lower()
    if any(token in haystack for token in ("greenhouse.io", "personio", "lever.co", "workdayjobs")):
        return "ats_board_or_embed"
    if any(token in haystack for token in CAREER_HINTS):
        return "career_search_or_job_board"
    return "unknown"


def bounded_fetch(url: str, *, timeout_seconds: float = 8.0, max_bytes: int = 250_000) -> ProbeFetchResult:
    request = Request(
        url,
        headers={
            "User-Agent": "job-application-pipeline/connector-feasibility-probe (+bounded-read-only)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - bounded user-reviewed public URLs only
            body = response.read(max_bytes).decode("utf-8", errors="replace")
            return ProbeFetchResult(final_url=response.geturl(), http_status=getattr(response, "status", None), body=body)
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read(min(max_bytes, 50_000)).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return ProbeFetchResult(
            final_url=exc.url,
            http_status=exc.code,
            body=body,
            error=str(exc),
            blocked_by_site=exc.code in {401, 403, 429},
        )
    except (URLError, TimeoutError, socket.timeout) as exc:
        return ProbeFetchResult(final_url=url, http_status=None, body="", error=str(exc))


def _anchor_candidates(html: str) -> Iterable[tuple[str, str]]:
    pattern = re.compile(r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", flags=re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(html):
        href = unescape(match.group(1)).strip()
        text = re.sub(r"<[^>]+>", " ", match.group(2))
        text = re.sub(r"\s+", " ", unescape(text)).strip()
        yield href, text


CONTEXT_ONLY_PATH_PARTS = {
    "ausbildung",
    "schueler",
    "schüler",
    "student",
    "students",
    "working_students",
    "working-students",
    "praktikum",
    "trainee",
    "duales-studium",
    "bewerbung",
    "bewerbungstipps",
    "benefits",
    "culture",
    "kultur",
    "favoriten",
    "job-alert",
    "jobalert",
    "registerjobalerts",
    "gender",
    "hinweis",
    "datenschutz",
    "impressum",
    "login",
    "profile",
    "talent-community",
}

CONTEXT_ONLY_LABEL_MARKERS = {
    "ausbildung",
    "working students",
    "schüler",
    "student",
    "praktikum",
    "trainee",
    "bewerbungstipps",
    "bewerbung",
    "favoriten",
    "job alert",
    "jobalert",
    "gender",
    "hinweis",
    "datenschutz",
    "impressum",
}

JOB_AREA_MARKERS = {
    "job",
    "jobs",
    "stellen",
    "stelle",
    "stellenangebote",
    "jobangebote",
    "job-board",
    "job_board",
    "jobsuche",
    "karriere",
    "career",
    "careers",
    "vacancies",
    "positions",
}

JOB_DETAIL_MARKERS = {
    "data",
    "daten",
    "engineer",
    "developer",
    "entwickler",
    "analyst",
    "analytics",
    "cloud",
    "platform",
    "devops",
    "software",
    "architect",
    "architekt",
    "manager",
    "consultant",
    "bi",
    "ki",
    "ai",
    "ml",
    "etl",
    "sap",
    "it",
    "application",
    "system",
}


def _path_parts(url: str) -> list[str]:
    return [part for part in urlparse(url).path.lower().strip('/').split('/') if part]


def _is_context_only_path_or_label(url: str, label: str) -> bool:
    parts = _path_parts(url)
    normalized_parts = {part.replace('_', '-').strip() for part in parts}
    label_lower = label.lower()
    return bool(
        normalized_parts.intersection(CONTEXT_ONLY_PATH_PARTS)
        or any(marker in label_lower for marker in CONTEXT_ONLY_LABEL_MARKERS)
    )


def _looks_like_job_search_page(url: str, label: str) -> bool:
    if _is_context_only_path_or_label(url, label):
        return False
    parts = _path_parts(url)
    if not parts:
        return False
    last = parts[-1].replace('_', '-').lower()
    if last in {"jobs", "stellen", "stellenangebote", "jobsuche", "offene-stellen", "job-board", "job_board", "jobangebote"}:
        return True
    if len(parts) >= 2 and any(part in JOB_AREA_MARKERS for part in parts):
        combined = " ".join(parts[-2:]) + " " + label.lower()
        return any(hint in combined for hint in ("offene stellen", "job search", "jobsuche", "stellenangebote", "job board"))
    return False





def _looks_like_job_detail_path(url: str, label: str) -> bool:
    if _is_context_only_path_or_label(url, label):
        return False

    parts = _path_parts(url)
    if len(parts) < 2:
        return False

    # A build-ready sample job should look like a concrete detail page, not
    # just any career-context navigation link. This deliberately requires a
    # job/career area before the slug and a role-like signal in the slug or
    # label. It avoids counting feeds, gender notes, favourites, application
    # tips, education pages or generic career landing pages as sample jobs.
    has_job_area = any(part in JOB_AREA_MARKERS for part in parts[:-1])
    if not has_job_area:
        return False

    tail = parts[-1].replace('-', ' ').replace('_', ' ')
    combined = f"{tail} {label.lower()}"
    if any(marker in combined for marker in CONTEXT_ONLY_LABEL_MARKERS):
        return False
    return any(marker in combined for marker in JOB_DETAIL_MARKERS)


def classify_evidence_link(origin_url: str, absolute_url: str, label: str) -> EvidenceLink:
    parsed = urlparse(absolute_url)
    host = parsed.hostname or ""
    haystack = f"{absolute_url} {label}".lower()

    if parsed.scheme not in {"http", "https"}:
        return EvidenceLink(absolute_url, label, "technical_or_legacy_noise", "non-http(s) link")
    if host in KNOWN_AGGREGATOR_DOMAINS:
        return EvidenceLink(absolute_url, label, "aggregator_noise", "known aggregator domain")
    if host in SOCIAL_OR_EXTERNAL_NOISE_DOMAINS:
        return EvidenceLink(absolute_url, label, "offsite_social_noise", "social or employer-brand external profile")
    if parsed.scheme == "http" or "prod-" in host or "release" in host or "staging" in host or "test" in host:
        return EvidenceLink(absolute_url, label, "technical_or_legacy_noise", "non-production or non-https technical URL")
    if is_technical_or_asset_url(absolute_url):
        return EvidenceLink(absolute_url, label, "technical_or_legacy_noise", "asset, feed or technical endpoint")
    if _is_root_homepage(origin_url, absolute_url):
        return EvidenceLink(absolute_url, label, "marketing_or_press_noise", "root homepage is not sample job evidence")
    if _contains_any(haystack, MARKETING_OR_PRESS_MARKERS):
        return EvidenceLink(absolute_url, label, "marketing_or_press_noise", "marketing, press, media or legal navigation")

    if _looks_like_job_detail_path(absolute_url, label):
        return EvidenceLink(absolute_url, label, "job_detail_candidate_evidence", "strict job/detail-like URL with role signal")
    if _looks_like_job_search_page(absolute_url, label):
        return EvidenceLink(absolute_url, label, "job_search_page_evidence", "job search/listing page URL")

    if _is_context_only_path_or_label(absolute_url, label) or _contains_any(haystack, CAREER_CONTEXT_ONLY_MARKERS):
        return EvidenceLink(absolute_url, label, "career_context_evidence", "career context only, not build-ready job evidence")

    same_domain = _same_registered_domain(origin_url, absolute_url)
    trusted_job_host = any(token in host.lower() for token in ("job", "career", "karriere"))
    if any(hint in haystack for hint in CAREER_HINTS) and (same_domain or trusted_job_host):
        return EvidenceLink(absolute_url, label, "career_context_evidence", "career context link without job structure")

    return EvidenceLink(absolute_url, label, "marketing_or_press_noise", "not enough job or career structure")


def classify_evidence_links(origin_url: str, html: str, *, limit: int = 80) -> EvidenceClassification:
    accepted: list[EvidenceLink] = []
    rejected: list[EvidenceLink] = []
    seen: set[str] = set()
    for raw_href, link_text in _anchor_candidates(html):
        absolute = urljoin(origin_url, raw_href)
        if absolute in seen:
            continue
        seen.add(absolute)
        item = classify_evidence_link(origin_url, absolute, link_text)
        if item.evidence_type in {"job_search_page_evidence", "job_detail_candidate_evidence", "career_context_evidence"}:
            accepted.append(item)
        else:
            rejected.append(item)
        if len(accepted) + len(rejected) >= limit:
            break
    return EvidenceClassification(tuple(accepted), tuple(rejected))





def extract_sample_job_urls(origin_url: str, html: str, *, limit: int = 5) -> tuple[str, ...]:
    classification = classify_evidence_links(origin_url, html)
    detail_urls = tuple(
        item.url
        for item in classification.accepted
        if item.evidence_type == "job_detail_candidate_evidence"
    )
    return detail_urls[:limit]

def extract_repair_candidate_urls(origin_url: str, html: str, *, limit: int = 5) -> tuple[str, ...]:
    candidates: list[str] = []
    classification = classify_evidence_links(origin_url, html)
    for item in classification.accepted:
        parsed = urlparse(item.url)
        if item.evidence_type not in {"job_search_page_evidence", "job_detail_candidate_evidence"}:
            continue
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        if _same_registered_domain(origin_url, item.url) or any(hint in parsed.hostname.lower() for hint in ("job", "career", "karriere")):
            if item.url not in candidates:
                candidates.append(item.url)
        if len(candidates) >= limit:
            break
    return tuple(candidates)


def html_has_structural_job_evidence(html: str) -> bool:
    haystack = html[:160000].lower()
    structural_hits = sum(1 for hint in JOB_STRUCTURE_HTML_HINTS if hint in haystack)
    data_hits = sum(1 for hint in JOB_DETAIL_HINTS if hint in haystack)
    return structural_hits >= 2 and data_hits >= 1


def structural_job_evidence_count(origin_url: str, html: str, classification: EvidenceClassification) -> int:
    count = classification.structural_count
    if is_job_list_url(origin_url) and html_has_structural_job_evidence(html):
        count += 1
    return count


def _url_quality_feedback(
    candidate: OriginCandidate,
    *,
    reachable: bool,
    result: ProbeFetchResult | None,
    classification: EvidenceClassification,
    structural_count: int,
    page_type: str,
) -> UrlQualityFeedback:
    if not candidate.origin_url:
        return UrlQualityFeedback("missing_origin_url", "missing_origin_url", None, "Candidate has no origin URL to evaluate.")
    if not is_public_https_origin_url(candidate.origin_url):
        return UrlQualityFeedback("unsafe_or_aggregator_url", "unsafe_or_aggregator_origin_url", None, "Origin URL is unsafe, non-public, non-HTTPS or an aggregator URL.")
    if not result:
        return UrlQualityFeedback("not_evaluated", "fetch_disabled", None, "Fetch was disabled, so no URL quality feedback was produced.")

    repair_candidates = extract_repair_candidate_urls(candidate.origin_url, result.body)
    repair_url = repair_candidates[0] if repair_candidates else None
    if not reachable:
        if repair_url:
            return UrlQualityFeedback("repair_candidate_detected", "origin_url_repair_candidate_detected", repair_url, "Selected origin URL is not reachable, but a plausible career/job URL was detected in the response.")
        return UrlQualityFeedback("not_reachable", "origin_url_not_reachable", None, "Selected origin URL was not reachable by the bounded probe.")
    if structural_count > 0:
        return UrlQualityFeedback("valid_probe_ready", "sample_job_evidence_found", None, "Selected origin URL is reachable and exposes structural job evidence.")
    if classification.rejected_noise_count and not classification.accepted:
        return UrlQualityFeedback("asset_noise_only", "origin_url_asset_noise_only", repair_url, "Selected origin URL is reachable, but detected links are assets, feeds, technical endpoints or external noise.")
    if page_type == "career_search_or_job_board" or classification.career_context_count:
        return UrlQualityFeedback("career_page_without_job_structure", "origin_url_has_career_page_but_no_job_structure", repair_url, "Selected URL looks career-like, but the bounded probe did not detect job list or detail structure.")
    return UrlQualityFeedback("not_evaluated", "no_structural_job_evidence", repair_url, "No structural job evidence was detected.")


def _empty_classification() -> EvidenceClassification:
    return EvidenceClassification((), ())



def evaluate_connector_feasibility(
    candidate: OriginCandidate,
    *,
    fetch_enabled: bool = True,
    fetch_result: ProbeFetchResult | None = None,
) -> ConnectorFeasibilityItem:
    empty = _empty_classification()

    if not candidate.origin_url:
        feedback = _url_quality_feedback(
            candidate,
            reachable=False,
            result=None,
            classification=empty,
            structural_count=0,
            page_type="missing_origin_url",
        )
        return ConnectorFeasibilityItem(
            candidate=candidate,
            http_status=None,
            reachable=False,
            page_type="missing_origin_url",
            sample_job_urls=(),
            structural_job_evidence_count=0,
            feasibility_status="missing_origin_url",
            decision="defer_until_origin_url_available",
            blocker_code="missing_origin_url",
            reason="Candidate has no origin URL to probe.",
            recommended_next_action="Run Origin Source Discovery Gate or provide a reviewed manual origin URL.",
            url_quality=feedback,
            evidence_classification=empty,
            evidence={
                "fetch_enabled": fetch_enabled,
                "final_url": None,
                "error": None,
                "url_quality_feedback": feedback.__dict__,
                "structural_job_evidence_count": 0,
                "evidence_classification": empty.as_dict(),
            },
        )

    if not is_public_https_origin_url(candidate.origin_url):
        feedback = _url_quality_feedback(
            candidate,
            reachable=False,
            result=None,
            classification=empty,
            structural_count=0,
            page_type="unsafe_or_aggregator_url",
        )
        return ConnectorFeasibilityItem(
            candidate=candidate,
            http_status=None,
            reachable=False,
            page_type="unsafe_or_aggregator_url",
            sample_job_urls=(),
            structural_job_evidence_count=0,
            feasibility_status="blocked",
            decision="abort_documented",
            blocker_code="unsafe_or_aggregator_origin_url",
            reason="Origin URL is unsafe, non-public, non-HTTPS or points to an aggregator.",
            recommended_next_action="Replace the origin URL with a reviewed public HTTPS employer-origin career URL.",
            url_quality=feedback,
            evidence_classification=empty,
            evidence={
                "fetch_enabled": fetch_enabled,
                "final_url": None,
                "error": None,
                "url_quality_feedback": feedback.__dict__,
                "structural_job_evidence_count": 0,
                "evidence_classification": empty.as_dict(),
            },
        )

    if not fetch_enabled:
        feedback = _url_quality_feedback(
            candidate,
            reachable=False,
            result=None,
            classification=empty,
            structural_count=0,
            page_type="not_evaluated",
        )
        return ConnectorFeasibilityItem(
            candidate=candidate,
            http_status=None,
            reachable=False,
            page_type="not_evaluated",
            sample_job_urls=(),
            structural_job_evidence_count=0,
            feasibility_status="manual_review_required",
            decision="manual_review_required",
            blocker_code="fetch_disabled",
            reason="Fetch was disabled, so connector feasibility could not be evaluated.",
            recommended_next_action="Rerun the probe with bounded fetch enabled.",
            url_quality=feedback,
            evidence_classification=empty,
            evidence={
                "fetch_enabled": fetch_enabled,
                "final_url": None,
                "error": None,
                "url_quality_feedback": feedback.__dict__,
                "structural_job_evidence_count": 0,
                "evidence_classification": empty.as_dict(),
            },
        )

    result = fetch_result if fetch_result is not None else bounded_fetch(candidate.origin_url)
    status = result.http_status
    reachable = status is not None and 200 <= status < 400

    page_type = infer_page_type(result.final_url or candidate.origin_url, result.body)
    classification = classify_evidence_links(candidate.origin_url, result.body)
    structural_count = classification.structural_count
    sample_urls = classification.job_detail_candidate_urls[:5]

    feedback = _url_quality_feedback(
        candidate,
        reachable=reachable,
        result=result,
        classification=classification,
        structural_count=structural_count,
        page_type=page_type,
    )

    base_evidence = {
        "fetch_enabled": fetch_enabled,
        "final_url": result.final_url,
        "error": result.error,
        "url_quality_feedback": feedback.__dict__,
        "structural_job_evidence_count": structural_count,
        "evidence_classification": classification.as_dict(),
    }

    if reachable and classification.job_detail_candidate_count > 0:
        return ConnectorFeasibilityItem(
            candidate=candidate,
            http_status=status,
            reachable=True,
            page_type=page_type,
            sample_job_urls=sample_urls,
            structural_job_evidence_count=structural_count,
            feasibility_status="likely_feasible",
            decision="continue_to_connector_build_planning",
            blocker_code=None,
            reason="Bounded probe reached a career-like page with job-list and concrete job-detail evidence.",
            recommended_next_action="Create connector build plan and capture one reviewed sample job before registration.",
            url_quality=feedback,
            evidence_classification=classification,
            evidence=base_evidence,
        )

    if reachable and structural_count > 0:
        detail_feedback = UrlQualityFeedback(
            "structural_without_detail",
            "missing_job_detail_evidence",
            feedback.repair_candidate_url,
            "Selected URL is reachable and exposes job structure, but no concrete job-detail sample evidence was detected.",
        )
        base_evidence["url_quality_feedback"] = detail_feedback.__dict__
        return ConnectorFeasibilityItem(
            candidate=candidate,
            http_status=status,
            reachable=True,
            page_type=page_type,
            sample_job_urls=sample_urls,
            structural_job_evidence_count=structural_count,
            feasibility_status="manual_review_required",
            decision="manual_review_required",
            blocker_code="structural_evidence_without_job_detail",
            reason="Bounded probe found job-list structure but no concrete job-detail sample evidence.",
            recommended_next_action="Review source manually or improve origin URL/detail extraction before connector build planning.",
            url_quality=detail_feedback,
            evidence_classification=classification,
            evidence=base_evidence,
        )

    if result.blocked_by_site:
        return ConnectorFeasibilityItem(
            candidate=candidate,
            http_status=status,
            reachable=False,
            page_type=page_type,
            sample_job_urls=sample_urls,
            structural_job_evidence_count=structural_count,
            feasibility_status="manual_review_required",
            decision="manual_review_required",
            blocker_code="probe_blocked_by_site",
            reason="The source exists but blocked the bounded probe; manual browser review is needed.",
            recommended_next_action="Open the URL manually and decide whether connector build is still feasible.",
            url_quality=feedback,
            evidence_classification=classification,
            evidence=base_evidence,
        )

    if not reachable:
        return ConnectorFeasibilityItem(
            candidate=candidate,
            http_status=status,
            reachable=False,
            page_type=page_type,
            sample_job_urls=sample_urls,
            structural_job_evidence_count=structural_count,
            feasibility_status="manual_review_required",
            decision="manual_review_required",
            blocker_code="origin_url_not_reachable",
            reason="Selected origin URL was not reachable by the bounded probe.",
            recommended_next_action="Use URL quality feedback to repair the origin URL, then rerun the feasibility probe.",
            url_quality=feedback,
            evidence_classification=classification,
            evidence=base_evidence,
        )

    return ConnectorFeasibilityItem(
        candidate=candidate,
        http_status=status,
        reachable=True,
        page_type=page_type,
        sample_job_urls=sample_urls,
        structural_job_evidence_count=structural_count,
        feasibility_status="manual_review_required",
        decision="manual_review_required",
        blocker_code="no_structural_job_evidence",
        reason="Bounded probe reached the URL but found no build-relevant job-list or job-detail evidence.",
        recommended_next_action="Inspect the page manually or improve origin URL discovery before connector build planning.",
        url_quality=feedback,
        evidence_classification=classification,
        evidence=base_evidence,
    )

def build_connector_feasibility_review(
    candidates: Iterable[OriginCandidate],
    *,
    reviewed_by: str,
    fetch_enabled: bool = True,
) -> ConnectorFeasibilityReview:
    items = tuple(evaluate_connector_feasibility(candidate, fetch_enabled=fetch_enabled) for candidate in candidates)
    return ConnectorFeasibilityReview(items=items, fetch_enabled=fetch_enabled, reviewed_by=reviewed_by)
