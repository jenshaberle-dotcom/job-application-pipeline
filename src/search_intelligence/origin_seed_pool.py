"""Seed classification for origin observation and URL-discovery learning.

This module deliberately separates seed *roles* from pipeline decisions.
Company-name seeds may guide bounded URL discovery. URL seeds may guide
observation. Text-signal seeds may guide later vocabulary learning. None of
these seeds pass gates, activate sources or write Bronze/Silver data.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping
from urllib.parse import urlparse

SEED_POOL_BOUNDARY = {
    "learning_input_only": True,
    "no_gate_decision": True,
    "no_candidate_status_mutation": True,
    "no_connector_artifact_generation": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_bronze_write": True,
    "no_silver_write": True,
    "no_scheduler_change": True,
    "no_csv_or_export_input": True,
    "company_name_seed_requires_url_discovery": True,
    "aggregator_seeds_not_origin_structure_evidence": True,
}

AGGREGATOR_SOURCE_NAMES = {"stepstone", "indeed", "linkedin", "xing", "glassdoor"}
PUBLIC_TEXT_SIGNAL_SOURCE_NAMES = {"bundesagentur_fuer_arbeit", "ba"}
ATS_SOURCE_PREFIXES = ("greenhouse:", "personio:", "workday:", "successfactors:")
HISTORICAL_OR_UNDIFFERENTIATED_PREFIXES = ("greenhouse:stripe",)


@dataclass(frozen=True)
class ObservationSeed:
    seed_key: str
    seed_type: str
    seed_source_table: str
    observation_role: str
    priority_score: float
    prior_reason: str
    company_key: str | None = None
    company_name: str | None = None
    source_name: str | None = None
    source_family: str | None = None
    seed_url: str | None = None
    url_allowed_for_observation: bool = False
    evidence: Mapping[str, object] | None = None


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_company_key(value: object) -> str:
    normalized = normalize_text(value)
    normalized = normalized.replace("&", " und ")
    normalized = re.sub(r"\b(gmbh|ag|se|kg|co|kgaa|mbh|inc|ltd|group|gruppe)\b", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def canonical_seed_url(url: object) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}{query}"


def _source_name(row: Mapping[str, object]) -> str:
    return normalize_text(row.get("source_name") or row.get("source_name_candidate") or row.get("source_family_candidate"))


def _has_url(row: Mapping[str, object]) -> bool:
    return canonical_seed_url(row.get("seed_url") or row.get("candidate_url") or row.get("source_url") or row.get("evidence_url")) is not None


def _company_key(row: Mapping[str, object]) -> str | None:
    value = row.get("company_key") or row.get("normalized_company_key") or row.get("source_family_candidate")
    if value:
        return normalize_company_key(value)
    name = row.get("company_name") or row.get("display_company_name")
    return normalize_company_key(name) if name else None


def _company_name(row: Mapping[str, object]) -> str | None:
    value = row.get("company_name") or row.get("display_company_name") or row.get("company_key")
    return str(value).strip() if value else None


def classify_seed_row(row: Mapping[str, object]) -> ObservationSeed:
    """Classify one DB row into a seed role with explicit boundaries."""

    source_table = str(row.get("seed_source_table") or row.get("source_table") or "unknown")
    source_name_raw = str(row.get("source_name") or row.get("source_name_candidate") or "").strip()
    source_name = _source_name(row)
    company_key = _company_key(row)
    company_name = _company_name(row)
    source_family = str(row.get("source_family_candidate") or company_key or "").strip() or None
    seed_url = canonical_seed_url(row.get("seed_url") or row.get("candidate_url") or row.get("source_url") or row.get("evidence_url"))

    if source_table in {"candidate_expansion_review_items", "candidate_promotion_review_items"} and not seed_url:
        seed_type = "company_name_only_seed"
        role = "url_discovery_input"
        priority = 0.68
        allowed = False
        reason = "search-intelligence seeded company should feed bounded URL discovery before observation"
    elif source_name in AGGREGATOR_SOURCE_NAMES or source_table.startswith("aggregator_"):
        seed_type = "aggregator_company_seed"
        role = "company_discovery_only"
        priority = 0.48
        allowed = False
        reason = "aggregator signal can prioritize company-name discovery but must not train origin URL structure"
    elif source_name in PUBLIC_TEXT_SIGNAL_SOURCE_NAMES:
        seed_type = "job_text_signal_seed"
        role = "text_signal_learning"
        priority = 0.55
        allowed = False
        reason = "public job API/text source may enrich signal vocabulary but is not employer-origin URL structure"
    elif source_name.startswith(ATS_SOURCE_PREFIXES):
        seed_type = "ats_structure_seed"
        role = "ats_structure_learning"
        priority = 0.62 if not source_name.startswith(HISTORICAL_OR_UNDIFFERENTIATED_PREFIXES) else 0.35
        allowed = bool(seed_url)
        reason = "known ATS/provider source may contribute bounded structure observations"
    elif seed_url and source_table in {
        "employer_origin_source_candidates",
        "employer_origin_job_detail_evidence",
        "candidate_promotion_review_items",
        "connector_feasibility_review_items",
        "market_evidence",
        "silver_jobs",
    }:
        seed_type = "origin_url_seed"
        role = "origin_url_observation"
        priority = 0.80
        allowed = True
        reason = "existing employer-origin or evidence URL can be observed as learning input"
    elif company_key or company_name:
        seed_type = "company_name_only_seed"
        role = "url_discovery_input"
        priority = 0.68 if source_table in {"candidate_expansion_review_items", "candidate_promotion_review_items", "aggregator_novelty_items", "market_evidence"} else 0.50
        allowed = False
        reason = "company name is search-intelligence seeded and should feed bounded URL discovery before observation"
    else:
        seed_type = "unknown_seed"
        role = "diagnostics_only"
        priority = 0.10
        allowed = False
        reason = "seed row lacks enough information for observation or URL discovery"

    if source_name.startswith(HISTORICAL_OR_UNDIFFERENTIATED_PREFIXES):
        priority = min(priority, 0.35)
        reason += "; historical undifferentiated source is low-priority learning input"

    seed_key_parts = [seed_type, company_key or normalize_company_key(company_name), seed_url or source_name or source_table]
    seed_key = "|".join(part for part in seed_key_parts if part)

    return ObservationSeed(
        seed_key=seed_key,
        seed_type=seed_type,
        seed_source_table=source_table,
        observation_role=role,
        priority_score=round(priority, 4),
        prior_reason=reason,
        company_key=company_key,
        company_name=company_name,
        source_name=source_name_raw or None,
        source_family=source_family,
        seed_url=seed_url,
        url_allowed_for_observation=allowed,
        evidence={
            "boundary": SEED_POOL_BOUNDARY,
            "source_name": source_name_raw,
            "source_table": source_table,
            "has_url": bool(seed_url),
        },
    )


def deduplicate_seeds(seeds: Iterable[ObservationSeed]) -> list[ObservationSeed]:
    by_key: dict[str, ObservationSeed] = {}
    for seed in seeds:
        existing = by_key.get(seed.seed_key)
        if existing is None or seed.priority_score > existing.priority_score:
            by_key[seed.seed_key] = seed
    return sorted(by_key.values(), key=lambda item: (-item.priority_score, item.seed_type, item.company_key or "", item.seed_url or ""))


def observation_url_seeds(seeds: Iterable[ObservationSeed]) -> list[ObservationSeed]:
    return [seed for seed in seeds if seed.url_allowed_for_observation and seed.seed_url]


def seed_type_counts(seeds: Iterable[ObservationSeed]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for seed in seeds:
        counts[seed.seed_type] = counts.get(seed.seed_type, 0) + 1
    return dict(sorted(counts.items()))


def observation_role_counts(seeds: Iterable[ObservationSeed]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for seed in seeds:
        counts[seed.observation_role] = counts.get(seed.observation_role, 0) + 1
    return dict(sorted(counts.items()))


def generate_company_url_candidates(company_key: str, company_name: str | None = None, *, promoted_path_patterns: Iterable[str] = ()) -> tuple[str, ...]:
    """Generate bounded URL-discovery candidates from a company seed.

    These are candidates for the URL finder, not observation evidence and not
    gate evidence. Callers must validate reachability and employer-origin fit.
    """

    key = normalize_company_key(company_key or company_name)
    if not key:
        return ()
    compact = key.replace("_", "")
    dashed = key.replace("_", "-")
    bases = (
        f"https://jobs.{dashed}.de/",
        f"https://jobs.{dashed}.com/",
        f"https://karriere.{dashed}.de/",
        f"https://careers.{dashed}.com/",
        f"https://www.{dashed}.de/karriere",
        f"https://www.{dashed}.de/jobs",
    )
    pattern_paths: list[str] = []
    for pattern in promoted_path_patterns:
        value = normalize_text(pattern)
        if value in {"/job/...", "/jobs/...", "/search/...", "/stellen/..."}:
            pattern_paths.append(value.replace("...", "").rstrip("/") or "/")
    urls: list[str] = []
    for base in bases:
        urls.append(base)
        for path in pattern_paths[:3]:
            urls.append(base.rstrip("/") + path)
    if compact != dashed:
        urls.append(f"https://jobs.{compact}.de/")
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        canonical = canonical_seed_url(url)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        unique.append(canonical)
    return tuple(unique)
