from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.finanz_informatik import (
    MAX_DETAIL_PAGES as CONNECTOR_MAX_DETAIL_PAGES,
    FinanzInformatikConnector,
)

DEFAULT_EXPORT_DIR = Path("exports/s2l_finanz_informatik_incremental_uniqueness_review")
DEFAULT_MAX_DETAIL_PAGES = CONNECTOR_MAX_DETAIL_PAGES


def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    value = value.lower()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tokens(value: str | None) -> set[str]:
    return {
        token
        for token in normalize_text(value).split()
        if len(token) >= 3 and token not in {"und", "der", "die", "das", "mit", "mwd", "wmd"}
    }


def token_similarity(left: str | None, right: str | None) -> float:
    left_tokens = tokens(left)
    right_tokens = tokens(right)

    if not left_tokens or not right_tokens:
        return 0.0

    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class Candidate:
    source_candidate_url: str
    page_title: str
    recommendation: str
    matched_profile_terms: str
    matched_location_terms: str

    @property
    def comparison_text(self) -> str:
        return " ".join(
            [
                self.source_candidate_url,
                self.page_title,
                self.matched_profile_terms,
                self.matched_location_terms,
                "Finanz Informatik Hannover",
            ]
        )


@dataclass(frozen=True)
class EvidenceRecord:
    table_name: str
    record_id: str
    source_name: str
    source_url: str
    title: str
    company_name: str
    location: str
    evidence_text: str

    @property
    def comparison_text(self) -> str:
        return " ".join(
            [
                self.source_url,
                self.title,
                self.company_name,
                self.location,
                self.evidence_text,
            ]
        )


@dataclass(frozen=True)
class UniquenessRow:
    source_candidate_url: str
    page_title: str
    candidate_recommendation: str
    matched_profile_terms: str
    matched_location_terms: str
    best_match_table: str
    best_match_record_id: str
    best_match_source_name: str
    best_match_source_url: str
    best_match_title: str
    best_match_company_name: str
    best_match_location: str
    exact_url_match: bool
    title_similarity: float
    evidence_similarity: float
    uniqueness_decision: str
    reason: str


def terms_to_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "; ".join(str(item) for item in value if str(item).strip())
    return ""


def candidate_from_raw_record(record: RawJobRecord) -> Candidate:
    raw_data = record.raw_data or {}
    job = raw_data.get("job", {}) if isinstance(raw_data.get("job"), dict) else {}
    result_card = (
        raw_data.get("result_card", {})
        if isinstance(raw_data.get("result_card"), dict)
        else {}
    )

    title = str(
        job.get("title") or result_card.get("title") or record.external_job_id or ""
    ).strip()
    location = str(job.get("location") or result_card.get("location") or "").strip()
    profile_terms = terms_to_text(job.get("profile_terms"))

    return Candidate(
        source_candidate_url=record.source_url,
        page_title=title,
        recommendation="connector_candidate_record",
        matched_profile_terms=profile_terms,
        matched_location_terms=location,
    )


def load_candidates_from_connector(
    max_detail_pages: int = DEFAULT_MAX_DETAIL_PAGES,
) -> tuple[list[Candidate], str]:
    connector = FinanzInformatikConnector(max_detail_pages=max_detail_pages)

    profile = SearchProfile(
        id=0,
        profile_name="s2l_finanz_informatik_incremental_uniqueness_review",
        source_name="finanz_informatik:hannover",
        search_location=None,
        search_radius_km=None,
        offer_type=None,
        page_size=max_detail_pages,
    )

    records, requested_url = connector.fetch_jobs(profile, SearchTerm(search_term="*"))
    return [candidate_from_raw_record(record) for record in records], requested_url


def fallback_dsn() -> str | None:
    explicit = os.getenv("JOB_PIPELINE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    pgdatabase = os.getenv("PGDATABASE")
    pguser = os.getenv("PGUSER")

    if pgdatabase and pguser:
        parts = [f"dbname={pgdatabase}", f"user={pguser}"]
        if os.getenv("PGHOST"):
            parts.append(f"host={os.getenv('PGHOST')}")
        if os.getenv("PGPORT"):
            parts.append(f"port={os.getenv('PGPORT')}")
        if os.getenv("PGPASSWORD"):
            parts.append(f"password={os.getenv('PGPASSWORD')}")
        return " ".join(parts)

    return None


def load_database_evidence(dsn: str | None) -> tuple[list[EvidenceRecord], str | None]:
    if not dsn:
        return [], "No database DSN configured. Set JOB_PIPELINE_DATABASE_URL, DATABASE_URL or PG* variables."

    try:
        import psycopg
    except ImportError as exc:
        return [], f"psycopg is not installed in this environment: {exc}"

    evidence: list[EvidenceRecord] = []

    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id::text,
                        source_name,
                        COALESCE(source_url, ''),
                        COALESCE(title, ''),
                        COALESCE(company_name, ''),
                        COALESCE(city, ''),
                        CONCAT_WS(' ', source_name, source_url, title, company_name, city, external_job_id)::text
                    FROM silver_jobs
                    WHERE lower(CONCAT_WS(' ', source_name, source_url, title, company_name, city, external_job_id))
                          SIMILAR TO '%(finanz|informatik|hannover|product|owner|entwickler|javascript|software|osplus|versiegelung)%'
                    LIMIT 500
                    """
                )
                for row in cur.fetchall():
                    evidence.append(
                        EvidenceRecord(
                            table_name="silver_jobs",
                            record_id=row[0],
                            source_name=row[1],
                            source_url=row[2],
                            title=row[3],
                            company_name=row[4],
                            location=row[5],
                            evidence_text=row[6],
                        )
                    )

                cur.execute(
                    """
                    SELECT
                        id::text,
                        source_name,
                        COALESCE(source_url, ''),
                        '',
                        '',
                        '',
                        CONCAT_WS(' ', source_name, source_url, external_job_id, raw_data::text)::text
                    FROM raw_jobs
                    WHERE lower(CONCAT_WS(' ', source_name, source_url, external_job_id, raw_data::text))
                          SIMILAR TO '%(finanz|informatik|f-i.de|hannover|product|owner|entwickler|javascript|software|osplus|versiegelung)%'
                    LIMIT 500
                    """
                )
                for row in cur.fetchall():
                    title = extract_title_from_raw_text(row[6])
                    company = "Finanz Informatik" if "finanz" in normalize_text(row[6]) else ""
                    location = "Hannover" if "hannover" in normalize_text(row[6]) else ""
                    evidence.append(
                        EvidenceRecord(
                            table_name="raw_jobs",
                            record_id=row[0],
                            source_name=row[1],
                            source_url=row[2],
                            title=title,
                            company_name=company,
                            location=location,
                            evidence_text=row[6],
                        )
                    )
    except Exception as exc:  # pragma: no cover - environment dependent
        return evidence, f"Database evidence query failed: {exc}"

    return evidence, None


def extract_title_from_raw_text(value: str) -> str:
    patterns = [
        r'"title"\s*:\s*"([^"]+)"',
        r'"titel"\s*:\s*"([^"]+)"',
        r'"candidate_title_or_slug"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return match.group(1)
    return ""


def choose_best_match(candidate: Candidate, evidence: list[EvidenceRecord]) -> tuple[EvidenceRecord | None, bool, float, float]:
    best_record: EvidenceRecord | None = None
    best_title_similarity = 0.0
    best_evidence_similarity = 0.0
    exact_url_match = False

    normalized_candidate_url = normalize_text(candidate.source_candidate_url)

    for record in evidence:
        record_url = normalize_text(record.source_url)
        is_exact_url = bool(record_url and record_url == normalized_candidate_url)
        title_score = token_similarity(candidate.page_title, record.title)
        evidence_score = token_similarity(candidate.comparison_text, record.comparison_text)

        score = max(title_score, evidence_score, 1.0 if is_exact_url else 0.0)
        current_best = max(best_title_similarity, best_evidence_similarity, 1.0 if exact_url_match else 0.0)

        if score > current_best:
            best_record = record
            best_title_similarity = title_score
            best_evidence_similarity = evidence_score
            exact_url_match = is_exact_url

    return best_record, exact_url_match, best_title_similarity, best_evidence_similarity


def classify_uniqueness(
    candidate: Candidate,
    best_match: EvidenceRecord | None,
    exact_url_match: bool,
    title_similarity: float,
    evidence_similarity: float,
    db_error: str | None,
) -> tuple[str, str]:
    if db_error:
        return "manual_review_db_unavailable", db_error

    if best_match is None:
        return "incrementally_unique_candidate", "No relevant raw or Silver evidence was found."

    if exact_url_match:
        return "known_exact_url_match", "The same source URL already exists in project evidence."

    if title_similarity >= 0.82 and evidence_similarity >= 0.35:
        return "likely_known_elsewhere", "Title and evidence similarity are high enough to treat this as probably known."

    if title_similarity >= 0.55 or evidence_similarity >= 0.45:
        return "possible_known_elsewhere_review", "Some evidence overlaps; manual review is needed before claiming incremental uniqueness."

    return "incrementally_unique_candidate", "No sufficiently similar existing evidence was found."


def build_uniqueness_rows(candidates: list[Candidate], evidence: list[EvidenceRecord], db_error: str | None) -> list[UniquenessRow]:
    rows: list[UniquenessRow] = []

    for candidate in candidates:
        best_match, exact_url_match, title_similarity, evidence_similarity = choose_best_match(candidate, evidence)
        decision, reason = classify_uniqueness(
            candidate=candidate,
            best_match=best_match,
            exact_url_match=exact_url_match,
            title_similarity=title_similarity,
            evidence_similarity=evidence_similarity,
            db_error=db_error,
        )

        rows.append(
            UniquenessRow(
                source_candidate_url=candidate.source_candidate_url,
                page_title=candidate.page_title,
                candidate_recommendation=candidate.recommendation,
                matched_profile_terms=candidate.matched_profile_terms,
                matched_location_terms=candidate.matched_location_terms,
                best_match_table=best_match.table_name if best_match else "",
                best_match_record_id=best_match.record_id if best_match else "",
                best_match_source_name=best_match.source_name if best_match else "",
                best_match_source_url=best_match.source_url if best_match else "",
                best_match_title=best_match.title if best_match else "",
                best_match_company_name=best_match.company_name if best_match else "",
                best_match_location=best_match.location if best_match else "",
                exact_url_match=exact_url_match,
                title_similarity=round(title_similarity, 3),
                evidence_similarity=round(evidence_similarity, 3),
                uniqueness_decision=decision,
                reason=reason,
            )
        )

    return rows


def write_review(path: Path, rows: list[UniquenessRow], evidence_count: int, db_error: str | None) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.uniqueness_decision] = counts.get(row.uniqueness_decision, 0) + 1

    lines = [
        "# S2L Finanz Informatik Incremental Uniqueness Review",
        "",
        "## Boundary",
        "",
        "This review is read-only. It compares selected S2K candidates with existing raw and Silver evidence and does not write to the database.",
        "",
        "## Interpretation",
        "",
        "Finanz Informatik is evaluated as a precision source, not as a broad-volume source.",
        "For employer-origin sources, even one relevant non-duplicate candidate may provide source value if it adds incremental evidence not already available from BA or other sources.",
        "",
        "## Counts",
        "",
        f"- candidates reviewed: {len(rows)}",
        f"- database evidence rows considered: {evidence_count}",
        f"- database status: {'unavailable' if db_error else 'available'}",
        "",
        "## Decision Counts",
        "",
    ]

    for key in sorted(counts):
        lines.append(f"- {key}: {counts[key]}")

    if db_error:
        lines += ["", "## Database Note", "", db_error]

    lines += ["", "## Candidate Results", ""]
    for row in rows:
        lines += [
            f"- {row.uniqueness_decision}: {row.page_title}",
            f"  - url: {row.source_candidate_url}",
            f"  - best match: {row.best_match_table or '-'} {row.best_match_record_id or ''} {row.best_match_source_name or ''}".rstrip(),
            f"  - title similarity: {row.title_similarity}",
            f"  - evidence similarity: {row.evidence_similarity}",
            f"  - reason: {row.reason}",
        ]

    lines += [
        "",
        "## Boundary Reminder",
        "",
        "S2L does not approve a connector, Bronze persistence or recurring ingestion.",
        "It only identifies whether the selected Finanz Informatik candidates appear to add incremental source value.",
    ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_review(
    export_dir: Path,
    dsn: str | None,
    max_detail_pages: int = DEFAULT_MAX_DETAIL_PAGES,
) -> dict[str, Any]:
    export_dir.mkdir(parents=True, exist_ok=True)

    candidates, requested_url = load_candidates_from_connector(max_detail_pages=max_detail_pages)
    evidence, db_error = load_database_evidence(dsn)
    rows = build_uniqueness_rows(candidates, evidence, db_error)

    review_path = export_dir / "finanz_informatik_incremental_uniqueness_review.md"
    manifest_path = export_dir / "finanz_informatik_incremental_uniqueness_manifest.json"

    write_review(review_path, rows, len(evidence), db_error)

    decision_counts: dict[str, int] = {}
    for row in rows:
        decision_counts[row.uniqueness_decision] = decision_counts.get(row.uniqueness_decision, 0) + 1

    manifest = {
        "mode": "s2l_finanz_informatik_incremental_uniqueness_review",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input_source": "live_finanz_informatik_connector_candidate_preview_and_current_database_evidence",
        "requested_url": requested_url,
        "export_dir": str(export_dir),
        "candidate_count": len(candidates),
        "database_writes": False,
        "database_available": db_error is None,
        "database_error": db_error or "",
        "evidence_count": len(evidence),
        "decision_counts": decision_counts,
        "output_files": {
            "review_md": str(review_path),
        },
        "output_sha256": {
            "review_md": sha256_file(review_path),
        },
        "interpretation_boundary": "S2L reviews incremental uniqueness only. It does not approve connector activation or Bronze persistence.",
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review Finanz Informatik candidates for incremental uniqueness.")
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--dsn", default=None, help="Optional PostgreSQL DSN. Defaults to JOB_PIPELINE_DATABASE_URL / DATABASE_URL / PG* env vars.")
    parser.add_argument("--max-detail-pages", type=int, default=DEFAULT_MAX_DETAIL_PAGES)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    dsn = args.dsn or fallback_dsn()
    manifest = run_review(args.export_dir, dsn, args.max_detail_pages)

    print("S2L Finanz Informatik incremental uniqueness review")
    print(f"candidate_count: {manifest['candidate_count']}")
    print(f"database_available: {manifest['database_available']}")
    print(f"decision_counts: {manifest['decision_counts']}")
    print("Exported files:")
    for path in manifest["output_files"].values():
        print(f"- {path}")


if __name__ == "__main__":
    main()
