"""Mass-company census primitives for Connector Factory experiments.

This module deliberately owns no network transport, database writes, source activation,
or scheduler authority. It converts large heterogeneous seed sets into deterministic
company candidates so the existing Employer-Origin pipeline can be stressed at scale.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import re
from urllib.parse import urlsplit, urlunsplit

SCHEMA_VERSION = "jap.connector_mass_census.v1"
_CLEAN = re.compile(r"[^a-z0-9]+")
_LEGAL = re.compile(
    r"\b(gmbh|ag|se|kg|ohg|ug|mbh|eg|e\.g\.|gbr|co|holding|gruppe|group)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class CompanySeed:
    company_name: str
    source: str
    website: str | None = None
    location: str | None = None
    industry: str | None = None
    source_record_id: str | None = None
    cohort: str = "TECH"


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def normalize_company_name(value: str) -> str:
    text = _LEGAL.sub(" ", _text(value).casefold())
    return " ".join(text.split())


def company_key(value: str) -> str:
    normalized = normalize_company_name(value)
    slug = _CLEAN.sub("-", normalized).strip("-")
    if not slug:
        raise ValueError("company_name_required")
    return slug[:96]


def canonical_website(value: str | None) -> str | None:
    if not value:
        return None
    raw = _text(value)
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.casefold().rstrip(".")
    if any(char.isspace() for char in host) or "." not in host:
        return None
    if host.startswith("www."):
        host = host[4:]
    return urlunsplit(("https", host, "", "", ""))


def _identity(seed: CompanySeed) -> tuple[str, str]:
    website = canonical_website(seed.website)
    if website:
        return ("domain", urlsplit(website).hostname or website)
    return ("name", normalize_company_name(seed.company_name))


def build_mass_census(
    seeds: list[CompanySeed],
    *,
    region: str = "Region Hannover",
    experiment_id: str = "hannover-tech-mass-census-v1",
) -> dict[str, object]:
    if not seeds:
        raise ValueError("company_seeds_required")
    grouped: dict[tuple[str, str], list[CompanySeed]] = {}
    rejected: list[dict[str, str]] = []
    for seed in seeds:
        if not _text(seed.company_name) or not _text(seed.source):
            rejected.append({"company_name": _text(seed.company_name), "reason": "name_or_source_missing"})
            continue
        grouped.setdefault(_identity(seed), []).append(seed)

    candidates: list[dict[str, object]] = []
    for identity, rows in sorted(grouped.items()):
        names = sorted({_text(row.company_name) for row in rows}, key=lambda x: (len(x), x.casefold()))
        primary = names[0]
        websites = sorted({v for row in rows if (v := canonical_website(row.website))})
        sources = sorted({_text(row.source) for row in rows})
        locations = sorted({_text(row.location) for row in rows if _text(row.location)})
        industries = sorted({_text(row.industry) for row in rows if _text(row.industry)})
        evidence_ids = sorted(
            {
                f"{_text(row.source)}:{_text(row.source_record_id) or hashlib.sha256(json.dumps(asdict(row), sort_keys=True).encode()).hexdigest()[:16]}"
                for row in rows
            }
        )
        cohorts = sorted({_text(row.cohort).upper() or "TECH" for row in rows})
        if len(cohorts) != 1:
            raise ValueError("company_identity_cross_cohort_collision")
        base_key = company_key(primary)
        stable_key = base_key if identity[0] == "name" else f"{base_key}-{hashlib.sha256(identity[1].encode()).hexdigest()[:8]}"
        candidates.append(
            {
                "company_key": stable_key,
                "company_name": primary,
                "cohort": cohorts[0],
                "aliases": names[1:],
                "websites": websites,
                "locations": locations,
                "industries": industries,
                "seed_sources": sources,
                "discovery_evidence_ids": evidence_ids,
                "candidate_origin": "MASS_CENSUS_EXPERIMENT",
                "disposition": "ORIGIN_DISCOVERY_REQUIRED",
            }
        )

    source_counts = Counter(_text(seed.source) for seed in seeds if _text(seed.source))
    canonical = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "region": region,
        "summary": {
            "raw_seed_count": len(seeds),
            "accepted_seed_count": sum(len(rows) for rows in grouped.values()),
            "rejected_seed_count": len(rejected),
            "unique_company_count": len(candidates),
            "duplicate_seed_count": sum(len(rows) - 1 for rows in grouped.values()),
            "candidate_population_authority": "mass_census_experiment_by_domain_then_normalized_name",
            "source_counts": dict(sorted(source_counts.items())),
        },
        "boundaries": {
            "experiment_only": True,
            "market_sensors_excluded_from_employer_source_authority": True,
            "production_source_activation": False,
            "recurring_scheduling": False,
            "database_writes": False,
            "provider_calls": 0,
            "application_actions": 0,
        },
        "rejected": rejected,
        "candidates": candidates,
    }
    canonical["population_digest"] = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return canonical


def seeds_from_payload(payload: object, *, default_source: str) -> list[CompanySeed]:
    if isinstance(payload, dict):
        payload = payload.get("companies", payload.get("candidates"))
    if not isinstance(payload, list):
        raise TypeError("company_seed_list_required")
    result = []
    for row in payload:
        if isinstance(row, str):
            result.append(CompanySeed(company_name=row, source=default_source))
            continue
        if not isinstance(row, dict):
            raise TypeError("company_seed_item_invalid")
        result.append(
            CompanySeed(
                company_name=_text(row.get("company_name") or row.get("name")),
                source=_text(row.get("source")) or default_source,
                website=_text(row.get("website") or row.get("url")) or None,
                location=_text(row.get("location") or row.get("city")) or None,
                industry=_text(row.get("industry") or row.get("sector")) or None,
                source_record_id=_text(row.get("source_record_id") or row.get("id")) or None,
                cohort=(_text(row.get("cohort")) or "TECH").upper(),
            )
        )
    return result
