"""Tiny Finanz Informatik detail-page probe.

S2K is intentionally small, read-only and export-first. It reads the S2J
candidate export, selects only a tiny set of Hannover listing-level candidates
that were explicitly marked as detail-fetch candidates, fetches at most a small
number of detail pages, and writes review artifacts under exports/.

It does not write to the database, does not implement a connector and does not
activate Finanz Informatik as a source target.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html as html_lib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_CANDIDATES_CSV = Path(
    "exports/s2j_finanz_informatik_export_first_spike/finanz_informatik_spike_candidates.csv"
)
DEFAULT_EXPORT_DIR = Path("exports/s2k_finanz_informatik_detail_page_probe")
DEFAULT_MAX_DETAIL_PAGES = 3
DEFAULT_TIMEOUT_SECONDS = 20

ALLOWED_RECOMMENDATIONS = {
    "strong_listing_candidate_for_review",
    "job_candidate_low_profile_signal",
}

PROFILE_TERMS = (
    "data engineer",
    "data",
    "daten",
    "analytics",
    "analyst",
    "business analyst",
    "business intelligence",
    "bi",
    "sql",
    "python",
    "ki",
    "ai",
    "artificial intelligence",
    "machine learning",
    "product owner",
    "produkt owner",
    "produktverantwort",
    "software",
    "entwickler",
    "javascript",
    "java script",
    "ui",
)

LOCATION_TERMS = (
    "hannover",
    "remote",
    "hybrid",
    "mobiles arbeiten",
    "homeoffice",
    "deutschlandweit",
    "bundesweit",
)

EXCLUSION_TERMS = (
    "duales studium",
    "ausbildung",
    "werkstudent",
    "werkstudierende",
    "praktikum",
    "trainee",
)


@dataclass(frozen=True)
class ListingCandidate:
    source_url: str
    candidate_url: str
    candidate_path: str
    listing_recommendation: str
    listing_location_signal: str
    listing_profile_terms: tuple[str, ...]
    listing_reason: str


@dataclass(frozen=True)
class FetchedPage:
    source_url: str
    status_code: int | None
    final_url: str
    html: str
    html_bytes: int
    error: str = ""


@dataclass(frozen=True)
class DetailProbeRow:
    source_candidate_url: str
    final_url: str
    status_code: int | None
    page_title: str
    html_bytes: int
    matched_profile_terms: tuple[str, ...]
    matched_location_terms: tuple[str, ...]
    matched_exclusion_terms: tuple[str, ...]
    listing_recommendation: str
    listing_location_signal: str
    recommendation: str
    reason: str
    text_excerpt: str
    error: str = ""


def normalize_terms(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(";") if part.strip())


def load_listing_candidates(path: Path, max_detail_pages: int) -> list[ListingCandidate]:
    """Load only the tiny allowed candidate set from the S2J export."""
    if not path.exists():
        raise FileNotFoundError(
            f"Missing S2J candidate export: {path}. Run "
            "`python -m scripts.preview_finanz_informatik_source_target_spike` first."
        )

    candidates: list[ListingCandidate] = []

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            recommendation = row.get("recommendation", "")
            location_signal = row.get("location_signal", "")
            detail_flag = row.get("detail_fetch_needed_later", "").lower() == "true"
            candidate_url = row.get("candidate_url", "")

            if recommendation not in ALLOWED_RECOMMENDATIONS:
                continue
            if location_signal != "hannover":
                continue
            if not detail_flag:
                continue
            if not candidate_url:
                continue

            candidates.append(
                ListingCandidate(
                    source_url=row.get("source_url", ""),
                    candidate_url=candidate_url,
                    candidate_path=row.get("candidate_path", ""),
                    listing_recommendation=recommendation,
                    listing_location_signal=location_signal,
                    listing_profile_terms=normalize_terms(row.get("profile_terms", "")),
                    listing_reason=row.get("reason", ""),
                )
            )

            if len(candidates) >= max_detail_pages:
                break

    return candidates


def fetch_url(url: str, timeout_seconds: int) -> FetchedPage:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "job-application-pipeline/0.1 "
                "(bounded read-only source-target spike; contact: portfolio project)"
            )
        },
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            return FetchedPage(
                source_url=url,
                status_code=response.status,
                final_url=response.geturl(),
                html=raw.decode(charset, errors="replace"),
                html_bytes=len(raw),
            )
    except HTTPError as exc:
        return FetchedPage(
            source_url=url,
            status_code=exc.code,
            final_url=url,
            html="",
            html_bytes=0,
            error=f"HTTPError: {exc}",
        )
    except URLError as exc:
        return FetchedPage(
            source_url=url,
            status_code=None,
            final_url=url,
            html="",
            html_bytes=0,
            error=f"URLError: {exc}",
        )


def strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_title(html: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if not match:
        return ""
    return strip_html(match.group(1))


def find_terms(text: str, terms: Iterable[str]) -> tuple[str, ...]:
    lowered = text.lower()
    matches = []
    for term in terms:
        if term in lowered:
            matches.append(term)
    return tuple(dict.fromkeys(matches))


def excerpt_text(text: str, max_chars: int = 350) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"


def recommendation_for_detail(
    status_code: int | None,
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
    exclusion_terms: tuple[str, ...],
    error: str,
) -> tuple[str, str]:
    if error or status_code != 200:
        return "detail_fetch_failed_or_not_ok", "Detail page could not be fetched successfully."

    if exclusion_terms:
        return "exclude_detail_scope", "Detail page contains exclusion terms."

    has_profile = bool(profile_terms)
    has_target_or_remote = any(
        term in location_terms
        for term in (
            "hannover",
            "remote",
            "hybrid",
            "mobiles arbeiten",
            "homeoffice",
            "deutschlandweit",
            "bundesweit",
        )
    )

    if has_profile and has_target_or_remote:
        return (
            "detail_candidate_supports_future_preview",
            "Detail page contains profile and target/remote signals.",
        )

    if has_target_or_remote:
        return (
            "detail_candidate_needs_manual_review",
            "Detail page contains target/remote signals but weak profile evidence.",
        )

    if has_profile:
        return (
            "detail_profile_signal_without_location_confirmation",
            "Detail page contains profile signals but no target/remote confirmation.",
        )

    return (
        "detail_low_signal_defer",
        "Detail page does not provide enough profile or target-location evidence.",
    )


def evaluate_detail(candidate: ListingCandidate, page: FetchedPage) -> DetailProbeRow:
    page_title = extract_title(page.html)
    text = strip_html(page.html)

    relevance_text = " ".join(
        [
            candidate.candidate_url,
            candidate.candidate_path,
            page_title,
            text,
        ]
    )
    exclusion_scope_text = " ".join(
        [
            candidate.candidate_url,
            candidate.candidate_path,
            page_title,
        ]
    )

    profile_terms = find_terms(relevance_text, PROFILE_TERMS)
    location_terms = find_terms(relevance_text, LOCATION_TERMS)
    exclusion_terms = find_terms(exclusion_scope_text, EXCLUSION_TERMS)
    recommendation, reason = recommendation_for_detail(
        page.status_code,
        profile_terms,
        location_terms,
        exclusion_terms,
        page.error,
    )

    return DetailProbeRow(
        source_candidate_url=candidate.candidate_url,
        final_url=page.final_url,
        status_code=page.status_code,
        page_title=page_title,
        html_bytes=page.html_bytes,
        matched_profile_terms=profile_terms,
        matched_location_terms=location_terms,
        matched_exclusion_terms=exclusion_terms,
        listing_recommendation=candidate.listing_recommendation,
        listing_location_signal=candidate.listing_location_signal,
        recommendation=recommendation,
        reason=reason,
        text_excerpt=excerpt_text(text),
        error=page.error,
    )


def tuple_to_cell(value: tuple[str, ...]) -> str:
    return "; ".join(value)


def write_detail_csv(path: Path, rows: list[DetailProbeRow]) -> None:
    fieldnames = [
        "source_candidate_url",
        "final_url",
        "status_code",
        "page_title",
        "html_bytes",
        "matched_profile_terms",
        "matched_location_terms",
        "matched_exclusion_terms",
        "listing_recommendation",
        "listing_location_signal",
        "recommendation",
        "reason",
        "text_excerpt",
        "error",
    ]

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            data = asdict(row)
            data["matched_profile_terms"] = tuple_to_cell(row.matched_profile_terms)
            data["matched_location_terms"] = tuple_to_cell(row.matched_location_terms)
            data["matched_exclusion_terms"] = tuple_to_cell(row.matched_exclusion_terms)
            writer.writerow(data)


def write_summary_csv(path: Path, rows: list[DetailProbeRow]) -> None:
    counts = Counter(row.recommendation for row in rows)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["recommendation", "count"])
        writer.writeheader()
        for recommendation, count in sorted(counts.items()):
            writer.writerow({"recommendation": recommendation, "count": count})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_review(rows: list[DetailProbeRow], manifest: dict[str, object]) -> str:
    counts = Counter(row.recommendation for row in rows)
    lines: list[str] = [
        "# S2K Finanz Informatik Detail-Page Probe Review",
        "",
        "## Boundary",
        "",
        "This probe is tiny, read-only and export-first. It fetches only selected S2J Hannover candidates and does not write to the database, implement a connector or activate a source target.",
        "",
        "## Counts",
        "",
        f"- detail pages requested: {manifest['request_count']}",
        f"- database writes: {manifest['database_writes']}",
        f"- raw HTML persisted: {manifest['raw_html_persisted']}",
        f"- connector implemented: {manifest['connector_implemented']}",
        "",
        "## Recommendation Counts",
        "",
    ]

    for recommendation, count in sorted(counts.items()):
        lines.append(f"- {recommendation}: {count}")

    lines.extend(["", "## Detail Candidate Samples", ""])

    for row in rows:
        lines.append(f"- {row.recommendation}: {row.source_candidate_url}")
        if row.matched_profile_terms:
            lines.append(f"  - profile: {tuple_to_cell(row.matched_profile_terms)}")
        if row.matched_location_terms:
            lines.append(f"  - location/remote: {tuple_to_cell(row.matched_location_terms)}")
        if row.matched_exclusion_terms:
            lines.append(f"  - exclusions: {tuple_to_cell(row.matched_exclusion_terms)}")
        lines.append(f"  - reason: {row.reason}")

    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "Positive rows are evidence for manual review only. S2K does not approve Bronze persistence, connector activation or recurring ingestion.",
        ]
    )

    return "\n".join(lines) + "\n"


def run_probe(
    *,
    candidates_csv: Path,
    export_dir: Path,
    max_detail_pages: int,
    timeout_seconds: int,
    fetcher: Callable[[str, int], FetchedPage] = fetch_url,
) -> dict[str, object]:
    export_dir.mkdir(parents=True, exist_ok=True)

    candidates = load_listing_candidates(candidates_csv, max_detail_pages=max_detail_pages)
    rows = [
        evaluate_detail(candidate, fetcher(candidate.candidate_url, timeout_seconds))
        for candidate in candidates
    ]

    detail_csv = export_dir / "finanz_informatik_detail_page_probe.csv"
    summary_csv = export_dir / "finanz_informatik_detail_page_probe_summary.csv"
    manifest_path = export_dir / "finanz_informatik_detail_page_probe_manifest.json"
    review_path = export_dir / "finanz_informatik_detail_page_probe_review.md"

    write_detail_csv(detail_csv, rows)
    write_summary_csv(summary_csv, rows)

    manifest: dict[str, object] = {
        "mode": "s2k_finanz_informatik_tiny_detail_page_probe",
        "candidate_source_csv": str(candidates_csv),
        "export_dir": str(export_dir),
        "max_detail_pages": max_detail_pages,
        "request_count": len(rows),
        "database_writes": False,
        "raw_html_persisted": False,
        "connector_implemented": False,
        "source_target_activated": False,
        "bronze_persistence_approved": False,
        "detail_pages_fetched": True,
        "recommendation_counts": dict(Counter(row.recommendation for row in rows)),
        "status_counts": dict(Counter(str(row.status_code) for row in rows)),
        "output_files": {
            "detail_csv": str(detail_csv),
            "summary_csv": str(summary_csv),
            "review_md": str(review_path),
        },
        "interpretation_boundary": (
            "S2K is a tiny detail-page probe for selected S2J candidates. "
            "Positive rows are manual review evidence only."
        ),
    }

    review_path.write_text(build_review(rows, manifest), encoding="utf-8")

    manifest["output_sha256"] = {
        "detail_csv": sha256_file(detail_csv),
        "summary_csv": sha256_file(summary_csv),
        "review_md": sha256_file(review_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates-csv", type=Path, default=DEFAULT_CANDIDATES_CSV)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--max-detail-pages", type=int, default=DEFAULT_MAX_DETAIL_PAGES)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = run_probe(
        candidates_csv=args.candidates_csv,
        export_dir=args.export_dir,
        max_detail_pages=args.max_detail_pages,
        timeout_seconds=args.timeout_seconds,
    )

    print("S2K Finanz Informatik tiny detail-page probe")
    print(f"request_count: {manifest['request_count']}")
    print(f"recommendation_counts: {manifest['recommendation_counts']}")
    print("Exported files:")
    for output_file in manifest["output_files"].values():
        print(f"- {output_file}")


if __name__ == "__main__":
    main()
