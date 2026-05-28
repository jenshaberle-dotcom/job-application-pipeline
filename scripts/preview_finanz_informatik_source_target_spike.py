"""Preview Finanz Informatik as a bounded export-first source-target spike.

S2J is intentionally read-only and export-first. It does not implement a
production connector, does not write to the database and does not fetch job
detail pages. It reads explicitly configured source pages, extracts candidate
links, applies S2I URL/relevance gates and writes review artifacts under
``exports/``.

Usage:
    python -m scripts.preview_finanz_informatik_source_target_spike
    python -m scripts.preview_finanz_informatik_source_target_spike --export-dir exports/s2j_finanz_informatik_export_first_spike
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse

import requests


DEFAULT_EXPORT_DIR = Path("exports/s2j_finanz_informatik_export_first_spike")
DEFAULT_SOURCE_URLS: tuple[str, ...] = (
    "https://www.f-i.de/de/karriere/offene-stellen",
)
TIMEOUT_SECONDS = 20
USER_AGENT = "job-application-pipeline/finanz-informatik-export-first-spike"

ALLOWED_ORIGIN_HOSTS = {"www.f-i.de", "f-i.de"}
MANUAL_REVIEW_HOSTS = {"finanz-informatik.onapply.de"}

TARGET_LOCATION_TERMS = ("hannover", "remote", "deutschland", "bundesweit")
SECONDARY_LOCATION_TERMS = ("frankfurt", "muenster", "münster")

PROFILE_TERMS = (
    "data",
    "daten",
    "analytics",
    "analyst",
    "business-analyst",
    "business intelligence",
    "business-intelligence",
    "bi",
    "sql",
    "python",
    "ki",
    "ai",
    "artificial intelligence",
    "machine learning",
    "data integration",
    "data governance",
    "data platform",
    "product owner",
    "produktverantwortlicher",
    "sas",
)

EXCLUSION_TERMS = (
    "duales-studium",
    "duales studium",
    "ausbildung",
    "werkstudierende",
    "werkstudent",
    "praktikum",
    "trainee",
    "active sourcing",
)

LOWER_VALUE_SCOPE_TERMS = (
    "hr-only",
    "payroll",
    "entgeltabrechnung",
    "recruiting",
    "personal",
)


@dataclass(frozen=True)
class FetchedPage:
    source_url: str
    status_code: int | str
    final_url: str
    html: str
    html_bytes: int
    error: str = ""


@dataclass(frozen=True)
class ExtractedLink:
    source_url: str
    href: str
    absolute_url: str
    text: str


@dataclass(frozen=True)
class SpikeCandidate:
    source_url: str
    candidate_url: str
    candidate_path: str
    candidate_title_or_slug: str
    link_text: str
    host: str
    path_class: str
    location_signal: str
    profile_terms: tuple[str, ...]
    exclusion_terms: tuple[str, ...]
    lower_value_scope_terms: tuple[str, ...]
    recommendation: str
    reason: str
    detail_fetch_needed_later: bool
    source_evidence_available_without_detail_fetch: str


class Fetcher(Protocol):
    def __call__(self, url: str, timeout_seconds: int) -> FetchedPage:
        ...


def fetch_source_page(url: str, timeout_seconds: int) -> FetchedPage:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout_seconds)
    except requests.RequestException as exc:
        return FetchedPage(
            source_url=url,
            status_code="request_error",
            final_url="-",
            html="",
            html_bytes=0,
            error=str(exc),
        )

    return FetchedPage(
        source_url=url,
        status_code=response.status_code,
        final_url=response.url,
        html=response.text,
        html_bytes=len(response.content),
    )


def strip_html(value: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>", " ", value)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_links(html: str, base_url: str) -> tuple[ExtractedLink, ...]:
    links: list[ExtractedLink] = []
    pattern = re.compile(
        r"(?is)<a\b[^>]*?href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<text>.*?)</a>"
    )

    for match in pattern.finditer(html):
        href = unescape(match.group("href")).strip()
        if not href:
            continue
        text = strip_html(match.group("text"))
        links.append(
            ExtractedLink(
                source_url=base_url,
                href=href,
                absolute_url=urljoin(base_url, href),
                text=text,
            )
        )

    return tuple(links)


def slug_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path:
        return "-"
    return unescape(path.rsplit("/", 1)[-1]).replace("-", " ").strip() or "-"


def classify_path(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if not url or url.startswith("#"):
        return "navigation_or_anchor"
    if host and host not in ALLOWED_ORIGIN_HOSTS and host not in MANUAL_REVIEW_HOSTS:
        return "external_non_job"
    if host in MANUAL_REVIEW_HOSTS and path.startswith("/details/"):
        return "onapply_detail_candidate_manual_review_only"
    if path.startswith("/de/karriere/duales-studium-ausbildung"):
        return "training_or_dual_study_exclude"
    if path.startswith("/de/karriere/offene-stellen/"):
        return "origin_open_position_candidate"
    if path in {"/de/karriere/offene-stellen", "/de/karriere/offene-stellen/"}:
        return "career_listing_page"
    if path.startswith("/de/karriere"):
        return "career_content_or_overview"
    return "other"


def find_terms(blob: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    lowered = blob.lower()
    matches = [term for term in terms if term.lower() in lowered]
    return tuple(dict.fromkeys(matches))


def location_signal(blob: str) -> str:
    lowered = blob.lower()
    hits = [term for term in TARGET_LOCATION_TERMS + SECONDARY_LOCATION_TERMS if term in lowered]
    return "; ".join(dict.fromkeys(hits)) or "unknown_from_listing_link"


def has_target_location(location: str) -> bool:
    return any(term in location for term in TARGET_LOCATION_TERMS)


def has_secondary_location(location: str) -> bool:
    return any(term in location for term in SECONDARY_LOCATION_TERMS)


def recommendation_for_candidate(
    *,
    path_class: str,
    profile_terms: tuple[str, ...],
    exclusion_terms: tuple[str, ...],
    lower_value_scope_terms: tuple[str, ...],
    location: str,
) -> tuple[str, str]:
    if path_class in {
        "navigation_or_anchor",
        "external_non_job",
        "career_content_or_overview",
        "career_listing_page",
        "other",
    }:
        return (
            "exclude_non_job_or_overview",
            "URL gate excludes non-job, overview, external or navigation paths.",
        )

    if path_class == "training_or_dual_study_exclude" or exclusion_terms:
        return (
            "exclude_training_student_or_entry_level",
            "Exclusion gate matched training, student, trainee or Ausbildung scope.",
        )

    if lower_value_scope_terms and not profile_terms:
        return (
            "exclude_low_profile_fit_scope",
            "Lower-value scope term matched without a positive profile signal.",
        )

    if path_class == "onapply_detail_candidate_manual_review_only":
        if profile_terms:
            return (
                "onapply_profile_match_manual_review_only",
                "OnApply detail path is visible, but OnApply usage must be reviewed separately.",
            )
        return (
            "onapply_candidate_manual_review_only",
            "OnApply detail path is visible, but profile fit is not proven at listing level.",
        )

    if profile_terms and has_target_location(location):
        return (
            "strong_listing_candidate_for_review",
            "Origin open-position path has profile and target-location signals.",
        )
    if profile_terms and has_secondary_location(location):
        return (
            "defer_non_target_location_without_remote_signal",
            "Profile signal exists, but the listing location is outside the primary target scope and no remote/Germany-wide signal is visible at listing level.",
        )
    if profile_terms:
        return (
            "profile_match_location_unknown_review",
            "Profile signal exists, but location cannot be confirmed from the listing link.",
        )
    if path_class == "origin_open_position_candidate" and has_secondary_location(location):
        return (
            "defer_non_target_location_without_remote_signal",
            "Origin open-position path is outside the primary target scope and no remote/Germany-wide signal is visible at listing level.",
        )
    if path_class == "origin_open_position_candidate":
        return (
            "job_candidate_low_profile_signal",
            "Origin open-position path exists, but listing-level profile signals are weak.",
        )

    return ("manual_review", "Fallback classification requires manual review.")


def candidate_from_link(link: ExtractedLink) -> SpikeCandidate:
    parsed = urlparse(link.absolute_url)
    blob = f"{link.href} {link.absolute_url} {link.text} {slug_from_url(link.absolute_url)}".lower()
    path_class = classify_path(link.absolute_url)
    profile_matches = find_terms(blob, PROFILE_TERMS)
    exclusion_matches = find_terms(blob, EXCLUSION_TERMS)
    lower_value_matches = find_terms(blob, LOWER_VALUE_SCOPE_TERMS)
    location = location_signal(blob)
    recommendation, reason = recommendation_for_candidate(
        path_class=path_class,
        profile_terms=profile_matches,
        exclusion_terms=exclusion_matches,
        lower_value_scope_terms=lower_value_matches,
        location=location,
    )

    return SpikeCandidate(
        source_url=link.source_url,
        candidate_url=link.absolute_url,
        candidate_path=parsed.path or "-",
        candidate_title_or_slug=link.text or slug_from_url(link.absolute_url),
        link_text=link.text,
        host=parsed.netloc or "-",
        path_class=path_class,
        location_signal=location,
        profile_terms=profile_matches,
        exclusion_terms=exclusion_matches,
        lower_value_scope_terms=lower_value_matches,
        recommendation=recommendation,
        reason=reason,
        detail_fetch_needed_later=recommendation in {
            "strong_listing_candidate_for_review",
            "profile_match_location_unknown_review",
            "job_candidate_low_profile_signal",
        },
        source_evidence_available_without_detail_fetch="url; slug; link_text; source_url",
    )


def deduplicate_candidates(candidates: list[SpikeCandidate]) -> list[SpikeCandidate]:
    deduped: dict[str, SpikeCandidate] = {}
    for candidate in candidates:
        deduped.setdefault(candidate.candidate_url, candidate)
    return list(deduped.values())


def csv_safe_row(row: Any) -> dict[str, Any]:
    data = asdict(row) if not isinstance(row, dict) else row
    return {
        key: "; ".join(value) if isinstance(value, tuple) else value
        for key, value in data.items()
    }


def write_csv(path: Path, rows: list[Any], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(csv_safe_row(row))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_summary_rows(candidates: list[SpikeCandidate]) -> list[dict[str, Any]]:
    recommendation_counts = Counter(candidate.recommendation for candidate in candidates)
    path_class_counts = Counter(candidate.path_class for candidate in candidates)
    location_counts = Counter(candidate.location_signal for candidate in candidates)

    rows: list[dict[str, Any]] = []
    for group_name, counts in (
        ("recommendation", recommendation_counts),
        ("path_class", path_class_counts),
        ("location_signal", location_counts),
    ):
        for key, value in sorted(counts.items()):
            rows.append({"group": group_name, "key": key, "count": value})
    return rows


def build_review_markdown(
    *,
    candidates: list[SpikeCandidate],
    pages: list[FetchedPage],
    manifest: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append("# S2J Finanz Informatik Export-First Spike Review")
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append("This spike is read-only and export-first. It does not write to the database, does not fetch detail pages and does not implement a connector.")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- source pages requested: {len(pages)}")
    lines.append(f"- unique candidates exported: {len(candidates)}")
    lines.append(f"- database writes: {manifest['database_writes']}")
    lines.append(f"- detail pages fetched: {manifest['detail_pages_fetched']}")
    lines.append(f"- raw HTML persisted: {manifest['raw_html_persisted']}")
    lines.append("")
    lines.append("## Recommendation Counts")
    lines.append("")
    for key, value in manifest["recommendation_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Strong Listing Candidate Samples")
    lines.append("")
    strong = [c for c in candidates if c.recommendation == "strong_listing_candidate_for_review"]
    for candidate in strong[:30]:
        lines.append(f"- {candidate.candidate_url}")
    if not strong:
        lines.append("- none")
    lines.append("")
    lines.append("## Exclusion Samples")
    lines.append("")
    excluded = [c for c in candidates if c.recommendation.startswith("exclude_")]
    for candidate in excluded[:30]:
        lines.append(f"- {candidate.recommendation}: {candidate.candidate_url}")
    if not excluded:
        lines.append("- none")
    lines.append("")
    lines.append("## Interpretation Boundary")
    lines.append("")
    lines.append("Positive candidates are review candidates only. S2J does not approve Bronze persistence or connector activation.")
    return "\n".join(lines) + "\n"


def build_manifest(
    *,
    export_dir: Path,
    pages: list[FetchedPage],
    candidates: list[SpikeCandidate],
    candidate_path: Path,
    summary_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    status_counts = Counter(str(page.status_code) for page in pages)
    recommendation_counts = Counter(candidate.recommendation for candidate in candidates)
    path_class_counts = Counter(candidate.path_class for candidate in candidates)

    return {
        "mode": "s2j_finanz_informatik_export_first_source_target_spike",
        "database_writes": False,
        "detail_pages_fetched": False,
        "raw_html_persisted": False,
        "connector_implemented": False,
        "source_target_activated": False,
        "source_urls": [page.source_url for page in pages],
        "request_count": len(pages),
        "candidate_count": len(candidates),
        "status_counts": dict(sorted(status_counts.items())),
        "recommendation_counts": dict(sorted(recommendation_counts.items())),
        "path_class_counts": dict(sorted(path_class_counts.items())),
        "export_dir": str(export_dir),
        "output_files": {
            "candidates_csv": str(candidate_path),
            "summary_csv": str(summary_path),
            "review_md": str(review_path),
        },
        "output_sha256": {
            "candidates_csv": sha256_file(candidate_path),
            "summary_csv": sha256_file(summary_path),
            "review_md": sha256_file(review_path) if review_path.exists() else "",
        },
        "interpretation_boundary": (
            "S2J is an export-first spike. Positive rows are review candidates only. "
            "No Bronze persistence, source-target activation or connector decision is made by this script."
        ),
    }


def run_spike(
    *,
    export_dir: Path,
    source_urls: tuple[str, ...] = DEFAULT_SOURCE_URLS,
    timeout_seconds: int = TIMEOUT_SECONDS,
    fetcher: Fetcher = fetch_source_page,
) -> dict[str, Any]:
    export_dir.mkdir(parents=True, exist_ok=True)

    pages = [fetcher(url, timeout_seconds) for url in source_urls]
    links: list[ExtractedLink] = []
    for page in pages:
        if str(page.status_code).startswith("2"):
            links.extend(extract_links(page.html, page.final_url if page.final_url != "-" else page.source_url))

    candidates = deduplicate_candidates([candidate_from_link(link) for link in links])

    candidate_path = export_dir / "finanz_informatik_spike_candidates.csv"
    summary_path = export_dir / "finanz_informatik_spike_relevance_summary.csv"
    manifest_path = export_dir / "finanz_informatik_spike_manifest.json"
    review_path = export_dir / "finanz_informatik_spike_review.md"

    write_csv(
        candidate_path,
        candidates,
        [
            "source_url",
            "candidate_url",
            "candidate_path",
            "candidate_title_or_slug",
            "link_text",
            "host",
            "path_class",
            "location_signal",
            "profile_terms",
            "exclusion_terms",
            "lower_value_scope_terms",
            "recommendation",
            "reason",
            "detail_fetch_needed_later",
            "source_evidence_available_without_detail_fetch",
        ],
    )
    write_csv(summary_path, build_summary_rows(candidates), ["group", "key", "count"])

    manifest = build_manifest(
        export_dir=export_dir,
        pages=pages,
        candidates=candidates,
        candidate_path=candidate_path,
        summary_path=summary_path,
        review_path=review_path,
    )
    review_path.write_text(
        build_review_markdown(candidates=candidates, pages=pages, manifest=manifest),
        encoding="utf-8",
    )
    manifest = build_manifest(
        export_dir=export_dir,
        pages=pages,
        candidates=candidates,
        candidate_path=candidate_path,
        summary_path=summary_path,
        review_path=review_path,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print("S2J Finanz Informatik export-first spike")
    print(f"source_pages: {len(pages)}")
    print(f"candidate_count: {len(candidates)}")
    print("recommendation_counts:", dict(sorted(Counter(c.recommendation for c in candidates).items())))
    print("Exported files:")
    for path in (candidate_path, summary_path, manifest_path, review_path):
        print(f"- {path}")

    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview Finanz Informatik as a bounded export-first source-target spike."
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help="Directory for S2J export artifacts.",
    )
    parser.add_argument(
        "--source-url",
        action="append",
        dest="source_urls",
        help="Configured source URL to inspect. Can be passed multiple times.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=TIMEOUT_SECONDS,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_urls = tuple(args.source_urls or DEFAULT_SOURCE_URLS)
    run_spike(
        export_dir=args.export_dir,
        source_urls=source_urls,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    main()
