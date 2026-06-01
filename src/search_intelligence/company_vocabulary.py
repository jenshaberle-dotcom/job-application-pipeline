
"""Company vocabulary extraction for search-intelligence learning.

Company vocabulary observations are intentionally lighter than job records. They
capture terms seen around a company in exploration/market evidence so the system
can learn company-specific language without creating Bronze historical burden.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

TOKEN_RE = re.compile(r"[A-Za-zÄÖÜäöüß0-9+#.]+")

STOPWORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "im", "in", "mit", "of", "on", "the", "und", "with", "zu", "zur",
    "m", "w", "d", "mw", "mwd", "fmd", "all", "gender", "remote", "hybrid", "vollzeit", "teilzeit",
    "senior", "junior", "lead", "principal", "head", "chief", "expert", "professional", "specialist", "manager", "consultant",
    "engineer", "engineering", "developer", "entwickler", "entwicklerin", "ingenieur", "ingenieurin", "architekt", "architect",
    "job", "jobs", "stelle", "stellen", "karriere", "career", "team", "bereich", "berater", "beratung",
    "hannover", "hamburg", "berlin", "köln", "koeln", "munich", "münchen", "germany", "deutschland",
    "data", "daten", "software", "system", "systems", "business", "digital", "it", "technology", "technologie",
}

# Keep short but meaningful market vocabulary that a plain length rule would drop.
ALLOW_SHORT_TERMS = {"ai", "bi", "ml", "ki", "qa", "ux", "ui", "c#", "c++"}

# Terms that are too generic alone but meaningful in many current job titles when
# used as vocabulary hints. They are kept if explicitly present.
ALLOW_TERMS = {
    "analytics", "analytic", "analyse", "analysis", "platform", "plattform", "cloud", "azure", "aws", "gcp",
    "databricks", "python", "sql", "etl", "elt", "warehouse", "lakehouse", "pipeline", "pipelines", "streaming",
    "governance", "reporting", "intelligence", "agentic", "automation", "automatisierung", "integration",
    "risk", "versicherung", "insurance", "actuarial", "controlling", "retail", "banking", "finance",
}

SYNONYMS = {
    "analyse": "analytics",
    "analysis": "analytics",
    "analytic": "analytics",
    "plattform": "platform",
    "ki": "ai",
    "business-intelligence": "bi",
}


@dataclass(frozen=True)
class MarketEvidenceVocabularyInput:
    company_key: str
    company_name: str | None
    title: str
    source_name: str
    observed_at: str | None = None


@dataclass(frozen=True)
class CompanyVocabularyObservation:
    company_key: str
    company_name: str | None
    observed_term: str
    source_name: str
    evidence_type: str
    observation_count: int
    first_seen_at: str | None
    last_seen_at: str | None


def normalize_token(token: str) -> str:
    cleaned = token.strip().lower().replace("&", "and")
    cleaned = cleaned.strip(".,;:()[]{}<>|/\\")
    return SYNONYMS.get(cleaned, cleaned)


def extract_vocabulary_terms(text: str) -> tuple[str, ...]:
    """Extract lightweight vocabulary terms from a title or evidence snippet."""
    terms: list[str] = []
    for raw_token in TOKEN_RE.findall(text or ""):
        token = normalize_token(raw_token)
        if not token:
            continue
        if token in STOPWORDS:
            continue
        if len(token) < 3 and token not in ALLOW_SHORT_TERMS:
            continue
        if token in ALLOW_TERMS or token in ALLOW_SHORT_TERMS or len(token) >= 5:
            terms.append(token)

    # Preserve order while deduplicating within one title.
    seen: set[str] = set()
    unique_terms: list[str] = []
    for term in terms:
        if term not in seen:
            unique_terms.append(term)
            seen.add(term)
    return tuple(unique_terms)


def build_company_vocabulary_observations(
    rows: Iterable[MarketEvidenceVocabularyInput],
    *,
    evidence_type: str = "market_evidence_title",
) -> list[CompanyVocabularyObservation]:
    grouped: dict[tuple[str, str, str], Counter[str]] = {}
    company_names: dict[tuple[str, str, str], str | None] = {}
    first_seen: dict[tuple[str, str, str], str | None] = {}
    last_seen: dict[tuple[str, str, str], str | None] = {}

    for row in rows:
        for term in extract_vocabulary_terms(row.title):
            key = (row.company_key, term, row.source_name)
            if key not in grouped:
                grouped[key] = Counter()
                company_names[key] = row.company_name
                first_seen[key] = row.observed_at
                last_seen[key] = row.observed_at
            grouped[key][term] += 1
            if row.observed_at:
                if first_seen[key] is None or row.observed_at < str(first_seen[key]):
                    first_seen[key] = row.observed_at
                if last_seen[key] is None or row.observed_at > str(last_seen[key]):
                    last_seen[key] = row.observed_at

    observations: list[CompanyVocabularyObservation] = []
    for (company_key, term, source_name), counter in grouped.items():
        observations.append(
            CompanyVocabularyObservation(
                company_key=company_key,
                company_name=company_names[(company_key, term, source_name)],
                observed_term=term,
                source_name=source_name,
                evidence_type=evidence_type,
                observation_count=counter[term],
                first_seen_at=first_seen[(company_key, term, source_name)],
                last_seen_at=last_seen[(company_key, term, source_name)],
            )
        )

    return sorted(
        observations,
        key=lambda item: (item.company_key, -item.observation_count, item.observed_term, item.source_name),
    )
