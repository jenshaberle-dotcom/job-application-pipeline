"""Deterministic same-detail grounding helpers for Detail Semantics.

Provider/model output remains hypothesis-only. Exact evidence substrings are located
inside the already-bounded detail text here, and ambiguous repeated substrings fail
closed instead of asking the model to calculate Python character offsets.
"""

from __future__ import annotations


def locate_unique_evidence_span(*, detail_text: str, evidence: str) -> tuple[int, int]:
    """Return the unique exact span for evidence in detail_text or fail closed."""

    if not evidence:
        raise ValueError("semantic evidence must be non-empty")

    start = detail_text.find(evidence)
    if start < 0:
        raise ValueError("semantic evidence does not occur in bounded detail text")

    if detail_text.find(evidence, start + 1) >= 0:
        raise ValueError("semantic evidence is ambiguous in bounded detail text")

    return start, start + len(evidence)


__all__ = ["locate_unique_evidence_span"]
