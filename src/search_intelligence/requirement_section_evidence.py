"""Provider-neutral extraction of bounded requirement sections from job-detail HTML.

The extractor deliberately owns no skill taxonomy and no Product authority. It
only narrows already-fetched employer-origin HTML to visible requirement-bearing
sections such as ``Profil``, ``Qualifikationen`` or ``Requirements``. This keeps
navigation, cookie chrome, benefits and unrelated page text out of downstream
semantic observers while preserving the exact visible text that those observers
may inspect.

No raw HTML is returned or persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import re
from typing import Iterable


REQUIREMENT_SECTION_SCHEMA = "generic_requirement_section_evidence.v1"
MAX_REQUIREMENT_SECTION_CHARS = 16_000
_BLOCK_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "dt", "dd"})
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_IGNORED_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "nav",
        "footer",
        "header",
        "aside",
        "form",
        "button",
        "svg",
        "canvas",
    }
)

_REQUIREMENT_HEADING_PHRASES = (
    "profil",
    "dein profil",
    "ihr profil",
    "deine qualifikationen",
    "ihre qualifikationen",
    "qualifikationen",
    "anforderungen",
    "unsere anforderungen",
    "deine kenntnisse",
    "ihre kenntnisse",
    "kenntnisse",
    "kompetenzen",
    "deine kompetenzen",
    "ihre kompetenzen",
    "das bringst du mit",
    "was du mitbringst",
    "was sie mitbringen",
    "das zeichnet dich aus",
    "das zeichnet sie aus",
    "damit überzeugst du",
    "damit überzeugen sie",
    "wen wir suchen",
    "requirements",
    "qualifications",
    "your profile",
    "your qualifications",
    "what you bring",
    "what you'll bring",
    "what you will bring",
    "what we are looking for",
    "what we're looking for",
    "who we are looking for",
    "skills and experience",
    "skills & experience",
    "required skills",
    "required qualifications",
    "experience and qualifications",
)

_STOP_HEADING_PHRASES = (
    "aufgaben",
    "deine aufgaben",
    "ihre aufgaben",
    "was dich erwartet",
    "was sie erwartet",
    "deine rolle",
    "ihre rolle",
    "responsibilities",
    "your responsibilities",
    "what you will do",
    "what you'll do",
    "the role",
    "wir bieten",
    "was wir bieten",
    "das bieten wir",
    "deine benefits",
    "ihre benefits",
    "benefits",
    "our benefits",
    "what we offer",
    "warum wir",
    "why us",
    "über uns",
    "about us",
    "klingt interessant",
    "jetzt bewerben",
    "apply now",
    "kontakt",
    "contact",
)

_SPACE_RE = re.compile(r"\s+")
_EDGE_PUNCT_RE = re.compile(r"^[\s:;\-–—|•·]+|[\s:;\-–—|•·]+$")


@dataclass(frozen=True)
class RequirementSection:
    heading: str
    text: str
    block_count: int

    def canonical_payload(self) -> dict[str, object]:
        return {
            "heading": self.heading,
            "text": self.text,
            "block_count": self.block_count,
        }


@dataclass(frozen=True)
class RequirementSectionEvidence:
    sections: tuple[RequirementSection, ...]
    text: str
    truncated: bool

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema": REQUIREMENT_SECTION_SCHEMA,
            "sections": [section.canonical_payload() for section in self.sections],
            "text": self.text,
            "truncated": self.truncated,
            "raw_html_persisted": False,
        }


@dataclass(frozen=True)
class _Block:
    tag: str
    text: str


class _VisibleBlockParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[_Block] = []
        self._ignored_depth = 0
        self._active_tag: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        normalized = tag.casefold()
        if normalized in _IGNORED_TAGS:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if normalized in _BLOCK_TAGS:
            self._flush()
            self._active_tag = normalized
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized in _IGNORED_TAGS:
            if self._ignored_depth:
                self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return
        if self._active_tag == normalized:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and self._active_tag is not None:
            self._parts.append(data)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        if self._active_tag is None:
            return
        text = _normalize_text(" ".join(self._parts))
        if text:
            self.blocks.append(_Block(self._active_tag, text))
        self._active_tag = None
        self._parts = []


def _normalize_text(value: object) -> str:
    return _SPACE_RE.sub(" ", unescape(str(value or ""))).strip()


def _heading_key(value: object) -> str:
    normalized = _normalize_text(value).casefold()
    normalized = _EDGE_PUNCT_RE.sub("", normalized)
    return normalized.rstrip("?!.").strip()


def _matches_heading(value: str, phrases: Iterable[str]) -> bool:
    key = _heading_key(value)
    if not key:
        return False
    return any(key == phrase or key.startswith(phrase + " ") for phrase in phrases)


def _is_requirement_heading(block: _Block) -> bool:
    if block.tag not in _HEADING_TAGS and len(block.text) > 100:
        return False
    return _matches_heading(block.text, _REQUIREMENT_HEADING_PHRASES)


def _is_stop_heading(block: _Block) -> bool:
    if block.tag in _HEADING_TAGS:
        return not _is_requirement_heading(block)
    if len(block.text) > 100:
        return False
    return _matches_heading(block.text, _STOP_HEADING_PHRASES)


def _bounded_join(parts: Iterable[str], limit: int) -> tuple[str, bool]:
    result: list[str] = []
    used = 0
    truncated = False
    for raw in parts:
        text = _normalize_text(raw)
        if not text:
            continue
        separator = 1 if result else 0
        remaining = limit - used - separator
        if remaining <= 0:
            truncated = True
            break
        if len(text) > remaining:
            clipped = text[:remaining].rsplit(" ", 1)[0].strip() or text[:remaining]
            if clipped:
                result.append(clipped)
                used += separator + len(clipped)
            truncated = True
            break
        result.append(text)
        used += separator + len(text)
    return "\n".join(result), truncated


def extract_requirement_section_evidence(
    html: str,
    *,
    max_chars: int = MAX_REQUIREMENT_SECTION_CHARS,
) -> RequirementSectionEvidence:
    """Return bounded visible requirement sections from one already-fetched page."""

    parser = _VisibleBlockParser()
    try:
        parser.feed(str(html or ""))
        parser.close()
    except Exception:
        return RequirementSectionEvidence(sections=(), text="", truncated=False)

    sections: list[RequirementSection] = []
    active_heading: str | None = None
    active_parts: list[str] = []

    def finish() -> None:
        nonlocal active_heading, active_parts
        if active_heading is None:
            return
        section_text, _ = _bounded_join(active_parts, max_chars)
        if section_text:
            sections.append(
                RequirementSection(
                    heading=active_heading,
                    text=section_text,
                    block_count=len(active_parts),
                )
            )
        active_heading = None
        active_parts = []

    for block in parser.blocks:
        if _is_requirement_heading(block):
            finish()
            active_heading = block.text
            continue
        if active_heading is None:
            continue
        if _is_stop_heading(block):
            finish()
            continue
        if block.tag in _HEADING_TAGS:
            finish()
            continue
        active_parts.append(block.text)
    finish()

    combined, truncated = _bounded_join(
        (section.text for section in sections),
        max_chars,
    )
    return RequirementSectionEvidence(
        sections=tuple(sections),
        text=combined,
        truncated=truncated,
    )


__all__ = [
    "MAX_REQUIREMENT_SECTION_CHARS",
    "REQUIREMENT_SECTION_SCHEMA",
    "RequirementSection",
    "RequirementSectionEvidence",
    "extract_requirement_section_evidence",
]
