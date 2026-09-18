#!/usr/bin/env python3
"""Independent read-only terminal proof for the first F5 mailbox persistence batch.

The proof binds the committed apply report, normalized JSONL and exact public source
SHA, independently re-derives expected Gmail evidence identities, and verifies the
persisted PostgreSQL rows plus Product read-model authority separation. It performs
no Gmail access and no database writes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
import sys
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.product_v1_f5_mailbox_ingest import (  # noqa: E402
    MailboxIngestError,
    evidence_fingerprint,
    mailbox_application_key,
    parse_normalized_mailbox_observation,
    should_discover_application,
    should_persist_candidate,
    source_message_identity_key,
)
from scripts.run_f5_candidate_supersession_schema_qualification import (  # noqa: E402
    current as qualify_candidate_schema_current,
)
from scripts.run_product_v1_f5_mailbox_persistence_apply import (  # noqa: E402
    PersistenceApplyError,
    _checkout_sha,
    _sha256_file,
    _validate_sha256,
    _validate_source_sha,
)
from scripts.run_product_v1_f5_mailbox_persistence_preflight import (  # noqa: E402
    load_jsonl,
)
from src.search_intelligence.application_event_classifier import (  # noqa: E402
    classify_application_evidence,
)

TRACKING_VIEW = "gold_product_v1_application_tracking"
_OBSERVED_STAGE_BY_CLASS = {
    "application_acknowledgement": "applied",
    "recruiter_contact": "reply",
    "assessment_request": "reply",
    "interview_invitation": "interview",
    "offer_signal": "offer",
    "rejection": "closed",
    "withdrawal_confirmation": "closed",
}


class PostwriteProofError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExpectedCandidate:
    source_identity_key: str
    evidence_fingerprint: str
    candidate_class: str
    application_key: str
    source_thread_reference: str
    source_message_reference: str
    observed_at: datetime
    confidence: float


@dataclass(frozen=True)
class ExpectedApplication:
    application_key: str
    latest_candidate_class: str
    latest_observed_at: datetime
    observed_stage: str
    attention_candidate_count: int


def _parse_iso_date(value: str) -> date:
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


def _load_json_object(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise PostwriteProofError(f"json_missing:{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PostwriteProofError(f"json_object_required:{path}")
    return payload


def _validate_apply_report(
    report: Mapping[str, object],
    *,
    source_sha: str,
    input_sha256: str,
    plan_sha256: str,
    expected_application_inserts: int,
    expected_candidate_inserts: int,
) -> None:
    expected_scalars: dict[str, object] = {
        "schema": "jap.f5.mailbox_persistence_apply.v1",
        "proof_source_sha": proof_source_sha,
        "apply_source_sha": apply_source_sha,
        "input_sha256": input_sha256,
        "plan_sha256": plan_sha256,
        "application_inserts": expected_application_inserts,
        "candidate_inserts": expected_candidate_inserts,
        "candidate_noops": 0,
        "candidate_supersessions": 0,
        "gmail_network_requests": 0,
        "email_actions": 0,
        "application_submission_actions": 0,
        "authoritative_lifecycle_mutations": 0,
        "transaction": "committed",
    }
    for key, expected in expected_scalars.items():
        if report.get(key) != expected:
            raise PostwriteProofError(
                f"apply_report_mismatch:{key}:expected={expected}:actual={report.get(key)}"
            )


def _derive_expected(
    rows: list[dict[str, object]],
    *,
    since: date | None,
    until: date | None,
) -> tuple[dict[str, ExpectedCandidate], dict[str, ExpectedApplication], dict[str, int]]:
    expected_candidates: dict[str, ExpectedCandidate] = {}
    app_candidates: dict[str, list[ExpectedCandidate]] = defaultdict(list)
    class_counts: Counter[str] = Counter()

    for payload in rows:
        observed_date = _row_date(payload)
        if since is not None and (observed_date is None or observed_date < since):
            continue
        if until is not None and (observed_date is None or observed_date > until):
            continue

        try:
            observation = parse_normalized_mailbox_observation(payload)
        except MailboxIngestError as exc:
            raise PostwriteProofError(f"invalid_normalized_input:{exc}") from exc

        classification = classify_application_evidence(
            subject=observation.subject,
            text_excerpt=observation.text_excerpt,
            sender_domain=observation.sender_domain,
            mail_direction=observation.mail_direction,
            counterparty_domain=observation.counterparty_domain,
            deterministic_event_signals=observation.gmail_search_signals,
        )
        if not should_persist_candidate(classification):
            continue
        if not should_discover_application(classification):
            raise PostwriteProofError(
                f"first_batch_candidate_not_discoverable:{classification.candidate_class}"
            )
        if classification.confidence is None:
            raise PostwriteProofError("candidate_confidence_missing")

        source_key = source_message_identity_key(observation)
        if source_key in expected_candidates:
            raise PostwriteProofError(f"duplicate_expected_source_identity:{source_key}")

        application_key = mailbox_application_key(observation)
        expected = ExpectedCandidate(
            source_identity_key=source_key,
            evidence_fingerprint=evidence_fingerprint(observation, classification),
            candidate_class=classification.candidate_class,
            application_key=application_key,
            source_thread_reference=observation.thread_reference,
            source_message_reference=observation.message_reference,
            observed_at=observation.observed_at,
            confidence=float(classification.confidence),
        )
        expected_candidates[source_key] = expected
        app_candidates[application_key].append(expected)
        class_counts[classification.candidate_class] += 1

    expected_applications: dict[str, ExpectedApplication] = {}
    for application_key, candidates in app_candidates.items():
        latest = max(candidates, key=lambda item: item.observed_at)
        stage = _OBSERVED_STAGE_BY_CLASS.get(latest.candidate_class)
        if stage is None:
            raise PostwriteProofError(
                f"candidate_class_not_product_observable:{latest.candidate_class}"
            )
        expected_applications[application_key] = ExpectedApplication(
            application_key=application_key,
            latest_candidate_class=latest.candidate_class,
            latest_observed_at=latest.observed_at,
            observed_stage=stage,
            attention_candidate_count=len(candidates),
        )

    return (
        expected_candidates,
        expected_applications,
        dict(sorted(class_counts.items())),
    )


def _fetch_candidates(conn: object, source_keys: list[str]) -> list[Mapping[str, object]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                candidate.id,
                candidate.source_identity_key,
                candidate.evidence_fingerprint,
                candidate.candidate_class,
                candidate.source_thread_reference,
                candidate.source_message_reference,
                candidate.match_status,
                candidate.review_status,
                candidate.confidence,
                candidate.observed_at,
                candidate.is_active,
                candidate.supersedes_candidate_id,
                application.application_key
            FROM application_event_candidates candidate
            LEFT JOIN applications application
              ON application.id = candidate.matched_application_id
            WHERE candidate.source_kind = 'gmail'
              AND candidate.source_identity_key = ANY(%s)
            ORDER BY candidate.source_identity_key, candidate.id
            """,
            (source_keys,),
        )
        return list(cur.fetchall())


def _fetch_applications(conn: object, application_keys: list[str]) -> list[Mapping[str, object]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                application.id,
                application.application_key,
                application.discovery_kind,
                application.silver_job_id,
                application.draft_request_id,
                application.prepared_at,
                application.prepared_by
            FROM applications application
            WHERE application.application_key = ANY(%s)
            ORDER BY application.application_key
            """,
            (application_keys,),
        )
        return list(cur.fetchall())


def _fetch_tracking(conn: object, application_keys: list[str]) -> list[Mapping[str, object]]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                application_key,
                submission_id,
                authoritative_stage,
                authoritative_event_count,
                attention_candidate_count,
                observed_stage,
                observed_event_class,
                observed_at,
                effective_stage,
                effective_stage_basis,
                discovery_kind
            FROM {TRACKING_VIEW}
            WHERE application_key = ANY(%s)
            ORDER BY application_key
            """,
            (application_keys,),
        )
        return list(cur.fetchall())


def _scalar_count(conn: object, query: str, params: tuple[object, ...] = ()) -> int:
    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
    return int(row["count"])


def _verify_candidates(
    rows: list[Mapping[str, object]],
    expected: Mapping[str, ExpectedCandidate],
) -> None:
    if len(rows) != len(expected):
        raise PostwriteProofError(
            f"candidate_row_count_mismatch:expected={len(expected)}:actual={len(rows)}"
        )
    seen: set[str] = set()
    for row in rows:
        source_key = str(row["source_identity_key"])
        if source_key in seen:
            raise PostwriteProofError(f"multiple_rows_for_source_identity:{source_key}")
        seen.add(source_key)
        item = expected.get(source_key)
        if item is None:
            raise PostwriteProofError(f"unexpected_source_identity:{source_key}")

        exact_pairs = {
            "evidence_fingerprint": item.evidence_fingerprint,
            "candidate_class": item.candidate_class,
            "source_thread_reference": item.source_thread_reference,
            "source_message_reference": item.source_message_reference,
            "match_status": "exact",
            "review_status": "unreviewed",
            "application_key": item.application_key,
        }
        for key, expected_value in exact_pairs.items():
            if row[key] != expected_value:
                raise PostwriteProofError(
                    f"candidate_mismatch:{source_key}:{key}:"
                    f"expected={expected_value}:actual={row[key]}"
                )
        if row["is_active"] is not True:
            raise PostwriteProofError(f"candidate_not_active:{source_key}")
        if row["supersedes_candidate_id"] is not None:
            raise PostwriteProofError(f"unexpected_supersession:{source_key}")
        if row["observed_at"] != item.observed_at:
            raise PostwriteProofError(f"candidate_observed_at_mismatch:{source_key}")
        if abs(float(row["confidence"]) - item.confidence) > 1e-9:
            raise PostwriteProofError(f"candidate_confidence_mismatch:{source_key}")


def _verify_applications(
    rows: list[Mapping[str, object]],
    expected: Mapping[str, ExpectedApplication],
) -> None:
    if len(rows) != len(expected):
        raise PostwriteProofError(
            f"application_row_count_mismatch:expected={len(expected)}:actual={len(rows)}"
        )
    actual_keys = {str(row["application_key"]) for row in rows}
    if actual_keys != set(expected):
        raise PostwriteProofError("application_key_set_mismatch")
    for row in rows:
        key = str(row["application_key"])
        if row["discovery_kind"] != "mailbox_observed":
            raise PostwriteProofError(f"application_discovery_kind_mismatch:{key}")
        for nullable in (
            "silver_job_id",
            "draft_request_id",
            "prepared_at",
            "prepared_by",
        ):
            if row[nullable] is not None:
                raise PostwriteProofError(
                    f"mailbox_application_unexpected_{nullable}:{key}"
                )


def _verify_tracking(
    rows: list[Mapping[str, object]],
    expected: Mapping[str, ExpectedApplication],
) -> None:
    if len(rows) != len(expected):
        raise PostwriteProofError(
            f"tracking_row_count_mismatch:expected={len(expected)}:actual={len(rows)}"
        )
    for row in rows:
        key = str(row["application_key"])
        item = expected.get(key)
        if item is None:
            raise PostwriteProofError(f"unexpected_tracking_application:{key}")
        if row["submission_id"] is not None:
            raise PostwriteProofError(f"tracking_submission_present:{key}")
        if row["authoritative_stage"] != "prepared":
            raise PostwriteProofError(f"authoritative_stage_changed:{key}")
        if int(row["authoritative_event_count"]) != 0:
            raise PostwriteProofError(f"authoritative_events_present:{key}")
        if int(row["attention_candidate_count"]) != item.attention_candidate_count:
            raise PostwriteProofError(f"attention_candidate_count_mismatch:{key}")
        if row["observed_stage"] != item.observed_stage:
            raise PostwriteProofError(f"observed_stage_mismatch:{key}")
        if row["observed_event_class"] != item.latest_candidate_class:
            raise PostwriteProofError(f"observed_class_mismatch:{key}")
        if row["observed_at"] != item.latest_observed_at:
            raise PostwriteProofError(f"observed_at_mismatch:{key}")
        if row["effective_stage"] != item.observed_stage:
            raise PostwriteProofError(f"effective_stage_mismatch:{key}")
        if row["effective_stage_basis"] != "mailbox_observed":
            raise PostwriteProofError(f"effective_stage_basis_mismatch:{key}")
        if row["discovery_kind"] != "mailbox_observed":
            raise PostwriteProofError(f"tracking_discovery_kind_mismatch:{key}")


def prove_postwrite(
    *,
    input_path: Path,
    expected_input_sha256: str,
    apply_report_path: Path,
    expected_apply_report_sha256: str,
    expected_prewrite_plan_sha256: str,
    proof_source_sha: str,
    apply_source_sha: str,
    since: date | None,
    until: date | None,
    expected_application_inserts: int,
    expected_candidate_inserts: int,
) -> dict[str, object]:
    expected_input_sha256 = _validate_sha256(
        expected_input_sha256, name="expected_input_sha256"
    )
    expected_apply_report_sha256 = _validate_sha256(
        expected_apply_report_sha256, name="expected_apply_report_sha256"
    )
    expected_prewrite_plan_sha256 = _validate_sha256(
        expected_prewrite_plan_sha256, name="expected_prewrite_plan_sha256"
    )
    proof_source_sha = _validate_source_sha(proof_source_sha)
    apply_source_sha = _validate_source_sha(apply_source_sha)

    actual_source_sha = _checkout_sha()
    if actual_source_sha != proof_source_sha:
        raise PostwriteProofError(
            "checkout_source_mismatch:"
            f"expected={proof_source_sha}:actual={actual_source_sha}"
        )

    input_sha256 = _sha256_file(input_path)
    if input_sha256 != expected_input_sha256:
        raise PostwriteProofError(
            f"input_sha256_mismatch:expected={expected_input_sha256}:actual={input_sha256}"
        )

    apply_report_sha256 = _sha256_file(apply_report_path)
    if apply_report_sha256 != expected_apply_report_sha256:
        raise PostwriteProofError(
            "apply_report_sha256_mismatch:"
            f"expected={expected_apply_report_sha256}:actual={apply_report_sha256}"
        )

    apply_report = _load_json_object(apply_report_path)
    _validate_apply_report(
        apply_report,
        source_sha=apply_source_sha,
        input_sha256=input_sha256,
        plan_sha256=expected_prewrite_plan_sha256,
        expected_application_inserts=expected_application_inserts,
        expected_candidate_inserts=expected_candidate_inserts,
    )

    expected_candidates, expected_applications, class_counts = _derive_expected(
        load_jsonl(input_path),
        since=since,
        until=until,
    )
    if len(expected_candidates) != expected_candidate_inserts:
        raise PostwriteProofError(
            "derived_candidate_count_mismatch:"
            f"expected={expected_candidate_inserts}:actual={len(expected_candidates)}"
        )
    if len(expected_applications) != expected_application_inserts:
        raise PostwriteProofError(
            "derived_application_count_mismatch:"
            f"expected={expected_application_inserts}:actual={len(expected_applications)}"
        )

    # Separate read-only schema proof before inspecting persisted product truth.
    qualify_candidate_schema_current(source_sha=proof_source_sha)

    import psycopg
    from psycopg.rows import dict_row

    from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig

    source_keys = sorted(expected_candidates)
    application_keys = sorted(expected_applications)
    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(),
        row_factory=dict_row,
    ) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            candidates = _fetch_candidates(conn, source_keys)
            applications = _fetch_applications(conn, application_keys)
            tracking = _fetch_tracking(conn, application_keys)

            submission_count = _scalar_count(
                conn,
                """
                SELECT count(*)::integer AS count
                FROM application_submissions submission
                JOIN applications application
                  ON application.id = submission.application_id
                WHERE application.application_key = ANY(%s)
                """,
                (application_keys,),
            )
            lifecycle_count = _scalar_count(
                conn,
                """
                SELECT count(*)::integer AS count
                FROM application_lifecycle_events event
                JOIN application_submissions submission
                  ON submission.id = event.submission_id
                JOIN applications application
                  ON application.id = submission.application_id
                WHERE application.application_key = ANY(%s)
                """,
                (application_keys,),
            )
            global_submission_count = _scalar_count(
                conn,
                "SELECT count(*)::integer AS count FROM application_submissions",
            )
            global_lifecycle_count = _scalar_count(
                conn,
                "SELECT count(*)::integer AS count FROM application_lifecycle_events",
            )
            active_gmail_candidate_count = _scalar_count(
                conn,
                """
                SELECT count(*)::integer AS count
                FROM application_event_candidates
                WHERE source_kind = 'gmail' AND is_active
                """,
            )

    _verify_candidates(candidates, expected_candidates)
    _verify_applications(applications, expected_applications)
    _verify_tracking(tracking, expected_applications)

    if submission_count != 0 or lifecycle_count != 0:
        raise PostwriteProofError(
            f"scoped_authority_rows_present:submissions={submission_count}:"
            f"lifecycle={lifecycle_count}"
        )
    if global_submission_count != 0 or global_lifecycle_count != 0:
        raise PostwriteProofError(
            f"global_authority_rows_present:submissions={global_submission_count}:"
            f"lifecycle={global_lifecycle_count}"
        )
    if active_gmail_candidate_count != expected_candidate_inserts:
        raise PostwriteProofError(
            "active_gmail_candidate_count_mismatch:"
            f"expected={expected_candidate_inserts}:actual={active_gmail_candidate_count}"
        )

    return {
        "schema": "jap.f5.mailbox_persistence_postwrite_proof.v1",
        "source_sha": source_sha,
        "input_sha256": input_sha256,
        "apply_report_sha256": apply_report_sha256,
        "prewrite_plan_sha256": expected_prewrite_plan_sha256,
        "expected_application_rows": len(expected_applications),
        "expected_candidate_rows": len(expected_candidates),
        "verified_application_rows": len(applications),
        "verified_candidate_rows": len(candidates),
        "verified_tracking_rows": len(tracking),
        "active_gmail_candidate_count": active_gmail_candidate_count,
        "scoped_submission_rows": submission_count,
        "scoped_authoritative_lifecycle_rows": lifecycle_count,
        "global_submission_rows": global_submission_count,
        "global_authoritative_lifecycle_rows": global_lifecycle_count,
        "class_counts": class_counts,
        "database_connections": 2,
        "database_writes": 0,
        "gmail_network_requests": 0,
        "email_actions": 0,
        "application_submission_actions": 0,
        "authoritative_lifecycle_mutations": 0,
        "proof": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Independent read-only post-write proof for the first F5 mailbox batch"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--apply-report", type=Path, required=True)
    parser.add_argument("--expected-apply-report-sha256", required=True)
    parser.add_argument("--expected-prewrite-plan-sha256", required=True)
    parser.add_argument("--proof-source-sha", required=True)
    parser.add_argument("--apply-source-sha", required=True)
    parser.add_argument("--since", type=_parse_iso_date)
    parser.add_argument("--until", type=_parse_iso_date)
    parser.add_argument("--expected-application-inserts", type=int, required=True)
    parser.add_argument("--expected-candidate-inserts", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.since is not None and args.until is not None and args.until < args.since:
        print("F5_MAILBOX_PERSISTENCE_POSTWRITE_ERROR=until_before_since")
        return 2

    try:
        report = prove_postwrite(
            input_path=args.input.expanduser(),
            expected_input_sha256=args.expected_input_sha256,
            apply_report_path=args.apply_report.expanduser(),
            expected_apply_report_sha256=args.expected_apply_report_sha256,
            expected_prewrite_plan_sha256=args.expected_prewrite_plan_sha256,
            proof_source_sha=args.proof_source_sha,
            apply_source_sha=args.apply_source_sha,
            since=args.since,
            until=args.until,
            expected_application_inserts=args.expected_application_inserts,
            expected_candidate_inserts=args.expected_candidate_inserts,
        )
    except (
        MailboxIngestError,
        PersistenceApplyError,
        PostwriteProofError,
        RuntimeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"F5_MAILBOX_PERSISTENCE_POSTWRITE_ERROR={exc}")
        return 2

    output = args.output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("F5_MAILBOX_PERSISTENCE_POSTWRITE_PROOF=PASS")
    for key in (
        "proof_source_sha",
        "apply_source_sha",
        "input_sha256",
        "apply_report_sha256",
        "prewrite_plan_sha256",
        "expected_application_rows",
        "expected_candidate_rows",
        "verified_application_rows",
        "verified_candidate_rows",
        "verified_tracking_rows",
        "active_gmail_candidate_count",
        "scoped_submission_rows",
        "scoped_authoritative_lifecycle_rows",
        "global_submission_rows",
        "global_authoritative_lifecycle_rows",
    ):
        print(f"{key.upper()}={report[key]}")
    for candidate_class, count in report["class_counts"].items():
        print(f"CLASS_{candidate_class.upper()}={count}")
    print("DATABASE_CONNECTIONS=2")
    print("DATABASE_WRITES=0")
    print("GMAIL_NETWORK_REQUESTS=0")
    print("EMAIL_ACTIONS=0")
    print("APPLICATION_SUBMISSION_ACTIONS=0")
    print("AUTHORITATIVE_LIFECYCLE_MUTATIONS=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
