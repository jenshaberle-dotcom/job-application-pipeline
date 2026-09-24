"""Exact URL-bound reuse of persisted current vacancy observations.

This module is read-only and grants no Product, lifecycle, ranking, application,
submission or send authority. It only exposes vacancy text already persisted by a
current recurring Employer-Origin observation when three independent bindings agree:
Silver source URL, observation source URL, and normalized nested job source URL.

The same contract is shared by assessment materialization and the Product V1
Application Workspace so downstream consumers do not create redundant network paths.
"""

from __future__ import annotations

from typing import Mapping


def flatten_source_text(value: object) -> list[str]:
    """Deterministically flatten source-provided structured vacancy evidence."""

    if isinstance(value, str):
        text = " ".join(value.split())
        return [text] if text else []
    if isinstance(value, Mapping):
        parts: list[str] = []
        for key in sorted(value, key=lambda item: str(item)):
            parts.extend(flatten_source_text(value[key]))
        return parts
    if isinstance(value, (list, tuple)):
        parts: list[str] = []
        for item in value:
            parts.extend(flatten_source_text(item))
        return parts
    return []


def bound_observation_detail(
    row: Mapping[str, object],
) -> tuple[str, str] | None:
    """Return persisted vacancy title/text only for exact URL-bound evidence."""

    source_url = str(row.get("source_url") or "")
    normalized = row.get("latest_observation_evidence")
    if not source_url or not isinstance(normalized, Mapping):
        return None
    if str(row.get("latest_observation_source_url") or "") != source_url:
        return None
    if str(normalized.get("source_url") or "") != source_url:
        return None

    raw_evidence = normalized.get("raw_evidence")
    if not isinstance(raw_evidence, Mapping):
        return None
    job = raw_evidence.get("job")
    if not isinstance(job, Mapping) or str(job.get("source_url") or "") != source_url:
        return None

    description = " ".join(str(job.get("description") or "").split())
    if not description:
        return None

    source_specific = raw_evidence.get("source_specific")
    structured_text = " ".join(flatten_source_text(source_specific)).strip()
    if structured_text:
        detail_text = structured_text
        if description not in detail_text:
            detail_text = f"{description} {detail_text}".strip()
    else:
        detail_text = description

    title = str(job.get("title") or row.get("title") or "").strip()
    return title, detail_text


__all__ = ["bound_observation_detail", "flatten_source_text"]
