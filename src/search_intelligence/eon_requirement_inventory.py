from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any


INVENTORY_KEY = "EON-REQUIREMENT-INVENTORY-001"
REPORT_SCHEMA = "eon_requirement_inventory.v1"

_BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "section",
        "table",
        "tbody",
        "td",
        "th",
        "tr",
        "ul",
    }
)
_SPACE_RE = re.compile(r"\s+")
_BULLET_PREFIX_RE = re.compile(r"^(?:[•·▪◦*-]|\d+[.)])\s*")
_PROFILE_HEADING_RE = re.compile(
    r"^(?:your profile|your qualifications|qualifications|what you bring|"
    r"what we are looking for|what you are good at|profile)\s*:?(.*)$",
    re.IGNORECASE,
)
_END_HEADING_RE = re.compile(
    r"^(?:what we offer|what you can expect|our benefits|benefits|"
    r"do you have questions|about us|company|apply now|application|"
    r"inclusion|diversity|your benefits)\s*:?.*$",
    re.IGNORECASE,
)
_FLUENCY_RE = re.compile(
    r"\b(?:fluent|fluently|fluency|business[- ]fluent|very good|"
    r"verhandlungssicher|fließend)\b",
    re.IGNORECASE,
)
_EXPERIENCE_ANCHOR_PATTERNS = (
    re.compile(
        r"\b(?:several|multiple)\s+years(?:\s+of)?\s+"
        r"(?:relevant\s+|professional\s+|hands-on\s+)*experience\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bmany\s+years(?:\s+of)?\s+(?:professional\s+)?experience\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bmehrjährig\w*\s+(?:relevant\w*\s+|beruflich\w*\s+)*erfahrung\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bextensive\s+(?:relevant\s+)?professional\s+experience\b",
        re.IGNORECASE,
    ),
)

_FAMILY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "language",
        re.compile(r"\b(?:english|german|language|fluent|fluency)\b", re.IGNORECASE),
    ),
    (
        "education",
        re.compile(
            r"\b(?:degree|university|bachelor|master|phd|education|qualification)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "experience",
        re.compile(
            r"\b(?:experience|experienced|background|track record|years)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "technical_capability",
        re.compile(
            r"\b(?:data engineering|data platform|data pipeline|cloud|python|sql|"
            r"azure|aws|gcp|databricks|snowflake|spark|etl|architecture|"
            r"software|technology|technical|analytics|machine learning|ai)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "collaboration",
        re.compile(
            r"\b(?:stakeholders?|teams?|communication|consulting|collaborat\w*|"
            r"agile|leadership|customers?|business partners?)\b",
            re.IGNORECASE,
        ),
    ),
)


class _BlockTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag.casefold() in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


@dataclass(frozen=True)
class EonRequirementStatement:
    order: int
    statement_key: str
    family: str
    text: str
    normalized_text_sha256: str

    def canonical_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EonRequirementInventory:
    inventory_key: str
    section_heading: str
    description_sha256: str
    section_sha256: str
    statements: tuple[EonRequirementStatement, ...]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "inventory_key": self.inventory_key,
            "section_heading": self.section_heading,
            "description_sha256": self.description_sha256,
            "section_sha256": self.section_sha256,
            "statements": [statement.canonical_payload() for statement in self.statements],
        }

    def family_counts(self) -> dict[str, int]:
        counts = Counter(statement.family for statement in self.statements)
        return dict(sorted(counts.items()))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _normalize_line(value: str) -> str:
    text = _SPACE_RE.sub(" ", value).strip()
    text = _BULLET_PREFIX_RE.sub("", text).strip()
    return text


def description_lines(description: object) -> tuple[str, ...]:
    _require(
        isinstance(description, str) and bool(description.strip()),
        "stored E.ON description is missing",
    )
    parser = _BlockTextParser()
    parser.feed(description)
    parser.close()
    rendered = parser.text()

    result: list[str] = []
    for raw_line in rendered.splitlines():
        line = _normalize_line(raw_line)
        if not line:
            continue
        if result and result[-1].casefold() == line.casefold():
            continue
        result.append(line)
    _require(bool(result), "stored E.ON description produced no text blocks")
    return tuple(result)


def _profile_section(lines: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    start_index: int | None = None
    heading = ""
    first_statement = ""

    for index, line in enumerate(lines):
        match = _PROFILE_HEADING_RE.fullmatch(line)
        if match is None:
            continue
        start_index = index
        heading = line[: len(line) - len(match.group(1))].rstrip(" :")
        first_statement = _normalize_line(match.group(1))
        break

    _require(
        start_index is not None,
        "stored E.ON description has no recognized profile section",
    )

    statements: list[str] = []
    if first_statement:
        statements.append(first_statement)

    for line in lines[start_index + 1 :]:
        if _END_HEADING_RE.fullmatch(line) is not None:
            break
        if _PROFILE_HEADING_RE.fullmatch(line) is not None:
            continue
        statements.append(line)

    normalized: list[str] = []
    seen: set[str] = set()
    for statement in statements:
        text = _normalize_line(statement)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)

    _require(
        bool(normalized),
        "recognized E.ON profile section contains no requirement statements",
    )
    return heading or "Your Profile", tuple(normalized)


def _validate_profile_anchors(texts: tuple[str, ...]) -> None:
    has_language = any(
        "english" in text.casefold()
        and "german" in text.casefold()
        and _FLUENCY_RE.search(text) is not None
        for text in texts
    )
    _require(
        has_language,
        "E.ON profile section does not explicitly evidence fluent German and English",
    )

    has_experience = any(
        pattern.search(text) is not None
        for text in texts
        for pattern in _EXPERIENCE_ANCHOR_PATTERNS
    )
    _require(
        has_experience,
        "E.ON profile section does not explicitly evidence extensive professional experience",
    )


def classify_requirement_family(text: str) -> str:
    for family, pattern in _FAMILY_PATTERNS:
        if pattern.search(text) is not None:
            return family
    return "unclassified"


def _statement_key(text: str) -> tuple[str, str]:
    normalized = _SPACE_RE.sub(" ", text).strip().casefold()
    digest = sha256(normalized.encode("utf-8")).hexdigest()
    return f"eon-req-{digest[:16]}", digest


def build_eon_requirement_inventory(
    *,
    description: object,
    title: object,
) -> EonRequirementInventory:
    _require(
        isinstance(title, str) and bool(title.strip()),
        "stored E.ON title is missing",
    )
    _require(
        "(senior)" in title.casefold(),
        "bounded E.ON senior title marker is missing",
    )

    assert isinstance(description, str)
    lines = description_lines(description)
    heading, texts = _profile_section(lines)
    _validate_profile_anchors(texts)

    statements: list[EonRequirementStatement] = []
    statement_keys: set[str] = set()
    for order, text in enumerate(texts, start=1):
        key, digest = _statement_key(text)
        _require(key not in statement_keys, "E.ON requirement statement hash collision")
        statement_keys.add(key)
        statements.append(
            EonRequirementStatement(
                order=order,
                statement_key=key,
                family=classify_requirement_family(text),
                text=text,
                normalized_text_sha256=digest,
            )
        )

    language_count = sum(item.family == "language" for item in statements)
    experience_count = sum(item.family == "experience" for item in statements)
    _require(
        language_count >= 1,
        "E.ON profile section contains no classified language requirement",
    )
    _require(
        experience_count >= 1,
        "E.ON profile section contains no classified experience requirement",
    )

    section_material = "\n".join(
        f"{item.statement_key}|{item.family}|{item.text}" for item in statements
    )
    description_digest = sha256(description.encode("utf-8")).hexdigest()
    section_digest = sha256(section_material.encode("utf-8")).hexdigest()

    return EonRequirementInventory(
        inventory_key=INVENTORY_KEY,
        section_heading=heading,
        description_sha256=description_digest,
        section_sha256=section_digest,
        statements=tuple(statements),
    )
