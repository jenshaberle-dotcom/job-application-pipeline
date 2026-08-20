from __future__ import annotations

from typing import Any


CONNECTOR_CANDIDATE_READY_DECISIONS = frozenset(
    {
        "passed",
        "build_connector_candidate",
    }
)


def connector_candidate_decision_ready(decision: str | None) -> bool:
    return decision in CONNECTOR_CANDIDATE_READY_DECISIONS


def connector_candidate_spec_from_evidence(evidence: dict[str, Any] | None) -> dict[str, Any]:
    spec = (evidence or {}).get("connector_candidate_spec") or {}
    return spec if isinstance(spec, dict) else {}


def connector_candidate_detail_urls(spec: dict[str, Any]) -> tuple[str, ...]:
    detail_evidence = spec.get("detail_evidence") or {}
    urls = detail_evidence.get("detail_urls") or []
    return tuple(
        str(url)
        for url in urls
        if str(url).startswith(("http://", "https://"))
    )
