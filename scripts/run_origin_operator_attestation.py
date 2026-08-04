"""Create a read-only operator origin-attestation artifact from local evidence.

The command performs no network access. It reads an operator-supplied local
text/HTML file, optionally hashes a screenshot, validates exact employer/entity
and career evidence, and writes a review-only JSON artifact.

It does not activate a source, create a connector, call a provider, mutate the
database, or authorize an automated client to pass an access-control challenge.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Sequence

from src.search_intelligence.browser_protected_origin_architecture import (
    OriginTruthEvidence,
    evaluate_browser_protected_origin,
)
from src.search_intelligence.origin_source_discovery_agent import normalize_candidate_url

MAX_CONTENT_BYTES = 5_000_000
MAX_SCREENSHOT_BYTES = 20_000_000
CHALLENGE_MARKERS = (
    "access denied",
    "captcha",
    "checking your browser",
    "cloudflare ray id",
    "just a moment",
    "press and hold",
    "verify you are human",
)
BOUNDARY = (
    "local files only",
    "no network access",
    "no browser automation",
    "no challenge interaction",
    "no provider request",
    "no database or pipeline mutation",
    "no source activation",
    "review output only; not pipeline input",
)


def _parse_timestamp(value: str, *, label: str) -> datetime:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: str, *, label: str) -> str:
    parsed = _parse_timestamp(value, label=label)
    return parsed.isoformat().replace("+00:00", "Z")


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _read_bounded(path: Path, *, maximum: int, label: str) -> bytes:
    if not path.is_file():
        raise ValueError(f"{label} does not exist or is not a file: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise ValueError(f"{label} is empty: {path}")
    if size > maximum:
        raise ValueError(f"{label} exceeds bounded size limit: {size} > {maximum}")
    return path.read_bytes()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _normalized_unique(values: Sequence[str], *, label: str) -> tuple[str, ...]:
    result: list[str] = []
    for raw in values:
        value = str(raw or "").strip().lower()
        if not value:
            continue
        if value not in result:
            result.append(value)
    if not result:
        raise ValueError(f"at least one {label} is required")
    return tuple(result)


def _assert_grounded_content(
    *,
    content_text: str,
    page_title: str,
    entity_tokens: tuple[str, ...],
    career_signals: tuple[str, ...],
) -> None:
    combined = f"{page_title}\n{content_text}".lower()
    compact = _compact(combined)

    matched_challenge = [
        marker for marker in CHALLENGE_MARKERS if marker in combined
    ]
    if matched_challenge:
        raise ValueError(
            "local evidence contains an access-control challenge marker: "
            + ", ".join(matched_challenge)
        )

    missing_entity = [
        token for token in entity_tokens if _compact(token) not in compact
    ]
    if missing_entity:
        raise ValueError(
            "local evidence lacks declared distinctive employer entity tokens: "
            + ", ".join(missing_entity)
        )

    if not any(_compact(signal) in compact for signal in career_signals):
        raise ValueError(
            "local evidence lacks every declared career or job signal"
        )


def _artifact_id(
    *,
    company_key: str,
    normalized_url: str,
    observed_at: str,
    content_sha256: str,
    reviewer_identity: str,
) -> str:
    material = json.dumps(
        {
            "company_key": company_key,
            "normalized_url": normalized_url,
            "observed_at": observed_at,
            "content_sha256": content_sha256,
            "reviewer_identity": reviewer_identity,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "origin-operator-attestation-" + _sha256(material)[:24]


def build_operator_attestation_artifact(
    *,
    company_key: str,
    operator_url: str,
    reviewer_identity: str,
    approval_token: str,
    page_title: str,
    entity_tokens: Sequence[str],
    career_signals: Sequence[str],
    content_path: Path,
    screenshot_path: Path | None,
    observed_at: str,
    expires_at: str,
) -> dict[str, object]:
    """Build and architecture-replay one local operator attestation."""

    normalized_url = normalize_candidate_url(operator_url)
    if normalized_url is None or not normalized_url.startswith("https://"):
        raise ValueError("operator URL must be a valid HTTPS URL")

    company = str(company_key or "").strip()
    reviewer = str(reviewer_identity or "").strip()
    token = str(approval_token or "").strip()
    title = str(page_title or "").strip()
    if not company:
        raise ValueError("company key is required")
    if not reviewer:
        raise ValueError("reviewer identity is required")
    if not token:
        raise ValueError("approval token is required")
    if not title:
        raise ValueError("page title is required")

    observed = _iso_utc(observed_at, label="observed_at")
    expires = _iso_utc(expires_at, label="expires_at")
    if _parse_timestamp(expires, label="expires_at") <= _parse_timestamp(
        observed,
        label="observed_at",
    ):
        raise ValueError("expires_at must be later than observed_at")

    normalized_entities = _normalized_unique(
        entity_tokens,
        label="distinctive entity token",
    )
    normalized_careers = _normalized_unique(
        career_signals,
        label="career signal",
    )

    content_bytes = _read_bounded(
        content_path,
        maximum=MAX_CONTENT_BYTES,
        label="content file",
    )
    try:
        content_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("content file must be UTF-8 text or HTML") from exc

    _assert_grounded_content(
        content_text=content_text,
        page_title=title,
        entity_tokens=normalized_entities,
        career_signals=normalized_careers,
    )

    content_digest = _sha256(content_bytes)
    screenshot_digest: str | None = None
    screenshot_name: str | None = None
    if screenshot_path is not None:
        screenshot_bytes = _read_bounded(
            screenshot_path,
            maximum=MAX_SCREENSHOT_BYTES,
            label="screenshot file",
        )
        screenshot_digest = _sha256(screenshot_bytes)
        screenshot_name = screenshot_path.name

    evidence_id = _artifact_id(
        company_key=company,
        normalized_url=normalized_url,
        observed_at=observed,
        content_sha256=content_digest,
        reviewer_identity=reviewer,
    )
    evidence = OriginTruthEvidence(
        schema_version="1.0",
        evidence_id=evidence_id,
        company_key=company,
        normalized_url=normalized_url,
        evidence_source="operator_attestation",
        observed_at=observed,
        expires_at=expires,
        verifier_identity=reviewer,
        verifier_version="operator-origin-attestation-writer/1.0",
        requested_url=normalized_url,
        final_url=normalized_url,
        canonical_url=normalized_url,
        page_title=title,
        observed_entity_tokens=normalized_entities,
        observed_career_signals=normalized_careers,
        content_sha256=content_digest,
        screenshot_sha256=screenshot_digest,
        operator_approval_token="sha256:" + _sha256(token.encode("utf-8")),
        challenge_encountered=False,
        automation_interacted_with_challenge=False,
        automation_techniques=(),
    )
    replay = evaluate_browser_protected_origin(
        company_key=company,
        operator_url=normalized_url,
        required_entity_tokens=normalized_entities,
        origin_evidence=evidence,
        collector_evidence=None,
        now=observed,
    )
    if replay.decision != "origin_verified_collection_unknown":
        raise ValueError(
            "operator attestation failed architecture validation: "
            + "; ".join(replay.reasons)
        )

    return {
        "artifact_type": "origin_operator_attestation",
        "schema_version": "1.0",
        "review_output_only_not_pipeline_input": True,
        "boundary": list(BOUNDARY),
        "origin_evidence": evidence.to_json(),
        "architecture_replay": replay.to_json(),
        "local_evidence": {
            "content_file_name": content_path.name,
            "content_sha256": content_digest,
            "screenshot_file_name": screenshot_name,
            "screenshot_sha256": screenshot_digest,
        },
        "provider_requests": 0,
        "pipeline_mutation": False,
        "source_activation_allowed": False,
    }


def write_artifact(payload: dict[str, object], output_path: Path) -> Path:
    """Write one immutable review artifact without overwriting prior evidence."""

    if output_path.exists():
        raise ValueError(f"output already exists; refusing overwrite: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_path)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a review-only operator origin attestation from local evidence. "
            "The command performs no network access."
        )
    )
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--operator-url", required=True)
    parser.add_argument("--reviewer-identity", required=True)
    parser.add_argument("--approval-token", required=True)
    parser.add_argument("--page-title", required=True)
    parser.add_argument("--entity-token", action="append", default=[], required=True)
    parser.add_argument("--career-signal", action="append", default=[], required=True)
    parser.add_argument("--content-file", type=Path, required=True)
    parser.add_argument("--screenshot-file", type=Path)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--expires-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        payload = build_operator_attestation_artifact(
            company_key=args.company_key,
            operator_url=args.operator_url,
            reviewer_identity=args.reviewer_identity,
            approval_token=args.approval_token,
            page_title=args.page_title,
            entity_tokens=args.entity_token,
            career_signals=args.career_signal,
            content_path=args.content_file,
            screenshot_path=args.screenshot_file,
            observed_at=args.observed_at,
            expires_at=args.expires_at,
        )
        output = write_artifact(payload, args.output)
    except ValueError as exc:
        print(f"operator_attestation_error: {exc}", file=sys.stderr)
        return 2

    replay = payload["architecture_replay"]
    decision = replay.get("decision") if isinstance(replay, dict) else None
    print(f"artifact_json: {output}")
    print(f"decision: {decision}")
    print("provider_requests: 0")
    print("pipeline_mutation: false")
    print("source_activation_allowed: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
