from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import re
from typing import Any
import unicodedata

from src.search_intelligence.eon_requirement_inventory import description_lines


DIAGNOSTIC_SCHEMA = "eon_requirement_heading_diagnostic.v1"
_MAX_CANDIDATES = 24
_HEADING_HINT_RE = re.compile(
    r"\b(?:profile|qualification|authentic|open|bring|looking|benefit|role)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class UnicodeCharacterDiagnostic:
    index: int
    character: str
    codepoint: str
    name: str
    category: str

    def canonical_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HeadingCandidateDiagnostic:
    line_index: int
    text: str
    ascii_repr: str
    text_sha256: str
    non_ascii_characters: tuple[UnicodeCharacterDiagnostic, ...]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "line_index": self.line_index,
            "text": self.text,
            "ascii_repr": self.ascii_repr,
            "text_sha256": self.text_sha256,
            "non_ascii_characters": [
                item.canonical_payload() for item in self.non_ascii_characters
            ],
        }


def _non_ascii_characters(text: str) -> tuple[UnicodeCharacterDiagnostic, ...]:
    result: list[UnicodeCharacterDiagnostic] = []
    for index, character in enumerate(text):
        if ord(character) < 128:
            continue
        result.append(
            UnicodeCharacterDiagnostic(
                index=index,
                character=character,
                codepoint=f"U+{ord(character):04X}",
                name=unicodedata.name(character, "UNNAMED"),
                category=unicodedata.category(character),
            )
        )
    return tuple(result)


def _is_heading_candidate(text: str) -> bool:
    if _HEADING_HINT_RE.search(text) is not None:
        return True
    if len(text) > 120:
        return False
    if text.endswith((".", "!", "?", ";")):
        return False
    return any(unicodedata.category(character) == "Pd" for character in text)


def build_heading_diagnostics(description: object) -> tuple[HeadingCandidateDiagnostic, ...]:
    lines = description_lines(description)
    result: list[HeadingCandidateDiagnostic] = []
    for line_index, text in enumerate(lines):
        if not _is_heading_candidate(text):
            continue
        digest = sha256(text.encode("utf-8")).hexdigest()
        result.append(
            HeadingCandidateDiagnostic(
                line_index=line_index,
                text=text,
                ascii_repr=ascii(text),
                text_sha256=digest,
                non_ascii_characters=_non_ascii_characters(text),
            )
        )
        if len(result) >= _MAX_CANDIDATES:
            break
    return tuple(result)


def diagnostic_payload(description: object) -> dict[str, Any]:
    candidates = build_heading_diagnostics(description)
    return {
        "schema_version": DIAGNOSTIC_SCHEMA,
        "review_output_only_not_pipeline_input": True,
        "candidate_count": len(candidates),
        "candidates": [item.canonical_payload() for item in candidates],
        "boundaries": {
            "database_writes": 0,
            "candidate_fact_reads": 0,
            "candidate_fact_writes": 0,
            "capability_fit_decision_created": False,
            "assessment_mutation": False,
            "readiness_mutation": False,
            "network_requests": 0,
            "provider_requests": 0,
            "source_or_scheduler_activation": False,
            "application_action_performed": False,
        },
    }
