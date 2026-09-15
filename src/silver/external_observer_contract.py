"""Tool-neutral contract for optional external evidence observers.

External tools are discovery-only. They may propose exact source spans, but they
never establish Silver truth, Candidate Facts, fit, ranking, Top-5 or application
authority. JAP validates every returned span against the bounded employer-origin
text and deliberately discards external normalized values.

The core imports no third-party observer package. Optional adapters can run in a
separate process and speak this small JSON contract instead.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
from typing import Mapping, Sequence

from src.silver.operator_requirement_semantics import ObservedFact


EXTERNAL_OBSERVER_SCHEMA = "jap.external_evidence_observer.v1"


class ExternalObserverError(RuntimeError):
    """Raised when an optional observer violates the transport contract."""


@dataclass(frozen=True)
class ExternalObserverResult:
    observer_name: str
    facts: tuple[ObservedFact, ...]
    proposed_count: int
    rejected_count: int


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def validate_external_skill_payload(
    *,
    text: str,
    payload: Mapping[str, object],
    observer_name: str,
) -> ExternalObserverResult:
    """Accept only exact skill spans from one external observer response.

    Any taxonomy label, canonical skill name, confidence or semantic class from
    the external tool is diagnostic only. The resulting :class:`ObservedFact`
    carries the exact employer-origin span as both value and evidence so an
    external normalizer cannot silently create product truth.
    """

    source = str(text or "")
    rows = payload.get("observations")
    if not isinstance(rows, list):
        raise ExternalObserverError("external observer response has no observations list")

    accepted: list[ObservedFact] = []
    rejected = 0
    seen: set[tuple[int, int, str]] = set()
    for raw in rows:
        row = _mapping(raw)
        if str(row.get("field") or "").casefold() != "skills":
            rejected += 1
            continue
        start = row.get("start")
        end = row.get("end")
        evidence = str(row.get("evidence") or "")
        if not isinstance(start, int) or isinstance(start, bool):
            rejected += 1
            continue
        if not isinstance(end, int) or isinstance(end, bool):
            rejected += 1
            continue
        if start < 0 or end <= start or end > len(source):
            rejected += 1
            continue
        exact = source[start:end]
        if not evidence or evidence != exact:
            rejected += 1
            continue
        identity = (start, end, exact.casefold())
        if identity in seen:
            continue
        seen.add(identity)
        accepted.append(
            ObservedFact(
                field="skills",
                value=exact,
                evidence=exact,
                basis=f"external_shadow:{observer_name}",
            )
        )

    return ExternalObserverResult(
        observer_name=observer_name,
        facts=tuple(accepted),
        proposed_count=len(rows),
        rejected_count=rejected,
    )


def run_external_skill_observer(
    *,
    command: Sequence[str],
    text: str,
    observer_name: str,
    timeout_seconds: float = 30.0,
) -> ExternalObserverResult:
    """Run one optional JSON observer in a separate process.

    Missing observers are handled by callers as an unavailable optional
    capability. A configured observer that crashes or returns malformed output
    fails closed for the research run; it never changes the normal JAP path.
    """

    if not command:
        raise ExternalObserverError("external observer command is empty")
    request = json.dumps(
        {"schema": EXTERNAL_OBSERVER_SCHEMA, "text": str(text or "")},
        ensure_ascii=False,
    )
    try:
        completed = subprocess.run(
            list(command),
            input=request + "\n",
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ExternalObserverError(f"external observer execution failed: {exc}") from exc
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise ExternalObserverError(
            f"external observer exited {completed.returncode}: {message[:500]}"
        )
    try:
        decoded = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ExternalObserverError("external observer returned invalid JSON") from exc
    if not isinstance(decoded, Mapping):
        raise ExternalObserverError("external observer returned non-object JSON")
    return validate_external_skill_payload(
        text=str(text or ""),
        payload=decoded,
        observer_name=observer_name,
    )


__all__ = [
    "EXTERNAL_OBSERVER_SCHEMA",
    "ExternalObserverError",
    "ExternalObserverResult",
    "run_external_skill_observer",
    "validate_external_skill_payload",
]
