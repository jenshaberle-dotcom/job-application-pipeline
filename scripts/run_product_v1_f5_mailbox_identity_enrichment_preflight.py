#!/usr/bin/env python3
"""Read-only metadata completeness/enrichment preflight for F5 mailbox applications."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime
import json
from pathlib import Path
import sys
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.product_v1_f5_mailbox_ingest import (  # noqa: E402
    mailbox_application_key,
    parse_normalized_mailbox_observation,
    should_discover_application,
)
from scripts.run_product_v1_f5_mailbox_batch_preflight import load_jsonl  # noqa: E402
from scripts.run_product_v1_f5_mailbox_persistence_apply import (  # noqa: E402
    _checkout_sha,
    _sha256_file,
    _validate_sha256,
    _validate_source_sha,
)
from src.search_intelligence.application_event_classifier import classify_application_evidence  # noqa: E402


class IdentityEnrichmentPreflightError(RuntimeError):
    pass


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value}") from exc


def _row_date(payload: Mapping[str, object]) -> date | None:
    raw = str(payload.get("observed_at") or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _clean(value: object) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def _single(values: set[str]) -> tuple[str | None, bool]:
    cleaned = {item for item in values if item}
    if not cleaned:
        return None, False
    if len(cleaned) == 1:
        return next(iter(cleaned)), False
    return None, True


def build_input_identity(rows: list[dict[str, object]], *, since: date, until: date) -> dict[str, dict[str, object]]:
    grouped: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"employer": set(), "title": set(), "url": set(), "domain": set()}
    )
    for payload in rows:
        observed = _row_date(payload)
        if observed is None or observed < since or observed > until:
            continue
        observation = parse_normalized_mailbox_observation(payload)
        classification = classify_application_evidence(
            subject=observation.subject,
            text_excerpt=observation.text_excerpt,
            sender_domain=observation.sender_domain,
            mail_direction=observation.mail_direction,
            counterparty_domain=observation.counterparty_domain,
            deterministic_event_signals=observation.gmail_search_signals,
        )
        if not should_discover_application(classification):
            continue
        key = mailbox_application_key(observation)
        for bucket, value in (
            ("employer", observation.employer_name),
            ("title", observation.job_title),
            ("url", observation.source_url),
            ("domain", observation.counterparty_domain or observation.sender_domain),
        ):
            cleaned = _clean(value)
            if cleaned:
                grouped[key][bucket].add(cleaned)

    result: dict[str, dict[str, object]] = {}
    for key, values in grouped.items():
        employer, employer_conflict = _single(values["employer"])
        title, title_conflict = _single(values["title"])
        source_url, url_conflict = _single(values["url"])
        domain, domain_conflict = _single(values["domain"])
        result[key] = {
            "employer_name": employer,
            "job_title": title,
            "source_url": source_url,
            "domain": domain,
            "employer_conflict": employer_conflict,
            "title_conflict": title_conflict,
            "source_url_conflict": url_conflict,
            "domain_conflict": domain_conflict,
        }
    return result


def run_preflight(
    *,
    input_path: Path,
    expected_input_sha256: str,
    source_sha: str,
    since: date,
    until: date,
) -> dict[str, object]:
    expected_input_sha256 = _validate_sha256(expected_input_sha256, name="expected_input_sha256")
    source_sha = _validate_source_sha(source_sha)
    actual_source = _checkout_sha()
    if actual_source != source_sha:
        raise IdentityEnrichmentPreflightError(
            f"checkout_source_mismatch:expected={source_sha}:actual={actual_source}"
        )
    actual_input_sha = _sha256_file(input_path)
    if actual_input_sha != expected_input_sha256:
        raise IdentityEnrichmentPreflightError(
            f"input_sha256_mismatch:expected={expected_input_sha256}:actual={actual_input_sha}"
        )

    expected = build_input_identity(load_jsonl(input_path), since=since, until=until)

    import psycopg
    from psycopg.rows import dict_row
    from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig

    keys = sorted(expected)
    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT application_key, job_identity_snapshot
                    FROM applications
                    WHERE discovery_kind = 'mailbox_observed'
                      AND application_key = ANY(%s)
                    ORDER BY application_key
                    """,
                    (keys,),
                )
                db_rows = list(cur.fetchall())

    by_key = {str(row["application_key"]): row for row in db_rows}
    missing_db = [key for key in keys if key not in by_key]
    if missing_db:
        raise IdentityEnrichmentPreflightError(
            "expected_application_missing:" + ",".join(missing_db)
        )

    metrics = {
        "application_count": len(keys),
        "db_application_count": len(db_rows),
        "title_present_db": 0,
        "employer_present_db": 0,
        "source_url_present_db": 0,
        "title_enrichable_from_input": 0,
        "employer_enrichable_from_input": 0,
        "source_url_enrichable_from_input": 0,
        "title_still_unknown_after_input": 0,
        "employer_still_unknown_after_input": 0,
        "source_url_still_unknown_after_input": 0,
        "identity_conflicts": 0,
    }

    details: list[dict[str, object]] = []
    for key in keys:
        snapshot = by_key[key]["job_identity_snapshot"]
        snapshot = snapshot if isinstance(snapshot, Mapping) else {}
        input_identity = expected[key]

        db_title = _clean(snapshot.get("job_title"))
        db_employer = _clean(snapshot.get("employer_name"))
        db_url = _clean(snapshot.get("application_url"))
        input_title = _clean(input_identity.get("job_title"))
        input_employer = _clean(input_identity.get("employer_name"))
        input_url = _clean(input_identity.get("source_url"))

        metrics["title_present_db"] += int(bool(db_title))
        metrics["employer_present_db"] += int(bool(db_employer))
        metrics["source_url_present_db"] += int(bool(db_url))
        metrics["title_enrichable_from_input"] += int(not db_title and bool(input_title))
        metrics["employer_enrichable_from_input"] += int(not db_employer and bool(input_employer))
        metrics["source_url_enrichable_from_input"] += int(not db_url and bool(input_url))
        metrics["title_still_unknown_after_input"] += int(not db_title and not input_title)
        metrics["employer_still_unknown_after_input"] += int(not db_employer and not input_employer)
        metrics["source_url_still_unknown_after_input"] += int(not db_url and not input_url)
        conflict = any(
            bool(input_identity[name])
            for name in (
                "employer_conflict",
                "title_conflict",
                "source_url_conflict",
                "domain_conflict",
            )
        )
        metrics["identity_conflicts"] += int(conflict)

        details.append(
            {
                "application_key": key,
                "db_employer_name": db_employer,
                "db_job_title": db_title,
                "db_source_url_present": bool(db_url),
                "input_employer_name": input_employer,
                "input_job_title": input_title,
                "input_source_url_present": bool(input_url),
                "input_domain": input_identity.get("domain"),
                "conflict": conflict,
            }
        )

    return {
        "schema": "jap.f5.mailbox_identity_enrichment_preflight.v1",
        "source_sha": source_sha,
        "input_sha256": actual_input_sha,
        **metrics,
        "details": details,
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
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--since", type=_parse_date, required=True)
    parser.add_argument("--until", type=_parse_date, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.until < args.since:
        print("F5_MAILBOX_IDENTITY_ENRICHMENT_PREFLIGHT_ERROR=until_before_since")
        return 2
    try:
        report = run_preflight(
            input_path=args.input.expanduser(),
            expected_input_sha256=args.expected_input_sha256,
            source_sha=args.source_sha,
            since=args.since,
            until=args.until,
        )
    except Exception as exc:
        print(f"F5_MAILBOX_IDENTITY_ENRICHMENT_PREFLIGHT_ERROR={exc}")
        return 2

    output = args.output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print("F5_MAILBOX_IDENTITY_ENRICHMENT_PREFLIGHT=PASS")
    for key in (
        "source_sha",
        "input_sha256",
        "application_count",
        "db_application_count",
        "title_present_db",
        "employer_present_db",
        "source_url_present_db",
        "title_enrichable_from_input",
        "employer_enrichable_from_input",
        "source_url_enrichable_from_input",
        "title_still_unknown_after_input",
        "employer_still_unknown_after_input",
        "source_url_still_unknown_after_input",
        "identity_conflicts",
    ):
        print(f"{key.upper()}={report[key]}")
    print("DATABASE_CONNECTIONS=1")
    print("DATABASE_WRITES=0")
    print("GMAIL_NETWORK_REQUESTS=0")
    print("EMAIL_ACTIONS=0")
    print("APPLICATION_SUBMISSION_ACTIONS=0")
    print("AUTHORITATIVE_LIFECYCLE_MUTATIONS=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
