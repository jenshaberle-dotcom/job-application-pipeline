"""Replay operator origin truth with prior blocked collector evidence.

The command reads two local JSON artifacts only:

* an immutable ``origin_operator_attestation`` artifact; and
* a prior origin-repair artifact containing an exact-URL HTTP 403 observation.

It performs no network access, retries, browser automation, provider request,
database write, pipeline mutation, or source activation. HTTP 403 remains a
blocked collector outcome and is never promoted to collection readiness.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

from src.search_intelligence.browser_protected_origin_architecture import (
    CollectorCapabilityEvidence,
    OriginTruthEvidence,
    evaluate_browser_protected_origin,
)
from src.search_intelligence.origin_source_discovery_agent import normalize_candidate_url

MAX_JSON_BYTES = 20_000_000
URL_KEYS = frozenset(
    {
        "canonical_url",
        "final_url",
        "normalized_url",
        "requested_url",
        "url",
    }
)
STATUS_KEYS = frozenset({"http_status", "status_code"})
REACHABLE_KEYS = frozenset({"prior_reachable", "reachable"})
CHALLENGE_BOOLEAN_KEYS = frozenset(
    {
        "access_control_blocked",
        "challenge_detected",
        "challenge_encountered",
    }
)
CHALLENGE_TEXT_KEYS = frozenset(
    {
        "body",
        "diagnostic",
        "diagnostics",
        "failure_class",
        "page_title",
        "reason",
        "reasons",
        "title",
    }
)
CHALLENGE_MARKERS = (
    "access control",
    "access denied",
    "captcha",
    "challenge",
    "checking your browser",
    "cloudflare",
    "forbidden",
    "just a moment",
    "rate limit",
    "too many requests",
    "verify you are human",
)
MUTATION_KEYS = frozenset(
    {
        "bronze_silver_write",
        "candidate_url_write",
        "connector_registration",
        "pipeline_mutation",
        "scheduler_change",
        "source_activation",
        "source_activation_allowed",
    }
)
PROVIDER_KEYS = frozenset({"provider_request_count", "provider_requests"})
BOUNDARY = (
    "local JSON artifacts only",
    "no network access",
    "no browser automation",
    "no access-control interaction or bypass",
    "no provider request",
    "no database or pipeline mutation",
    "no source activation",
    "review output only; not pipeline input",
)


def _read_json(path: Path, *, label: str) -> tuple[dict[str, object], bytes]:
    if not path.is_file():
        raise ValueError(f"{label} does not exist or is not a file: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise ValueError(f"{label} is empty: {path}")
    if size > MAX_JSON_BYTES:
        raise ValueError(f"{label} exceeds bounded size limit: {size}")
    raw = path.read_bytes()
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} root must be a JSON object")
    return decoded, raw


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _parse_timestamp(value: str, *, label: str) -> datetime:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp_from_filename(path: Path) -> datetime | None:
    match = re.search(r"(20\d{6})T(\d{6})\d*Z", path.name)
    if not match:
        return None
    try:
        return datetime.strptime(
            "".join(match.groups()),
            "%Y%m%d%H%M%S",
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _walk_mappings(
    value: object,
    *,
    path: tuple[str, ...] = (),
) -> Iterator[tuple[tuple[str, ...], Mapping[str, object]]]:
    if isinstance(value, Mapping):
        yield path, value
        for key, child in value.items():
            yield from _walk_mappings(child, path=(*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_mappings(child, path=(*path, str(index)))


def _flatten(
    value: object,
    *,
    path: tuple[str, ...] = (),
) -> list[tuple[tuple[str, ...], object]]:
    leaves: list[tuple[tuple[str, ...], object]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            leaves.extend(_flatten(child, path=(*path, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            leaves.extend(_flatten(child, path=(*path, str(index))))
    else:
        leaves.append((path, value))
    return leaves


def _last_key(path: tuple[str, ...]) -> str:
    return path[-1].lower() if path else ""


def _as_status(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if 100 <= parsed <= 599 else None


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    return ""


def _exact_url_values(
    leaves: Sequence[tuple[tuple[str, ...], object]],
    expected_url: str,
) -> list[str]:
    matches: list[str] = []
    for path, value in leaves:
        if _last_key(path) not in URL_KEYS or not isinstance(value, str):
            continue
        normalized = normalize_candidate_url(value)
        if normalized == expected_url:
            matches.append(value)
    return matches


def _challenge_indicators(
    leaves: Sequence[tuple[tuple[str, ...], object]],
) -> tuple[str, ...]:
    indicators: list[str] = []
    for path, value in leaves:
        key = _last_key(path)
        if key in CHALLENGE_BOOLEAN_KEYS and _as_bool(value) is True:
            indicators.append(f"{key}=true")
        if key not in CHALLENGE_TEXT_KEYS:
            continue
        text = _text(value).lower()
        for marker in CHALLENGE_MARKERS:
            if marker in text:
                indicators.append(f"{key}:{marker}")
    return tuple(dict.fromkeys(indicators))


def _validate_zero_provider_requests(payload: Mapping[str, object]) -> None:
    observed: list[int] = []
    for _, mapping in _walk_mappings(payload):
        for key, value in mapping.items():
            if str(key).lower() not in PROVIDER_KEYS:
                continue
            try:
                observed.append(int(value))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                raise ValueError("collector artifact has a non-integer provider count")
    if not observed:
        raise ValueError("collector artifact does not declare provider request counts")
    if any(value != 0 for value in observed):
        raise ValueError("collector artifact used provider requests")


def _validate_no_mutation(payload: Mapping[str, object]) -> None:
    for _, mapping in _walk_mappings(payload):
        for key, value in mapping.items():
            normalized = str(key).lower()
            if normalized not in MUTATION_KEYS:
                continue
            flag = _as_bool(value)
            if normalized == "source_activation_allowed":
                if flag is True:
                    raise ValueError("collector artifact grants source activation")
            elif flag is True:
                raise ValueError(f"collector artifact reports prohibited mutation: {normalized}")


def find_exact_blocked_observation(
    payload: Mapping[str, object],
    *,
    operator_url: str,
) -> dict[str, object]:
    """Find the smallest exact-URL 403/challenge observation subtree."""

    expected = normalize_candidate_url(operator_url)
    if expected is None:
        raise ValueError("operator URL is invalid")

    candidates: list[tuple[int, int, dict[str, object]]] = []
    for path, mapping in _walk_mappings(payload):
        leaves = _flatten(mapping)
        exact_urls = _exact_url_values(leaves, expected)
        if not exact_urls:
            continue
        statuses = [
            status
            for leaf_path, value in leaves
            if _last_key(leaf_path) in STATUS_KEYS
            for status in [_as_status(value)]
            if status is not None
        ]
        if 403 not in statuses:
            continue
        reachable_values = [
            _as_bool(value)
            for leaf_path, value in leaves
            if _last_key(leaf_path) in REACHABLE_KEYS
        ]
        if False not in reachable_values or True in reachable_values:
            continue
        indicators = _challenge_indicators(leaves)
        if not indicators:
            continue

        title = next(
            (
                _text(value)
                for leaf_path, value in leaves
                if _last_key(leaf_path) in {"page_title", "title"}
                and _text(value).strip()
            ),
            "",
        )
        failure_class = next(
            (
                _text(value)
                for leaf_path, value in leaves
                if _last_key(leaf_path) == "failure_class" and _text(value).strip()
            ),
            "",
        )
        result = {
            "json_path": "/" + "/".join(path),
            "normalized_url": expected,
            "status_code": 403,
            "reachable": False,
            "challenge_indicators": list(indicators),
            "title": title,
            "failure_class": failure_class or None,
        }
        candidates.append((len(leaves), -len(path), result))

    if not candidates:
        raise ValueError(
            "collector artifact lacks an exact-URL HTTP 403 observation with "
            "reachable=false and challenge/access-control evidence"
        )
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _origin_evidence_from_artifact(
    payload: Mapping[str, object],
    *,
    company_key: str,
    operator_url: str,
) -> OriginTruthEvidence:
    if payload.get("artifact_type") != "origin_operator_attestation":
        raise ValueError("origin artifact has the wrong artifact_type")
    if payload.get("review_output_only_not_pipeline_input") is not True:
        raise ValueError("origin artifact is not marked review-only")
    if payload.get("provider_requests") != 0:
        raise ValueError("origin artifact used provider requests")
    if payload.get("pipeline_mutation") is not False:
        raise ValueError("origin artifact does not prove zero pipeline mutation")
    if payload.get("source_activation_allowed") is not False:
        raise ValueError("origin artifact grants source activation")

    raw = payload.get("origin_evidence")
    if not isinstance(raw, Mapping):
        raise ValueError("origin artifact lacks origin_evidence")
    normalized_url = normalize_candidate_url(str(raw.get("normalized_url") or ""))
    expected = normalize_candidate_url(operator_url)
    if raw.get("company_key") != company_key or normalized_url != expected:
        raise ValueError("origin artifact company or exact URL does not match replay target")

    try:
        return OriginTruthEvidence(
            schema_version=str(raw["schema_version"]),
            evidence_id=str(raw["evidence_id"]),
            company_key=str(raw["company_key"]),
            normalized_url=str(raw["normalized_url"]),
            evidence_source=str(raw["evidence_source"]),  # type: ignore[arg-type]
            observed_at=str(raw["observed_at"]),
            expires_at=str(raw["expires_at"]),
            verifier_identity=str(raw["verifier_identity"]),
            verifier_version=str(raw["verifier_version"]),
            requested_url=str(raw["requested_url"]),
            final_url=str(raw["final_url"]),
            canonical_url=(
                None if raw.get("canonical_url") is None else str(raw["canonical_url"])
            ),
            page_title=str(raw["page_title"]),
            observed_entity_tokens=tuple(
                str(item) for item in raw.get("observed_entity_tokens", [])
            ),
            observed_career_signals=tuple(
                str(item) for item in raw.get("observed_career_signals", [])
            ),
            content_sha256=str(raw["content_sha256"]),
            screenshot_sha256=(
                None
                if raw.get("screenshot_sha256") is None
                else str(raw["screenshot_sha256"])
            ),
            operator_approval_token=(
                None
                if raw.get("operator_approval_token") is None
                else str(raw["operator_approval_token"])
            ),
            challenge_encountered=bool(raw.get("challenge_encountered", False)),
            automation_interacted_with_challenge=bool(
                raw.get("automation_interacted_with_challenge", False)
            ),
            automation_techniques=tuple(
                str(item) for item in raw.get("automation_techniques", [])
            ),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("origin artifact evidence schema is incomplete") from exc


def build_blocked_replay_artifact(
    *,
    company_key: str,
    operator_url: str,
    origin_artifact_path: Path,
    collector_artifact_path: Path,
    replay_at: str,
    collector_observed_at: str | None = None,
    collector_expires_at: str | None = None,
) -> dict[str, object]:
    """Build one deterministic local-only blocked-origin replay artifact."""

    normalized_url = normalize_candidate_url(operator_url)
    if normalized_url is None or not normalized_url.startswith("https://"):
        raise ValueError("operator URL must be a valid HTTPS URL")

    origin_payload, origin_raw = _read_json(origin_artifact_path, label="origin artifact")
    collector_payload, collector_raw = _read_json(
        collector_artifact_path,
        label="collector artifact",
    )
    origin_evidence = _origin_evidence_from_artifact(
        origin_payload,
        company_key=company_key,
        operator_url=normalized_url,
    )
    _validate_zero_provider_requests(collector_payload)
    _validate_no_mutation(collector_payload)
    observation = find_exact_blocked_observation(
        collector_payload,
        operator_url=normalized_url,
    )

    replay_time = _parse_timestamp(replay_at, label="replay_at")
    observed = (
        _parse_timestamp(collector_observed_at, label="collector_observed_at")
        if collector_observed_at
        else _timestamp_from_filename(collector_artifact_path)
    )
    if observed is None:
        raise ValueError(
            "collector observation timestamp is absent; provide --collector-observed-at"
        )
    expires = (
        _parse_timestamp(collector_expires_at, label="collector_expires_at")
        if collector_expires_at
        else observed + timedelta(days=30)
    )
    if expires <= observed:
        raise ValueError("collector_expires_at must be later than observation")

    collector_digest = _sha256(collector_raw)
    evidence_material = json.dumps(
        {
            "collector_sha256": collector_digest,
            "normalized_url": normalized_url,
            "observed_at": _iso_utc(observed),
            "status_code": 403,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    collector_evidence = CollectorCapabilityEvidence(
        schema_version="1.0",
        evidence_id="collector-blocked-" + _sha256(evidence_material)[:24],
        normalized_url=normalized_url,
        observed_at=_iso_utc(observed),
        expires_at=_iso_utc(expires),
        collector_identity="origin-url-default-repair-artifact",
        collector_version="blocked-replay/1.0",
        requested_url=normalized_url,
        final_url=normalized_url,
        status_code=403,
        reachable=False,
        challenge_detected=True,
        failure_class=str(observation.get("failure_class") or "access_control_challenge"),
        side_effect_free=True,
        provider_requests=0,
        pipeline_mutation=False,
    )
    decision = evaluate_browser_protected_origin(
        company_key=company_key,
        operator_url=normalized_url,
        required_entity_tokens=origin_evidence.observed_entity_tokens,
        origin_evidence=origin_evidence,
        collector_evidence=collector_evidence,
        now=_iso_utc(replay_time),
    )
    if decision.decision != "origin_verified_collection_blocked":
        raise ValueError(
            "combined evidence failed blocked-origin architecture replay: "
            + "; ".join(decision.reasons)
        )

    return {
        "artifact_type": "browser_protected_origin_replay",
        "schema_version": "1.0",
        "review_output_only_not_pipeline_input": True,
        "boundary": list(BOUNDARY),
        "origin_artifact": {
            "file_name": origin_artifact_path.name,
            "sha256": _sha256(origin_raw),
            "evidence_id": origin_evidence.evidence_id,
        },
        "collector_artifact": {
            "file_name": collector_artifact_path.name,
            "sha256": collector_digest,
            "matched_observation": observation,
        },
        "collector_evidence": collector_evidence.to_json(),
        "architecture_replay": decision.to_json(),
        "provider_requests": 0,
        "pipeline_mutation": False,
        "source_activation_allowed": False,
    }


def write_artifact(payload: Mapping[str, object], output_path: Path) -> Path:
    if output_path.exists():
        raise ValueError(f"output already exists; refusing overwrite: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_path)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay local operator origin truth with exact-URL blocked collector "
            "evidence. No network access or source activation is performed."
        )
    )
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--operator-url", required=True)
    parser.add_argument("--origin-artifact", type=Path, required=True)
    parser.add_argument("--collector-artifact", type=Path, required=True)
    parser.add_argument("--replay-at", required=True)
    parser.add_argument("--collector-observed-at")
    parser.add_argument("--collector-expires-at")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_blocked_replay_artifact(
            company_key=args.company_key,
            operator_url=args.operator_url,
            origin_artifact_path=args.origin_artifact,
            collector_artifact_path=args.collector_artifact,
            replay_at=args.replay_at,
            collector_observed_at=args.collector_observed_at,
            collector_expires_at=args.collector_expires_at,
        )
        output = write_artifact(payload, args.output)
    except ValueError as exc:
        print(f"blocked_origin_replay_error: {exc}", file=sys.stderr)
        return 2

    replay = payload["architecture_replay"]
    assert isinstance(replay, Mapping)
    print(f"artifact_json: {output}")
    print(f"decision: {replay['decision']}")
    print(f"origin_truth_state: {replay['origin_truth_state']}")
    print(f"collection_state: {replay['collection_state']}")
    print("provider_requests: 0")
    print("pipeline_mutation: false")
    print("source_activation_allowed: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
