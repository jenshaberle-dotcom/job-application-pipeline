"""Exact-head read-only Product proof for the F5 mailbox-first tracking projection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.product_v1_f5_application_tracking_runtime import (
    SCHEMA_VERSION,
    STAGES,
    load_application_tracking_payload,
)


PROOF_SCHEMA = "jap.f5.application_tracking_product_proof.v2"


def build_report(*, source_sha: str) -> dict[str, object]:
    payload = load_application_tracking_payload()
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("F5_TRACKING_SCHEMA_MISMATCH")
    if payload.get("available") is not True:
        raise RuntimeError("F5_TRACKING_RELATION_UNAVAILABLE")

    boundaries = payload.get("boundaries") or {}
    expected_boundaries = {
        "read_only_projection": True,
        "mailbox_observed_status_is_separate_from_authoritative_history": True,
        "unknown_job_application_supported": True,
        "gmail_credentials_present": False,
        "raw_mail_body_exposed": False,
        "email_send_authority": False,
        "automatic_application_submission": False,
    }
    for key, expected in expected_boundaries.items():
        if boundaries.get(key) != expected:
            raise RuntimeError(f"F5_TRACKING_BOUNDARY_MISMATCH:{key}")

    applications = payload.get("applications") or []
    for row in applications:
        if not isinstance(row, dict):
            raise RuntimeError("F5_TRACKING_APPLICATION_ROW_INVALID")
        authoritative_stage = row.get("authoritative_stage")
        effective_stage = row.get("effective_stage")
        observed_stage = row.get("observed_stage")
        if authoritative_stage not in STAGES:
            raise RuntimeError(f"F5_TRACKING_AUTHORITATIVE_STAGE_INVALID:{authoritative_stage}")
        if effective_stage not in STAGES:
            raise RuntimeError(f"F5_TRACKING_EFFECTIVE_STAGE_INVALID:{effective_stage}")
        if observed_stage is not None and observed_stage not in STAGES:
            raise RuntimeError(f"F5_TRACKING_OBSERVED_STAGE_INVALID:{observed_stage}")
        if row.get("silver_job_id") is None and row.get("job_link_status") != "external":
            raise RuntimeError("F5_TRACKING_UNKNOWN_JOB_LINK_STATUS_INVALID")
        for candidate in row.get("evidence_candidates") or []:
            if not isinstance(candidate, dict) or candidate.get("authority") != "evidence_only":
                raise RuntimeError("F5_TRACKING_CANDIDATE_AUTHORITY_INVALID")
            evidence = candidate.get("evidence") or {}
            if any(key in evidence for key in ("raw_body", "body", "headers", "raw_message")):
                raise RuntimeError("F5_TRACKING_RAW_MAIL_EXPOSED")

    summary = payload.get("summary") or {}
    return {
        "schema": PROOF_SCHEMA,
        "source_sha": source_sha,
        "tracking_schema": payload.get("schema_version"),
        "available": True,
        "summary": summary,
        "boundaries": expected_boundaries,
        "proof": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(source_sha=args.source_sha)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    summary = report["summary"]
    print(f"F5_TRACKING_SOURCE_SHA={args.source_sha}")
    print(f"F5_TRACKING_APPLICATIONS={summary.get('application_count')}")
    print(f"F5_TRACKING_MAILBOX_DISCOVERED={summary.get('mailbox_discovered_count')}")
    print(f"F5_TRACKING_OBSERVED_STATUS={summary.get('observed_status_count')}")
    print(f"F5_TRACKING_ATTENTION={summary.get('attention_count')}")
    print(f"F5_TRACKING_UNMATCHED={summary.get('unmatched_candidate_count')}")
    print("F5_TRACKING_REAL_PRODUCT_PROOF=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
