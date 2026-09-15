"""Bounded operator-facing semantics for persisted vacancy evidence.

These helpers create no Candidate Fact, hard-filter, ranking, Top-5 or application
authority. They only preserve distinctions that are already observable in the
employer-origin vacancy.

External semantic tools may implement :class:`EvidenceObserver`, but JAP owns the
canonical verification and normalization contract. An observer can discover an
exact source span; it cannot establish Silver truth by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping, Protocol, Sequence


_FULL_TIME = frozenset({"fulltime", "full_time", "full-time", "full time"})
_PART_TIME = frozenset({"parttime", "part_time", "part-time", "part time"})

_DE_MARKERS = frozenset(
    {
        "und", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer",
        "mit", "für", "von", "im", "in", "auf", "wir", "sie", "ihre", "deine",
        "du", "uns", "unser", "suchen", "erfahrung", "kenntnisse", "aufgaben",
        "anforderungen", "verantwortung", "bewerbung", "arbeitszeit", "stelle",
    }
)
_EN_MARKERS = frozenset(
    {
        "and", "the", "a", "an", "with", "for", "from", "in", "on", "we", "you",
        "your", "our", "are", "will", "role", "skills", "experience", "requirements",
        "responsibilities", "application", "working", "hours", "position", "team",
    }
)
_TOKEN_RE = re.compile(r"[a-zA-ZäöüÄÖÜß]+")


@dataclass(frozen=True)
class ObservedFact:
    """One tool-neutral candidate observation bound to exact employer text."""

    field: str
    value: object
    evidence: str
    basis: str

    def canonical_payload(self) -> dict[str, object]:
        return {
            "field": self.field,
            "value": self.value,
            "evidence": self.evidence,
            "basis": self.basis,
        }


class EvidenceObserver(Protocol):
    """Optional evidence-discovery adapter with no Silver authority."""

    name: str

    def observe(self, text: str) -> Sequence[ObservedFact]: ...


def _normalized_employment_token(value: object) -> str:
    return " ".join(
        str(value or "").strip().casefold().replace("_", " ").replace("-", " ").split()
    )


def normalize_employment_scope(values: Iterable[object]) -> str:
    """Map structured employmentType-like values without inventing contract duration."""

    normalized = {_normalized_employment_token(value) for value in values}
    compact = {value.replace(" ", "") for value in normalized if value}
    full = bool(compact & {"fulltime"}) or bool(normalized & _FULL_TIME)
    part = bool(compact & {"parttime"}) or bool(normalized & _PART_TIME)
    if full and part:
        return "full_or_part_time"
    if full:
        return "full_time"
    if part:
        return "part_time"
    return "unknown"


def infer_posting_language(value: object) -> str:
    """Infer only the dominant DE/EN language of bounded vacancy text.

    This is presentation evidence, never an explicit language requirement. The
    detector is intentionally conservative and returns ``mixed`` or ``unknown``
    instead of forcing a language when the text is short or balanced.
    """

    text = str(value or "").strip()
    tokens = [token.casefold() for token in _TOKEN_RE.findall(text)]
    if len(tokens) < 12:
        return "unknown"

    de = sum(token in _DE_MARKERS for token in tokens)
    en = sum(token in _EN_MARKERS for token in tokens)
    if any(char in text.casefold() for char in ("ä", "ö", "ü", "ß")):
        de += 2

    strongest = max(de, en)
    weakest = min(de, en)
    if strongest < 3:
        return "unknown"
    if weakest >= 3 and weakest / strongest >= 0.55:
        return "mixed"
    if de >= en * 1.5:
        return "de"
    if en >= de * 1.5:
        return "en"
    return "mixed"


_HOURS_RANGE_RE = re.compile(
    r"\b(?P<min>\d{1,2}(?:[.,]\d+)?)\s*(?:-|–|—|bis|to)\s*"
    r"(?P<max>\d{1,2}(?:[.,]\d+)?)\s*(?:h|hours?|hrs?|stunden|wochenstunden)"
    r"(?:\s*(?:/|pro|per)?\s*(?:woche|week|weekly))?\b",
    re.IGNORECASE,
)
_HOURS_SINGLE_RE = re.compile(
    r"\b(?P<single>\d{1,2}(?:[.,]\d+)?)\s*(?:h|hours?|hrs?|stunden|wochenstunden)\s*"
    r"(?:/|pro|per)\s*(?:woche|week)\b",
    re.IGNORECASE,
)
_FULLTIME_HOURS_RE = re.compile(
    r"\b(?:vollzeit|full[- ]?time)\s*\(\s*(?P<single>\d{1,2}(?:[.,]\d+)?)\s*h\s*\)",
    re.IGNORECASE,
)
_EXPERIENCE_RANGE_RE = re.compile(
    r"\b(?P<min>\d{1,2})\s*(?:-|–|—|bis|to)\s*(?P<max>\d{1,2})\s*"
    r"(?:jahre|years?)\b(?P<context>.{0,80}?)(?:berufserfahrung|erfahrung|experience)\b",
    re.IGNORECASE,
)
_EXPERIENCE_SINGLE_RE = re.compile(
    r"\b(?P<single>\d{1,2})\s*(?:\+\s*)?(?:jahre|years?)\b"
    r"(?P<context>.{0,80}?)(?:berufserfahrung|erfahrung|experience)\b",
    re.IGNORECASE,
)
_PARTIAL_MOBILE_RE = re.compile(
    r"\b(?:anteilig(?:e|er|es|en)?\s+)?mobile(?:s|r|n|m)?\s+"
    r"arbeit(?:en)?(?:\s+ist)?\s+(?:möglich|possible)\b",
    re.IGNORECASE,
)
_TARIFF_RE = re.compile(r"\b(?:haus)?tarifvertrag\b|\bcollective\s+agreement\b", re.IGNORECASE)
_SALARY_RE = re.compile(
    r"(?P<prefix>\bab\s+|\bfrom\s+|\bstarting\s+(?:at|from)\s+)?"
    r"(?:(?P<currency_before>€|EUR|USD|\$)\s*)?"
    r"(?P<amount>\d{2,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d{4,6}(?:[.,]\d{1,2})?)"
    r"\s*(?P<currency_after>€|EUR|USD|\$)?"
    r"\s*(?:/|pro|per)?\s*(?P<period>jahr|year|annum|monat|month)\b",
    re.IGNORECASE,
)


def _decimal_number(value: str) -> float:
    normalized = value.replace(" ", "")
    if "." in normalized and "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "." in normalized:
        tail = normalized.rsplit(".", 1)[-1]
        if len(tail) == 3:
            normalized = normalized.replace(".", "")
    elif "," in normalized:
        tail = normalized.rsplit(",", 1)[-1]
        if len(tail) == 3:
            normalized = normalized.replace(",", "")
        else:
            normalized = normalized.replace(",", ".")
    return float(normalized)


def _hours_fact(match: re.Match[str]) -> ObservedFact | None:
    groups = match.groupdict()
    if groups.get("single") is not None:
        minimum = maximum = _decimal_number(groups["single"])
    else:
        minimum = _decimal_number(groups["min"])
        maximum = _decimal_number(groups["max"])
    if minimum <= 0 or maximum < minimum or maximum > 80:
        return None
    return ObservedFact(
        field="weekly_hours",
        value={"minimum": minimum, "maximum": maximum},
        evidence=match.group(0),
        basis="deterministic_visible_text",
    )


def _experience_fact(match: re.Match[str]) -> ObservedFact | None:
    groups = match.groupdict()
    if groups.get("single") is not None:
        minimum_years = maximum_years = float(groups["single"])
    else:
        minimum_years = float(groups["min"])
        maximum_years = float(groups["max"])
    if minimum_years <= 0 or maximum_years < minimum_years or maximum_years > 60:
        return None
    return ObservedFact(
        field="experience",
        value={
            "minimum_months": int(minimum_years * 12),
            "maximum_months": int(maximum_years * 12),
        },
        evidence=match.group(0),
        basis="deterministic_visible_text",
    )


def _salary_fact(match: re.Match[str]) -> ObservedFact | None:
    amount = _decimal_number(match.group("amount"))
    if amount <= 0:
        return None
    raw_currency = (match.group("currency_before") or match.group("currency_after") or "").upper()
    currency = "EUR" if raw_currency in {"€", "EUR"} else "USD" if raw_currency in {"$", "USD"} else ""
    if not currency:
        return None
    raw_period = match.group("period").casefold()
    period = "year" if raw_period in {"jahr", "year", "annum"} else "month"
    qualifier = "minimum" if (match.group("prefix") or "").strip() else "observed"
    return ObservedFact(
        field="compensation",
        value={
            "amount": amount,
            "currency": currency,
            "period": period,
            "qualifier": qualifier,
        },
        evidence=match.group(0),
        basis="deterministic_visible_text",
    )


class DeterministicVacancyObserver:
    """Built-in observer used as the verification baseline for optional tools."""

    name = "jap_deterministic_vacancy_observer_v1"

    def observe(self, text: str) -> tuple[ObservedFact, ...]:
        source = " ".join(str(text or "").split()).strip()
        if not source:
            return ()

        facts: list[ObservedFact] = []
        occupied_hours: set[tuple[int, int]] = set()
        for pattern in (_HOURS_RANGE_RE, _HOURS_SINGLE_RE, _FULLTIME_HOURS_RE):
            for match in pattern.finditer(source):
                span = (match.start(), match.end())
                if any(span[0] < end and span[1] > start for start, end in occupied_hours):
                    continue
                fact = _hours_fact(match)
                if fact is not None:
                    facts.append(fact)
                    occupied_hours.add(span)

        occupied_experience: set[tuple[int, int]] = set()
        for pattern in (_EXPERIENCE_RANGE_RE, _EXPERIENCE_SINGLE_RE):
            for match in pattern.finditer(source):
                span = (match.start(), match.end())
                if any(span[0] < end and span[1] > start for start, end in occupied_experience):
                    continue
                fact = _experience_fact(match)
                if fact is not None:
                    facts.append(fact)
                    occupied_experience.add(span)

        mobile = _PARTIAL_MOBILE_RE.search(source)
        if mobile is not None:
            facts.append(
                ObservedFact(
                    field="work_model",
                    value="hybrid",
                    evidence=mobile.group(0),
                    basis="deterministic_visible_text",
                )
            )

        tariff = _TARIFF_RE.search(source)
        if tariff is not None:
            facts.append(
                ObservedFact(
                    field="collective_agreement_context",
                    value=True,
                    evidence=tariff.group(0),
                    basis="deterministic_visible_text",
                )
            )

        for match in _SALARY_RE.finditer(source):
            fact = _salary_fact(match)
            if fact is not None:
                facts.append(fact)

        return tuple(facts)


def collect_observed_facts(
    text: object,
    *,
    optional_observers: Sequence[EvidenceObserver] = (),
) -> tuple[ObservedFact, ...]:
    """Run JAP verification plus optional discovery-only observers.

    Optional tools are additive. Their presence or absence never changes pipeline
    availability. Every returned fact must still point to an exact span in the
    bounded employer-origin text before downstream code may promote a value.
    """

    bounded_text = " ".join(str(text or "").split()).strip()
    observers: tuple[EvidenceObserver, ...] = (
        DeterministicVacancyObserver(),
        *tuple(optional_observers),
    )
    result: list[ObservedFact] = []
    seen: set[tuple[str, str, str]] = set()
    for observer in observers:
        for fact in observer.observe(bounded_text):
            if not fact.evidence or fact.evidence not in bounded_text:
                continue
            key = (fact.field, repr(fact.value), fact.evidence)
            if key in seen:
                continue
            seen.add(key)
            result.append(fact)
    return tuple(result)


def observed_facts_by_field(
    facts: Iterable[ObservedFact],
) -> Mapping[str, tuple[ObservedFact, ...]]:
    grouped: dict[str, list[ObservedFact]] = {}
    for fact in facts:
        grouped.setdefault(fact.field, []).append(fact)
    return {field: tuple(values) for field, values in grouped.items()}


__all__ = [
    "DeterministicVacancyObserver",
    "EvidenceObserver",
    "ObservedFact",
    "collect_observed_facts",
    "infer_posting_language",
    "normalize_employment_scope",
    "observed_facts_by_field",
]
