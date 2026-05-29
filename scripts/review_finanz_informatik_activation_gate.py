"""DB-backed Finanz Informatik activation gate review.

S2N fetches the current bounded Finanz Informatik connector-candidate preview,
compares the resulting candidate records against current raw/Silver database
evidence by reusing the S2L incremental-uniqueness logic, and writes generated
review artifacts as outputs.

If the database is unavailable, S2N fails instead of producing a gate decision.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from scripts.review_finanz_informatik_incremental_uniqueness import (
    Candidate,
    EvidenceRecord,
    UniquenessRow,
    build_uniqueness_rows,
    fallback_dsn,
    load_database_evidence,
    sha256_file,
)
from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.finanz_informatik import (
    MAX_DETAIL_PAGES as CONNECTOR_MAX_DETAIL_PAGES,
    FinanzInformatikConnector,
)

DEFAULT_EXPORT_DIR = Path("exports/s2n_finanz_informatik_activation_gate")
DEFAULT_MAX_DETAIL_PAGES = CONNECTOR_MAX_DETAIL_PAGES


class ConnectorLike(Protocol):
    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        ...


@dataclass(frozen=True)
class ActivationGateRow:
    source_candidate_url: str
    page_title: str
    source_name: str
    external_job_id: str
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
    activation_gate_decision: str
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

    title = (
        str(job.get("title") or result_card.get("title") or record.external_job_id or "")
        .strip()
    )
    location = str(job.get("location") or result_card.get("location") or "").strip()
    profile_terms = terms_to_text(job.get("profile_terms"))

    return Candidate(
        source_candidate_url=record.source_url,
        page_title=title,
        recommendation="connector_candidate_record",
        matched_profile_terms=profile_terms,
        matched_location_terms=location,
    )


def preview_connector_records(
    connector: ConnectorLike | None = None,
    max_detail_pages: int = DEFAULT_MAX_DETAIL_PAGES,
) -> tuple[list[RawJobRecord], str]:
    active_connector = connector or FinanzInformatikConnector(max_detail_pages=max_detail_pages)

    profile = SearchProfile(
        id=0,
        profile_name="s2n_finanz_informatik_activation_gate_preview",
        source_name="finanz_informatik:hannover",
        search_location=None,
        search_radius_km=None,
        offer_type=None,
        page_size=max_detail_pages,
    )

    return active_connector.fetch_jobs(profile, SearchTerm(search_term="*"))


def classify_activation_gate(row: UniquenessRow) -> tuple[str, str]:
    if row.uniqueness_decision == "manual_review_db_unavailable":
        return (
            "activation_gate_blocked_db_unavailable",
            "Activation gate cannot be evaluated without current database evidence.",
        )

    if row.uniqueness_decision in {"known_exact_url_match", "likely_known_elsewhere"}:
        return (
            "activation_gate_defer_known_elsewhere",
            "Candidate is already known or likely known elsewhere.",
        )

    if row.uniqueness_decision == "possible_known_elsewhere_review":
        return (
            "activation_gate_needs_manual_overlap_review",
            "Candidate has enough overlap with existing evidence to require manual duplicate review.",
        )

    if row.uniqueness_decision == "incrementally_unique_candidate":
        return (
            "activation_gate_incremental_value_candidate",
            "Candidate appears to add incremental source value compared with current raw/Silver evidence.",
        )

    return (
        "activation_gate_manual_review",
        "Unexpected uniqueness decision; manual review required.",
    )


def activation_rows_from_uniqueness(
    records: list[RawJobRecord],
    uniqueness_rows: list[UniquenessRow],
) -> list[ActivationGateRow]:
    records_by_url = {record.source_url: record for record in records}
    rows: list[ActivationGateRow] = []

    for unique_row in uniqueness_rows:
        record = records_by_url.get(unique_row.source_candidate_url)
        activation_decision, activation_reason = classify_activation_gate(unique_row)

        rows.append(
            ActivationGateRow(
                source_candidate_url=unique_row.source_candidate_url,
                page_title=unique_row.page_title,
                source_name=record.source_name if record else "",
                external_job_id=(record.external_job_id if record and record.external_job_id else ""),
                matched_profile_terms=unique_row.matched_profile_terms,
                matched_location_terms=unique_row.matched_location_terms,
                best_match_table=unique_row.best_match_table,
                best_match_record_id=unique_row.best_match_record_id,
                best_match_source_name=unique_row.best_match_source_name,
                best_match_source_url=unique_row.best_match_source_url,
                best_match_title=unique_row.best_match_title,
                best_match_company_name=unique_row.best_match_company_name,
                best_match_location=unique_row.best_match_location,
                exact_url_match=unique_row.exact_url_match,
                title_similarity=unique_row.title_similarity,
                evidence_similarity=unique_row.evidence_similarity,
                uniqueness_decision=unique_row.uniqueness_decision,
                activation_gate_decision=activation_decision,
                reason=f"{unique_row.reason} Activation interpretation: {activation_reason}",
            )
        )

    return rows


def summarize_overall_decision(rows: list[ActivationGateRow]) -> str:
    if not rows:
        return "activation_gate_blocked_no_candidates"

    decisions = Counter(row.activation_gate_decision for row in rows)

    if decisions.get("activation_gate_blocked_db_unavailable"):
        return "activation_gate_blocked_db_unavailable"

    if decisions.get("activation_gate_incremental_value_candidate"):
        if decisions.get("activation_gate_needs_manual_overlap_review"):
            return "controlled_inactive_preview_supported_with_manual_overlap_review"
        return "controlled_inactive_preview_supported"

    if decisions.get("activation_gate_needs_manual_overlap_review"):
        return "manual_overlap_review_required_before_activation"

    if decisions.get("activation_gate_defer_known_elsewhere") == len(rows):
        return "defer_activation_known_elsewhere"

    return "manual_review_required"


def write_review(
    path: Path,
    rows: list[ActivationGateRow],
    evidence_count: int,
    requested_url: str,
    overall_decision: str,
) -> None:
    activation_counts = Counter(row.activation_gate_decision for row in rows)
    uniqueness_counts = Counter(row.uniqueness_decision for row in rows)

    lines = [
        "# S2N Finanz Informatik Activation Gate Review",
        "",
        "## Boundary",
        "",
        "This review is DB-backed and connector-preview-backed.",
        "It does not write to the database, activate a source target, approve Bronze persistence or enable recurring ingestion.",
        "",
        "Generated review artifacts are outputs only.",
        "",
        "## Inputs",
        "",
        f"- live connector candidate requested URL: {requested_url}",
        f"- database evidence rows considered: {evidence_count}",
        "- S2L uniqueness logic reused directly from `scripts.review_finanz_informatik_incremental_uniqueness`",
        "",
        "## Overall Decision",
        "",
        f"- {overall_decision}",
        "",
        "## Activation Gate Counts",
        "",
    ]

    for key in sorted(activation_counts):
        lines.append(f"- {key}: {activation_counts[key]}")

    lines += ["", "## Uniqueness Counts", ""]
    for key in sorted(uniqueness_counts):
        lines.append(f"- {key}: {uniqueness_counts[key]}")

    lines += ["", "## Candidate Results", ""]
    for row in rows:
        lines += [
            f"- `{row.activation_gate_decision}` — {row.page_title}",
            f"  - uniqueness decision: {row.uniqueness_decision}",
            f"  - url: {row.source_candidate_url}",
            f"  - external job id: {row.external_job_id or '-'}",
            f"  - profile terms: {row.matched_profile_terms or '-'}",
            f"  - location terms: {row.matched_location_terms or '-'}",
            f"  - best match: {row.best_match_table or '-'} {row.best_match_record_id or ''} {row.best_match_source_name or ''}".rstrip(),
            f"  - best match title: {row.best_match_title or '-'}",
            f"  - best match company: {row.best_match_company_name or '-'}",
            f"  - best match location: {row.best_match_location or '-'}",
            f"  - best match source url: {row.best_match_source_url or '-'}",
            f"  - title similarity: {row.title_similarity}",
            f"  - evidence similarity: {row.evidence_similarity}",
            f"  - reason: {row.reason}",
        ]

    lines += [
        "",
        "## Interpretation",
        "",
        "Finanz Informatik remains a precision-source candidate.",
        "A small number of relevant, incrementally unique employer-origin jobs can justify controlled preview work even when source volume is low.",
        "",
        "The next step may be a controlled inactive source-target implementation only if manual overlap review is accepted.",
        "Broad recurring ingestion and Bronze persistence remain deferred.",
    ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_activation_gate(
    export_dir: Path,
    dsn: str | None,
    connector: ConnectorLike | None = None,
    evidence_override: list[EvidenceRecord] | None = None,
    db_error_override: str | None = None,
    max_detail_pages: int = DEFAULT_MAX_DETAIL_PAGES,
) -> dict[str, Any]:
    export_dir.mkdir(parents=True, exist_ok=True)

    records, requested_url = preview_connector_records(
        connector=connector,
        max_detail_pages=max_detail_pages,
    )
    candidates = [candidate_from_raw_record(record) for record in records]

    if evidence_override is None:
        evidence, db_error = load_database_evidence(dsn)
    else:
        evidence = evidence_override
        db_error = db_error_override

    if db_error:
        raise RuntimeError(
            "S2N activation gate requires current database evidence. "
            f"Database evidence loading failed: {db_error}"
        )

    uniqueness_rows = build_uniqueness_rows(candidates, evidence, db_error=None)
    activation_rows = activation_rows_from_uniqueness(records, uniqueness_rows)
    overall_decision = summarize_overall_decision(activation_rows)

    review_md = export_dir / "finanz_informatik_activation_gate_review.md"
    manifest_path = export_dir / "finanz_informatik_activation_gate_manifest.json"

    write_review(
        review_md,
        activation_rows,
        evidence_count=len(evidence),
        requested_url=requested_url,
        overall_decision=overall_decision,
    )

    activation_counts = Counter(row.activation_gate_decision for row in activation_rows)
    uniqueness_counts = Counter(row.uniqueness_decision for row in activation_rows)

    manifest = {
        "mode": "s2n_finanz_informatik_activation_gate",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input_source": "live_finanz_informatik_connector_candidate_preview_and_current_database_evidence",
        "export_dir": str(export_dir),
        "requested_url": requested_url,
        "candidate_count": len(records),
        "evidence_count": len(evidence),
        "database_writes": False,
        "database_available": True,
        "connector_registered_for_ingestion": False,
        "bronze_persistence_approved": False,
        "recurring_ingestion_approved": False,
        "overall_decision": overall_decision,
        "activation_gate_counts": dict(activation_counts),
        "uniqueness_counts": dict(uniqueness_counts),
        "output_files": {
            "review_md": str(review_md),
        },
        "output_sha256": {
            "review_md": sha256_file(review_md),
        },
        "interpretation_boundary": (
            "S2N is an activation gate review only. It may support a controlled "
            "inactive source-target preview, but it does not approve Bronze persistence "
            "or recurring ingestion."
        ),
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the DB-backed Finanz Informatik activation gate review.")
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--dsn", default=None, help="Optional PostgreSQL DSN. Defaults to JOB_PIPELINE_DATABASE_URL / DATABASE_URL / PG* env vars.")
    parser.add_argument("--max-detail-pages", type=int, default=DEFAULT_MAX_DETAIL_PAGES)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    dsn = args.dsn or fallback_dsn()
    manifest = run_activation_gate(
        export_dir=args.export_dir,
        dsn=dsn,
        max_detail_pages=args.max_detail_pages,
    )

    print("S2N Finanz Informatik activation gate review")
    print(f"candidate_count: {manifest['candidate_count']}")
    print(f"database_available: {manifest['database_available']}")
    print(f"overall_decision: {manifest['overall_decision']}")
    print(f"activation_gate_counts: {manifest['activation_gate_counts']}")
    print("Exported files:")
    for path in manifest["output_files"].values():
        print(f"- {path}")


if __name__ == "__main__":
    main()
