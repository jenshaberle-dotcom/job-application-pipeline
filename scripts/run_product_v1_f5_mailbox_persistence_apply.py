#!/usr/bin/env python3
"""Explicit atomic apply path for a bounded normalized F5 mailbox batch.

This public script never accesses Gmail. It consumes an already-normalized private
JSONL file, binds execution to exact input/plan/source identities, snapshots live
PostgreSQL state, and applies only communication-evidence persistence in one outer
transaction. It cannot create submission authority or authoritative lifecycle
events.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.product_v1_f5_mailbox_ingest import (  # noqa: E402
    MailboxIngestError,
    ingest_normalized_mailbox_observation,
    parse_normalized_mailbox_observation,
    should_persist_candidate,
    source_message_identity_key,
)
from scripts.run_f5_candidate_supersession_schema_qualification import (  # noqa: E402
    current as qualify_candidate_schema_current,
)
from scripts.run_product_v1_f5_mailbox_persistence_preflight import (  # noqa: E402
    ActiveCandidate,
    PersistencePlan,
    load_jsonl,
    plan_rows,
)
from src.search_intelligence.application_event_classifier import (  # noqa: E402
    classify_application_evidence,
)
from src.search_intelligence.application_identity_matching import (  # noqa: E402
    ExistingApplicationIdentity,
)

APPROVAL_TOKEN = "F5-GMAIL-BATCH-PERSISTENCE-V1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class PersistenceApplyError(RuntimeError):
    pass


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _plan_json(plan: PersistencePlan) -> str:
    return json.dumps(asdict(plan), indent=2, sort_keys=True) + "\n"


def _plan_sha256(plan: PersistencePlan) -> str:
    return hashlib.sha256(_plan_json(plan).encode("utf-8")).hexdigest()


def _checkout_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PersistenceApplyError("checkout_sha_unavailable") from exc


def _validate_sha256(value: str, *, name: str) -> str:
    normalized = value.casefold().strip()
    if not _SHA256_RE.fullmatch(normalized):
        raise PersistenceApplyError(f"invalid_{name}")
    return normalized


def _validate_source_sha(value: str) -> str:
    normalized = value.casefold().strip()
    if not _GIT_COMMIT_SHA_RE.fullmatch(normalized):
        raise PersistenceApplyError("invalid_source_sha")
    return normalized


def _load_live_state(conn: object) -> tuple[set[str], dict[str, ActiveCandidate]]:
    with conn.cursor() as cur:
        cur.execute("SELECT application_key FROM applications")
        application_keys = {str(row["application_key"]) for row in cur.fetchall()}

        cur.execute(
            """
            SELECT
                candidate.source_identity_key,
                candidate.evidence_fingerprint,
                candidate.candidate_class,
                application.application_key
            FROM application_event_candidates candidate
            LEFT JOIN applications application
              ON application.id = candidate.matched_application_id
            WHERE candidate.source_kind = 'gmail'
              AND candidate.is_active
            ORDER BY candidate.source_identity_key
            """
        )
        active: dict[str, ActiveCandidate] = {}
        for row in cur.fetchall():
            source_key = str(row["source_identity_key"])
            if source_key in active:
                raise PersistenceApplyError("duplicate_active_source_identity")
            active[source_key] = ActiveCandidate(
                source_identity_key=source_key,
                evidence_fingerprint=str(row["evidence_fingerprint"]),
                candidate_class=str(row["candidate_class"]),
                application_key=(
                    str(row["application_key"])
                    if row["application_key"] is not None
                    else None
                ),
            )
    return application_keys, active


def _load_existing_application_identities(
    conn: object,
) -> list[ExistingApplicationIdentity]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                application.application_key,
                coalesce(
                    silver.company_name,
                    application.job_identity_snapshot->>'company_name',
                    application.job_identity_snapshot->>'employer_name',
                    application.job_identity_snapshot->>'company'
                ) AS employer_name,
                coalesce(
                    silver.title,
                    application.job_identity_snapshot->>'title',
                    application.job_identity_snapshot->>'job_title',
                    application.job_identity_snapshot->>'position'
                ) AS job_title,
                coalesce(
                    silver.source_url,
                    application.job_identity_snapshot->>'source_url',
                    application.job_identity_snapshot->>'job_url',
                    application.job_identity_snapshot->>'application_url'
                ) AS source_url,
                coalesce(
                    application.job_identity_snapshot->>'counterparty_domain',
                    application.provenance->>'counterparty_domain'
                ) AS counterparty_domain,
                application.provenance->>'thread_reference' AS thread_reference
            FROM applications application
            LEFT JOIN silver_jobs silver
              ON silver.id = application.silver_job_id
            ORDER BY application.id
            """
        )
        return [
            ExistingApplicationIdentity(
                application_key=str(row["application_key"]),
                employer_name=(
                    str(row["employer_name"]) if row["employer_name"] is not None else None
                ),
                job_title=(
                    str(row["job_title"]) if row["job_title"] is not None else None
                ),
                source_url=(
                    str(row["source_url"]) if row["source_url"] is not None else None
                ),
                counterparty_domain=(
                    str(row["counterparty_domain"])
                    if row["counterparty_domain"] is not None
                    else None
                ),
                thread_reference=(
                    str(row["thread_reference"])
                    if row["thread_reference"] is not None
                    else None
                ),
            )
            for row in cur.fetchall()
        ]


def _authority_counts(conn: object) -> dict[str, int]:
    with conn.cursor() as cur:
        result: dict[str, int] = {}
        for relation in (
            "applications",
            "application_event_candidates",
            "application_submissions",
            "application_lifecycle_events",
        ):
            cur.execute(f'SELECT count(*)::integer AS count FROM "{relation}"')
            result[relation] = int(cur.fetchone()["count"])
    return result


def _select_apply_rows(
    rows: list[dict[str, object]],
    *,
    active_candidates: Mapping[str, ActiveCandidate],
    since: date | None,
    until: date | None,
) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for payload in rows:
        observed_date = _row_date(payload)
        if since is not None and (observed_date is None or observed_date < since):
            continue
        if until is not None and (observed_date is None or observed_date > until):
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
        source_key = source_message_identity_key(observation)
        if should_persist_candidate(classification) or source_key in active_candidates:
            selected.append(payload)
    return selected


def _assert_plan_is_safe(plan: PersistencePlan) -> None:
    if plan.invalid_rows != 0:
        raise PersistenceApplyError(f"invalid_rows:{plan.invalid_rows}")
    if plan.persistence_candidate_rows != plan.unique_source_messages:
        raise PersistenceApplyError("persistence_rows_not_unique_source_messages")


def _summarize_results(results: list[dict[str, object]]) -> dict[str, object]:
    class_counts: Counter[str] = Counter()
    for result in results:
        class_counts[str(result["candidate_class"])] += 1
        for key in (
            "authoritative_state_mutation",
            "application_submission_action",
            "email_action",
        ):
            if bool(result.get(key)):
                raise PersistenceApplyError(f"forbidden_boundary:{key}")

    supersessions = sum(
        1 for result in results if result.get("superseded_candidate_id") is not None
    )
    return {
        "processed_rows": len(results),
        "application_inserts": sum(
            1 for result in results if bool(result.get("application_created"))
        ),
        "candidate_inserts": sum(
            1
            for result in results
            if bool(result.get("candidate_recorded"))
            and result.get("superseded_candidate_id") is None
        ),
        "candidate_noops": sum(
            1 for result in results if bool(result.get("candidate_noop"))
        ),
        "candidate_supersessions": supersessions,
        "candidate_skipped": sum(
            1 for result in results if bool(result.get("candidate_skipped"))
        ),
        "class_counts": dict(sorted(class_counts.items())),
    }


def apply_batch(
    *,
    input_path: Path,
    expected_input_sha256: str,
    expected_plan_sha256: str,
    source_sha: str,
    since: date | None,
    until: date | None,
) -> dict[str, object]:
    expected_input_sha256 = _validate_sha256(
        expected_input_sha256, name="expected_input_sha256"
    )
    expected_plan_sha256 = _validate_sha256(
        expected_plan_sha256, name="expected_plan_sha256"
    )
    source_sha = _validate_source_sha(source_sha)

    actual_source_sha = _checkout_sha()
    if actual_source_sha != source_sha:
        raise PersistenceApplyError(
            f"checkout_source_mismatch:expected={source_sha}:actual={actual_source_sha}"
        )

    actual_input_sha256 = _sha256_file(input_path)
    if actual_input_sha256 != expected_input_sha256:
        raise PersistenceApplyError(
            "input_sha256_mismatch:"
            f"expected={expected_input_sha256}:actual={actual_input_sha256}"
        )

    rows = load_jsonl(input_path)

    # Independent schema proof runs read-only before the mutation transaction.
    qualify_candidate_schema_current(source_sha=source_sha)

    import psycopg
    from psycopg.rows import dict_row

    from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig

    dsn = DatabaseConfig.from_environment().dsn()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            before = _authority_counts(conn)
            application_keys, active = _load_live_state(conn)
            application_identities = _load_existing_application_identities(conn)
            plan = plan_rows(
                rows,
                existing_application_keys=application_keys,
                existing_application_identities=application_identities,
                active_candidates=active,
                since=since,
                until=until,
            )
            _assert_plan_is_safe(plan)

            actual_plan_sha256 = _plan_sha256(plan)
            if actual_plan_sha256 != expected_plan_sha256:
                raise PersistenceApplyError(
                    "plan_sha256_mismatch:"
                    f"expected={expected_plan_sha256}:actual={actual_plan_sha256}"
                )

            selected = _select_apply_rows(
                rows,
                active_candidates=active,
                since=since,
                until=until,
            )
            if len(selected) != plan.persistence_candidate_rows:
                raise PersistenceApplyError(
                    "selected_row_count_mismatch:"
                    f"plan={plan.persistence_candidate_rows}:selected={len(selected)}"
                )

            results: list[dict[str, object]] = []
            for payload in selected:
                observation = parse_normalized_mailbox_observation(payload)
                results.append(
                    ingest_normalized_mailbox_observation(
                        observation,
                        connection=conn,
                    )
                )

            actual = _summarize_results(results)
            expected_effects = {
                "processed_rows": plan.persistence_candidate_rows,
                "application_inserts": plan.application_inserts,
                "candidate_inserts": plan.candidate_inserts,
                "candidate_noops": plan.candidate_noops,
                "candidate_supersessions": plan.candidate_supersessions,
                "candidate_skipped": 0,
                "class_counts": plan.class_counts,
            }
            if actual != expected_effects:
                raise PersistenceApplyError(
                    "actual_effects_do_not_match_plan:"
                    + json.dumps(
                        {"expected": expected_effects, "actual": actual},
                        sort_keys=True,
                    )
                )

            after = _authority_counts(conn)
            if (
                after["application_submissions"] != before["application_submissions"]
                or after["application_lifecycle_events"]
                != before["application_lifecycle_events"]
            ):
                raise PersistenceApplyError("authoritative_state_changed")

            if (
                after["applications"] - before["applications"]
                != plan.application_inserts
            ):
                raise PersistenceApplyError("application_delta_mismatch")
            expected_candidate_delta = (
                plan.candidate_inserts + plan.candidate_supersessions
            )
            if (
                after["application_event_candidates"]
                - before["application_event_candidates"]
                != expected_candidate_delta
            ):
                raise PersistenceApplyError("candidate_delta_mismatch")

    return {
        "schema": "jap.f5.mailbox_persistence_apply.v1",
        "source_sha": source_sha,
        "input_sha256": actual_input_sha256,
        "plan_sha256": actual_plan_sha256,
        "input_rows": plan.input_rows,
        "window_rows": plan.window_rows,
        "persistence_candidate_rows": plan.persistence_candidate_rows,
        "skipped_other_rows": plan.skipped_other_rows,
        "application_inserts": plan.application_inserts,
        "candidate_inserts": plan.candidate_inserts,
        "candidate_noops": plan.candidate_noops,
        "candidate_supersessions": plan.candidate_supersessions,
        "class_counts": plan.class_counts,
        "gmail_network_requests": 0,
        "email_actions": 0,
        "application_submission_actions": 0,
        "authoritative_lifecycle_mutations": 0,
        "transaction": "committed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explicit atomic F5 normalized-mailbox persistence apply"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--expected-plan-sha256", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--since", type=_parse_iso_date)
    parser.add_argument("--until", type=_parse_iso_date)
    parser.add_argument("--approval-token", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not args.apply:
        print("F5_MAILBOX_PERSISTENCE_APPLY_ERROR=explicit_apply_flag_required")
        return 3
    if args.approval_token != APPROVAL_TOKEN:
        print("F5_MAILBOX_PERSISTENCE_APPLY_ERROR=approval_token_invalid")
        return 3
    if args.since is not None and args.until is not None and args.until < args.since:
        print("F5_MAILBOX_PERSISTENCE_APPLY_ERROR=until_before_since")
        return 2

    try:
        report = apply_batch(
            input_path=args.input.expanduser(),
            expected_input_sha256=args.expected_input_sha256,
            expected_plan_sha256=args.expected_plan_sha256,
            source_sha=args.source_sha,
            since=args.since,
            until=args.until,
        )
    except (
        MailboxIngestError,
        PersistenceApplyError,
        RuntimeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"F5_MAILBOX_PERSISTENCE_APPLY_ERROR={exc}")
        return 2

    output = args.output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("F5_MAILBOX_PERSISTENCE_APPLY=PASS")
    for key in (
        "source_sha",
        "input_sha256",
        "plan_sha256",
        "input_rows",
        "window_rows",
        "persistence_candidate_rows",
        "skipped_other_rows",
        "application_inserts",
        "candidate_inserts",
        "candidate_noops",
        "candidate_supersessions",
    ):
        print(f"{key.upper()}={report[key]}")
    for candidate_class, count in report["class_counts"].items():
        print(f"CLASS_{candidate_class.upper()}={count}")
    print("GMAIL_NETWORK_REQUESTS=0")
    print("EMAIL_ACTIONS=0")
    print("APPLICATION_SUBMISSION_ACTIONS=0")
    print("AUTHORITATIVE_LIFECYCLE_MUTATIONS=0")
    print("TRANSACTION=committed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
