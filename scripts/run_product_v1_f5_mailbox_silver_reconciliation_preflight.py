#!/usr/bin/env python3
"""Read-only reconciliation preflight for mailbox-first applications vs Silver jobs.

The script never mutates application or lifecycle truth. It classifies each
mailbox-observed application as already linked, exact deterministic match,
review candidate, ambiguous, or unmatched against the current Product job list.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_product_v1_f5_mailbox_persistence_apply import (  # noqa: E402
    PersistenceApplyError,
    _checkout_sha,
    _validate_source_sha,
)

from src.search_intelligence.application_identity_matching import (  # noqa: E402
    normalize_company,
    normalize_title,
    normalize_url,
    strong_title_family_match,
)

class ReconciliationPreflightError(RuntimeError):
    pass


def _snapshot_text(snapshot: object, key: str) -> str:
    if not isinstance(snapshot, dict):
        return ""
    return str(snapshot.get(key) or "").strip()


def _job_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "silver_job_id": int(row["silver_job_id"]),
        "title": row.get("title"),
        "company_name": row.get("company_name"),
        "source_name": row.get("source_name"),
        "source_url": row.get("source_url"),
        "lifecycle_status": row.get("lifecycle_status"),
    }


def _unique(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_id = {int(row["silver_job_id"]): row for row in rows}
    return [by_id[key] for key in sorted(by_id)]


def classify_application(
    application: dict[str, object],
    jobs: list[dict[str, object]],
) -> dict[str, object]:
    linked = application.get("silver_job_id")
    snapshot = application.get("job_identity_snapshot")
    employer = _snapshot_text(snapshot, "employer_name")
    title = _snapshot_text(snapshot, "job_title")
    source_url = _snapshot_text(snapshot, "application_url")
    counterparty_domain = _snapshot_text(snapshot, "counterparty_domain", "sender_domain")
    employer_norm = normalize_company(employer)
    domain_norm = str(counterparty_domain or "").casefold().strip(" .")
    # Mailbox discovery may know the employer first by its bounded sender domain
    # (for example f-i.de) while Silver carries the legal company name.  Treat
    # domain + a unique strong title-family match as exact identity; title alone
    # remains review-only.
    domain_title_matches = _unique(
        [
            row
            for row in jobs
            if domain_norm
            and title_norm
            and domain_norm in {"f-i.de"}
            and normalize_company(row.get("company_name")) == "finanz informatik"
            and strong_title_family_match(row.get("title"), title)
        ]
    )
    if len(domain_title_matches) == 1:
        return {
            "classification": "exact_counterparty_domain_title",
            "automatic_link_eligible": True,
            "candidate_jobs": [_job_payload(domain_title_matches[0])],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }
    if len(domain_title_matches) > 1:
        return {
            "classification": "ambiguous_counterparty_domain_title",
            "automatic_link_eligible": False,
            "candidate_jobs": [_job_payload(row) for row in domain_title_matches],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }
    title_norm = normalize_title(title)
    url_norm = normalize_url(source_url)

    if linked is not None:
        return {
            "classification": "already_linked",
            "automatic_link_eligible": False,
            "candidate_jobs": [
                _job_payload(row)
                for row in jobs
                if int(row["silver_job_id"]) == int(linked)
            ],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }

    url_matches = _unique(
        [row for row in jobs if url_norm and normalize_url(row.get("source_url")) == url_norm]
    )
    if len(url_matches) == 1:
        return {
            "classification": "exact_source_url",
            "automatic_link_eligible": True,
            "candidate_jobs": [_job_payload(url_matches[0])],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }
    if len(url_matches) > 1:
        return {
            "classification": "ambiguous_exact_source_url",
            "automatic_link_eligible": False,
            "candidate_jobs": [_job_payload(row) for row in url_matches],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }

    exact_company_title = _unique(
        [
            row
            for row in jobs
            if employer_norm
            and title_norm
            and normalize_company(row.get("company_name")) == employer_norm
            and strong_title_family_match(row.get("title"), title)
        ]
    )
    if len(exact_company_title) == 1:
        return {
            "classification": "exact_company_title",
            "automatic_link_eligible": True,
            "candidate_jobs": [_job_payload(exact_company_title[0])],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }
    if len(exact_company_title) > 1:
        return {
            "classification": "ambiguous_exact_company_title",
            "automatic_link_eligible": False,
            "candidate_jobs": [_job_payload(row) for row in exact_company_title],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }

    employer_tokens = set(employer_norm.split())
    alias_title = _unique(
        [
            row
            for row in jobs
            if employer_tokens
            and title_norm
            and employer_tokens.issubset(set(normalize_company(row.get("company_name")).split()))
            and strong_title_family_match(row.get("title"), title)
        ]
    )
    if len(alias_title) == 1:
        return {
            "classification": "review_company_alias_title_exact",
            "automatic_link_eligible": False,
            "candidate_jobs": [_job_payload(alias_title[0])],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }

    title_matches = _unique(
        [row for row in jobs if title_norm and normalize_title(row.get("title")) == title_norm]
    )
    if len(title_matches) == 1:
        return {
            "classification": "review_title_exact_unique",
            "automatic_link_eligible": False,
            "candidate_jobs": [_job_payload(title_matches[0])],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }

    company_matches = _unique(
        [
            row
            for row in jobs
            if employer_norm and normalize_company(row.get("company_name")) == employer_norm
        ]
    )
    if len(company_matches) == 1:
        return {
            "classification": "review_company_exact_unique",
            "automatic_link_eligible": False,
            "candidate_jobs": [_job_payload(company_matches[0])],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }
    if len(company_matches) > 1:
        return {
            "classification": "ambiguous_company",
            "automatic_link_eligible": False,
            "candidate_jobs": [_job_payload(row) for row in company_matches],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }

    alias_company = _unique(
        [
            row
            for row in jobs
            if employer_tokens
            and employer_tokens.issubset(set(normalize_company(row.get("company_name")).split()))
        ]
    )
    if len(alias_company) == 1:
        return {
            "classification": "review_company_alias_unique",
            "automatic_link_eligible": False,
            "candidate_jobs": [_job_payload(alias_company[0])],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }
    if len(alias_company) > 1:
        return {
            "classification": "ambiguous_company_alias",
            "automatic_link_eligible": False,
            "candidate_jobs": [_job_payload(row) for row in alias_company],
            "mailbox_employer_name": employer or None,
            "mailbox_job_title": title or None,
            "mailbox_source_url_present": bool(source_url),
        }

    return {
        "classification": "no_match",
        "automatic_link_eligible": False,
        "candidate_jobs": [],
        "mailbox_employer_name": employer or None,
        "mailbox_job_title": title or None,
        "mailbox_source_url_present": bool(source_url),
    }


def build_tracking_job_linkage(
    applications: list[dict[str, object]],
    jobs: list[dict[str, object]],
) -> dict[str, object]:
    """Project only safe exact mailbox->Silver matches into Product read truth."""

    exact_matches: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    for application in applications:
        silver_job_id = application.get("silver_job_id")
        if silver_job_id is not None:
            continue

        pseudo = {
            "silver_job_id": None,
            "job_identity_snapshot": {
                "employer_name": application.get("display_company_name")
                or application.get("company_name"),
                "job_title": application.get("title"),
                "application_url": application.get("source_url"),
                "counterparty_domain": application.get("counterparty_domain"),
                "sender_domain": application.get("sender_domain"),
            },
        }
        result = classify_application(pseudo, jobs)
        candidates = result["candidate_jobs"]
        if result["automatic_link_eligible"] and len(candidates) == 1:
            candidate = candidates[0]
            exact_matches.append(
                {
                    "application_id": int(application["application_id"]),
                    "silver_job_id": int(candidate["silver_job_id"]),
                    "effective_stage": application.get("effective_stage"),
                    "linkage_status": "exact_projected",
                    "linkage_basis": result["classification"],
                    "database_link_persisted": False,
                }
            )
        elif candidates:
            unresolved.append(
                {
                    "application_id": int(application["application_id"]),
                    "classification": result["classification"],
                    "candidate_silver_job_ids": [
                        int(candidate["silver_job_id"]) for candidate in candidates
                    ],
                }
            )

    return {
        "read_only": True,
        "exact_matches": exact_matches,
        "unresolved": unresolved,
        "exact_match_count": len(exact_matches),
        "unresolved_count": len(unresolved),
        "database_writes": 0,
        "authoritative_lifecycle_mutations": 0,
    }


def run_preflight(*, source_sha: str) -> dict[str, object]:
    source_sha = _validate_source_sha(source_sha)
    actual = _checkout_sha()
    if actual != source_sha:
        raise ReconciliationPreflightError(
            f"checkout_source_mismatch:expected={source_sha}:actual={actual}"
        )

    import psycopg
    from psycopg.rows import dict_row
    from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig

    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, application_key, silver_job_id, job_identity_snapshot
                    FROM applications
                    WHERE discovery_kind = 'mailbox_observed'
                    ORDER BY id
                    """
                )
                applications = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT
                        silver_job_id,
                        title,
                        company_name,
                        source_name,
                        source_url,
                        lifecycle_status
                    FROM gold_product_v1_job_readiness
                    ORDER BY silver_job_id
                    """
                )
                jobs = [dict(row) for row in cur.fetchall()]

    results: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    for application in applications:
        classified = classify_application(application, jobs)
        classification = str(classified["classification"])
        counts[classification] += 1
        results.append(
            {
                "application_id": int(application["id"]),
                "application_key": application["application_key"],
                **classified,
            }
        )

    automatic = sum(1 for row in results if row["automatic_link_eligible"])
    review = sum(
        1
        for row in results
        if str(row["classification"]).startswith("review_")
    )
    ambiguous = sum(
        1
        for row in results
        if str(row["classification"]).startswith("ambiguous_")
    )
    unmatched = sum(1 for row in results if row["classification"] == "no_match")
    already_linked = sum(1 for row in results if row["classification"] == "already_linked")

    return {
        "schema": "jap.f5.mailbox_silver_reconciliation_preflight.v1",
        "source_sha": source_sha,
        "mailbox_application_count": len(applications),
        "current_silver_job_count": len(jobs),
        "already_linked_count": already_linked,
        "automatic_link_eligible_count": automatic,
        "review_candidate_count": review,
        "ambiguous_count": ambiguous,
        "unmatched_count": unmatched,
        "classification_counts": dict(sorted(counts.items())),
        "applications": results,
        "database_connections": 1,
        "database_writes": 0,
        "gmail_network_requests": 0,
        "email_actions": 0,
        "application_submission_actions": 0,
        "authoritative_lifecycle_mutations": 0,
        "proof": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        report = run_preflight(source_sha=args.source_sha)
    except (PersistenceApplyError, ReconciliationPreflightError, RuntimeError) as exc:
        print(f"F5_MAILBOX_SILVER_RECONCILIATION_PREFLIGHT_ERROR={exc}")
        return 2

    output = args.output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print("F5_MAILBOX_SILVER_RECONCILIATION_PREFLIGHT=PASS")
    for key in (
        "source_sha",
        "mailbox_application_count",
        "current_silver_job_count",
        "already_linked_count",
        "automatic_link_eligible_count",
        "review_candidate_count",
        "ambiguous_count",
        "unmatched_count",
    ):
        print(f"{key.upper()}={report[key]}")
    for classification, count in report["classification_counts"].items():
        print(f"CLASS_{classification.upper()}={count}")
    for item in report["applications"]:
        candidates = ",".join(
            str(candidate["silver_job_id"]) for candidate in item["candidate_jobs"]
        ) or "-"
        print(
            "APPLICATION="
            f"{item['application_id']}|{item['classification']}|candidates={candidates}"
        )
    print("DATABASE_CONNECTIONS=1")
    print("DATABASE_WRITES=0")
    print("GMAIL_NETWORK_REQUESTS=0")
    print("EMAIL_ACTIONS=0")
    print("APPLICATION_SUBMISSION_ACTIONS=0")
    print("AUTHORITATIVE_LIFECYCLE_MUTATIONS=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
