#!/usr/bin/env python3
"""Provider-free/read-only persistence planner for normalized F5 mailbox evidence.

The planner never connects to Gmail or PostgreSQL. It predicts application inserts,
candidate inserts, no-ops and source-message supersessions against an explicit
bounded state snapshot. First-seen `other` noise is skipped, while `other` may
supersede an already-active relevant interpretation so stale evidence cannot remain
active. Real persistence remains a separately authorized action.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
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
from src.search_intelligence.application_event_classifier import (  # noqa: E402
    classify_application_evidence,
)
from src.search_intelligence.application_identity_matching import (  # noqa: E402
    ExistingApplicationIdentity,
    match_existing_application_identity,
)


class PersistencePreflightError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActiveCandidate:
    source_identity_key: str
    evidence_fingerprint: str
    candidate_class: str
    application_key: str | None


@dataclass(frozen=True)
class PersistencePlan:
    input_rows: int
    window_rows: int
    valid_rows: int
    invalid_rows: int
    persistence_candidate_rows: int
    skipped_other_rows: int
    application_inserts: int
    candidate_inserts: int
    candidate_noops: int
    candidate_supersessions: int
    unique_source_messages: int
    class_counts: dict[str, int]


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


def load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        raise PersistencePreflightError(f"input_missing:{path}")
    rows: list[dict[str, object]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PersistencePreflightError(f"invalid_jsonl_line:{line_no}") from exc
        if not isinstance(payload, dict):
            raise PersistencePreflightError(f"invalid_jsonl_row:{line_no}")
        rows.append(payload)
    return rows


def load_state(path: Path | None, *, assume_empty: bool) -> tuple[set[str], dict[str, ActiveCandidate]]:
    if assume_empty:
        if path is not None:
            raise PersistencePreflightError("state_and_assume_empty_are_mutually_exclusive")
        return set(), {}
    if path is None or not path.is_file():
        raise PersistencePreflightError("explicit_state_required")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PersistencePreflightError("state_must_be_object")
    application_keys_raw = payload.get("application_keys", [])
    candidates_raw = payload.get("active_candidates", [])
    if not isinstance(application_keys_raw, list) or not isinstance(candidates_raw, list):
        raise PersistencePreflightError("invalid_state_shape")

    application_keys = {str(item) for item in application_keys_raw if str(item).strip()}
    active: dict[str, ActiveCandidate] = {}
    for item in candidates_raw:
        if not isinstance(item, dict):
            raise PersistencePreflightError("invalid_active_candidate_state")
        candidate = ActiveCandidate(
            source_identity_key=str(item.get("source_identity_key") or "").strip(),
            evidence_fingerprint=str(item.get("evidence_fingerprint") or "").strip(),
            candidate_class=str(item.get("candidate_class") or "").strip(),
            application_key=(
                str(item.get("application_key")).strip()
                if item.get("application_key") is not None
                else None
            ),
        )
        if not candidate.source_identity_key or not candidate.evidence_fingerprint or not candidate.candidate_class:
            raise PersistencePreflightError("incomplete_active_candidate_state")
        if candidate.source_identity_key in active:
            raise PersistencePreflightError("duplicate_active_source_identity")
        active[candidate.source_identity_key] = candidate
    return application_keys, active


def plan_rows(
    rows: list[dict[str, object]],
    *,
    existing_application_keys: set[str] | None = None,
    existing_application_identities: list[ExistingApplicationIdentity] | None = None,
    active_candidates: Mapping[str, ActiveCandidate] | None = None,
    since: date | None = None,
    until: date | None = None,
) -> PersistencePlan:
    if since is not None and until is not None and until < since:
        raise PersistencePreflightError("until_before_since")

    applications = set(existing_application_keys or set())
    application_identities = list(existing_application_identities or [])
    active = dict(active_candidates or {})
    initial_applications = set(applications)
    window_rows = 0
    valid_rows = 0
    invalid_rows = 0
    persistence_candidate_rows = 0
    skipped_other_rows = 0
    candidate_inserts = 0
    candidate_noops = 0
    candidate_supersessions = 0
    class_counts: Counter[str] = Counter()
    source_messages: set[str] = set()

    for payload in rows:
        observed_date = _row_date(payload)
        if since is not None and (observed_date is None or observed_date < since):
            continue
        if until is not None and (observed_date is None or observed_date > until):
            continue
        window_rows += 1

        try:
            observation = parse_normalized_mailbox_observation(payload)
        except MailboxIngestError:
            invalid_rows += 1
            continue
        valid_rows += 1

        classification = classify_application_evidence(
            subject=observation.subject,
            text_excerpt=observation.text_excerpt,
            sender_domain=observation.sender_domain,
            mail_direction=observation.mail_direction,
            counterparty_domain=observation.counterparty_domain,
            deterministic_event_signals=observation.gmail_search_signals,
        )
        source_key = source_message_identity_key(observation)
        existing = active.get(source_key)
        default_persistence_allowed = should_persist_candidate(classification)

        if not default_persistence_allowed and existing is None:
            skipped_other_rows += 1
            continue

        persistence_candidate_rows += 1
        class_counts[classification.candidate_class] += 1
        source_messages.add(source_key)
        interpretation = evidence_fingerprint(observation, classification)

        application_key: str | None = existing.application_key if existing else None
        if (
            default_persistence_allowed
            and application_key is None
            and should_discover_application(classification)
        ):
            matched_key, ambiguous_existing, _match_basis = (
                match_existing_application_identity(
                    employer_name=observation.employer_name,
                    job_title=observation.job_title,
                    source_url=observation.source_url,
                    applications=application_identities,
                    counterparty_domain=observation.counterparty_domain,
                    thread_reference=observation.thread_reference,
                )
            )
            if matched_key is not None:
                application_key = matched_key
            elif not ambiguous_existing:
                application_key = mailbox_application_key(observation)
                applications.add(application_key)

        if (
            existing is not None
            and existing.evidence_fingerprint == interpretation
            and existing.candidate_class == classification.candidate_class
            and existing.application_key == application_key
        ):
            candidate_noops += 1
            continue

        replacement = ActiveCandidate(
            source_identity_key=source_key,
            evidence_fingerprint=interpretation,
            candidate_class=classification.candidate_class,
            application_key=application_key,
        )
        if existing is None:
            candidate_inserts += 1
        else:
            candidate_supersessions += 1
        active[source_key] = replacement

    return PersistencePlan(
        input_rows=len(rows),
        window_rows=window_rows,
        valid_rows=valid_rows,
        invalid_rows=invalid_rows,
        persistence_candidate_rows=persistence_candidate_rows,
        skipped_other_rows=skipped_other_rows,
        application_inserts=len(applications - initial_applications),
        candidate_inserts=candidate_inserts,
        candidate_noops=candidate_noops,
        candidate_supersessions=candidate_supersessions,
        unique_source_messages=len(source_messages),
        class_counts=dict(sorted(class_counts.items())),
    )


def print_plan(plan: PersistencePlan) -> None:
    print("F5_MAILBOX_PERSISTENCE_PREFLIGHT=PASS" if plan.invalid_rows == 0 else "F5_MAILBOX_PERSISTENCE_PREFLIGHT=FAIL")
    for key, value in asdict(plan).items():
        if key == "class_counts":
            continue
        print(f"{key.upper()}={value}")
    for candidate_class, count in plan.class_counts.items():
        print(f"CLASS_{candidate_class.upper()}={count}")
    print("GMAIL_NETWORK_REQUESTS=0")
    print("DATABASE_CONNECTIONS=0")
    print("DATABASE_WRITES=0")
    print("APPLICATION_SUBMISSION_ACTIONS=0")
    print("AUTHORITATIVE_LIFECYCLE_MUTATIONS=0")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only F5 mailbox persistence planner")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--assume-empty-state", action="store_true")
    parser.add_argument("--since", type=_parse_iso_date)
    parser.add_argument("--until", type=_parse_iso_date)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        application_keys, active = load_state(
            args.state.expanduser() if args.state else None,
            assume_empty=args.assume_empty_state,
        )
        plan = plan_rows(
            load_jsonl(args.input.expanduser()),
            existing_application_keys=application_keys,
            active_candidates=active,
            since=args.since,
            until=args.until,
        )
    except (PersistencePreflightError, json.JSONDecodeError) as exc:
        print(f"F5_MAILBOX_PERSISTENCE_PREFLIGHT_ERROR={exc}")
        return 2

    print_plan(plan)
    if args.output is not None:
        args.output.expanduser().parent.mkdir(parents=True, exist_ok=True)
        args.output.expanduser().write_text(
            json.dumps(asdict(plan), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0 if plan.invalid_rows == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
