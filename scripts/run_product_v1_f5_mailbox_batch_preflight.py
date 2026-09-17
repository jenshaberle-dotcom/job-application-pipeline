#!/usr/bin/env python3
"""Read-only batch preflight for normalized F5 mailbox observations.

This script validates private-runtime JSONL against the public mailbox contract and
classifies evidence using the production deterministic classifier. It never opens a
Gmail connection and never connects to PostgreSQL.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.product_v1_f5_mailbox_ingest import (  # noqa: E402
    MailboxIngestError,
    evidence_fingerprint,
    mailbox_application_key,
    parse_normalized_mailbox_observation,
    should_discover_application,
)
from src.search_intelligence.application_event_classifier import (  # noqa: E402
    ClassificationResult,
    classify_application_evidence,
)


_REVIEW_WORTHY_CLASSES = frozenset(
    {
        "application_acknowledgement",
        "recruiter_contact",
        "interview_invitation",
        "assessment_request",
        "offer_signal",
        "rejection",
        "withdrawal_confirmation",
        "ambiguous",
    }
)


class MailboxBatchPreflightError(RuntimeError):
    """Fail closed when a batch cannot be safely preflighted."""


@dataclass(frozen=True)
class Finding:
    observed_at: str
    candidate_class: str
    reason_code: str
    employer_name: str | None
    job_title: str | None
    mail_direction: str
    counterparty_domain: str | None
    discoverable: bool


@dataclass(frozen=True)
class BatchPreflightResult:
    input_rows: int
    window_rows: int
    valid_rows: int
    invalid_rows: int
    discoverable_rows: int
    review_worthy_rows: int
    other_rows: int
    ambiguous_rows: int
    unique_application_keys: int
    duplicate_evidence_rows: int
    class_counts: dict[str, int]
    findings: tuple[Finding, ...]


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
        raise MailboxBatchPreflightError(f"input_missing:{path}")
    rows: list[dict[str, object]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MailboxBatchPreflightError(
                f"invalid_jsonl_line:{line_no}"
            ) from exc
        if not isinstance(payload, dict):
            raise MailboxBatchPreflightError(f"invalid_jsonl_row:{line_no}")
        rows.append(payload)
    return rows


def _classification(payload: Mapping[str, object]) -> tuple[Any, ClassificationResult]:
    observation = parse_normalized_mailbox_observation(payload)
    classification = classify_application_evidence(
        subject=observation.subject,
        text_excerpt=observation.text_excerpt,
        sender_domain=observation.sender_domain,
        mail_direction=observation.mail_direction,
        counterparty_domain=observation.counterparty_domain,
        deterministic_event_signals=observation.gmail_search_signals,
    )
    return observation, classification


def preflight_rows(
    rows: list[dict[str, object]],
    *,
    since: date | None = None,
    until: date | None = None,
) -> BatchPreflightResult:
    if since is not None and until is not None and until < since:
        raise MailboxBatchPreflightError("until_before_since")

    valid_rows = 0
    invalid_rows = 0
    window_rows = 0
    discoverable_rows = 0
    review_worthy_rows = 0
    other_rows = 0
    ambiguous_rows = 0
    duplicate_evidence_rows = 0
    class_counts: Counter[str] = Counter()
    application_keys: set[str] = set()
    evidence_keys: set[str] = set()
    findings: list[Finding] = []

    for payload in rows:
        observed_date = _row_date(payload)
        if since is not None and (observed_date is None or observed_date < since):
            continue
        if until is not None and (observed_date is None or observed_date > until):
            continue
        window_rows += 1

        try:
            observation, classification = _classification(payload)
        except MailboxIngestError:
            invalid_rows += 1
            continue

        valid_rows += 1
        class_counts[classification.candidate_class] += 1
        discoverable = should_discover_application(classification)
        if discoverable:
            discoverable_rows += 1
            application_keys.add(mailbox_application_key(observation))

        if classification.candidate_class in _REVIEW_WORTHY_CLASSES:
            review_worthy_rows += 1
        if classification.candidate_class == "other":
            other_rows += 1
        if classification.candidate_class == "ambiguous":
            ambiguous_rows += 1

        evidence_key = evidence_fingerprint(observation, classification)
        if evidence_key in evidence_keys:
            duplicate_evidence_rows += 1
        else:
            evidence_keys.add(evidence_key)

        if discoverable or classification.candidate_class in _REVIEW_WORTHY_CLASSES:
            findings.append(
                Finding(
                    observed_at=observation.observed_at.isoformat(),
                    candidate_class=classification.candidate_class,
                    reason_code=classification.reason_code,
                    employer_name=observation.employer_name,
                    job_title=observation.job_title,
                    mail_direction=observation.mail_direction,
                    counterparty_domain=observation.counterparty_domain,
                    discoverable=discoverable,
                )
            )

    findings.sort(key=lambda item: item.observed_at, reverse=True)
    return BatchPreflightResult(
        input_rows=len(rows),
        window_rows=window_rows,
        valid_rows=valid_rows,
        invalid_rows=invalid_rows,
        discoverable_rows=discoverable_rows,
        review_worthy_rows=review_worthy_rows,
        other_rows=other_rows,
        ambiguous_rows=ambiguous_rows,
        unique_application_keys=len(application_keys),
        duplicate_evidence_rows=duplicate_evidence_rows,
        class_counts=dict(sorted(class_counts.items())),
        findings=tuple(findings),
    )


def print_result(result: BatchPreflightResult, *, findings_limit: int) -> None:
    print("F5_MAILBOX_BATCH_PREFLIGHT=PASS" if result.invalid_rows == 0 else "F5_MAILBOX_BATCH_PREFLIGHT=FAIL")
    print(f"INPUT_ROWS={result.input_rows}")
    print(f"WINDOW_ROWS={result.window_rows}")
    print(f"VALID_ROWS={result.valid_rows}")
    print(f"INVALID_ROWS={result.invalid_rows}")
    print(f"DISCOVERABLE_ROWS={result.discoverable_rows}")
    print(f"REVIEW_WORTHY_ROWS={result.review_worthy_rows}")
    print(f"OTHER_ROWS={result.other_rows}")
    print(f"AMBIGUOUS_ROWS={result.ambiguous_rows}")
    print(f"UNIQUE_APPLICATION_KEYS={result.unique_application_keys}")
    print(f"DUPLICATE_EVIDENCE_ROWS={result.duplicate_evidence_rows}")
    print("GMAIL_NETWORK_REQUESTS=0")
    print("DATABASE_CONNECTIONS=0")
    print("DATABASE_WRITES=0")
    print("APPLICATION_SUBMISSION_ACTIONS=0")
    for candidate_class, count in result.class_counts.items():
        key = candidate_class.upper().replace("-", "_")
        print(f"CLASS_{key}={count}")
    for index, finding in enumerate(result.findings[:findings_limit], 1):
        print(f"FINDING_{index}_DATE={finding.observed_at[:10]}")
        print(f"FINDING_{index}_CLASS={finding.candidate_class}")
        print(f"FINDING_{index}_REASON={finding.reason_code}")
        print(f"FINDING_{index}_DISCOVERABLE={'true' if finding.discoverable else 'false'}")
        print(f"FINDING_{index}_EMPLOYER={finding.employer_name or 'UNKNOWN'}")
        print(f"FINDING_{index}_TITLE={finding.job_title or 'UNKNOWN'}")
        print(f"FINDING_{index}_DIRECTION={finding.mail_direction}")
        print(f"FINDING_{index}_COUNTERPARTY_DOMAIN={finding.counterparty_domain or 'UNKNOWN'}")


def write_json(path: Path, result: BatchPreflightResult) -> None:
    payload = asdict(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only F5 normalized mailbox batch preflight")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--since", type=_parse_iso_date)
    parser.add_argument("--until", type=_parse_iso_date)
    parser.add_argument("--findings-limit", type=int, default=50)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.findings_limit < 0:
        raise SystemExit("findings_limit_must_be_nonnegative")
    try:
        result = preflight_rows(
            load_jsonl(args.input.expanduser()),
            since=args.since,
            until=args.until,
        )
        print_result(result, findings_limit=args.findings_limit)
        if args.output is not None:
            write_json(args.output.expanduser(), result)
        return 0 if result.invalid_rows == 0 else 2
    except MailboxBatchPreflightError as exc:
        print(f"F5_MAILBOX_BATCH_PREFLIGHT_ERROR={exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
