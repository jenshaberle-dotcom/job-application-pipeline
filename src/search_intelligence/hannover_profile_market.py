"""Profile-aware Hannover employer universe and target-role signals.

The original TECH Census remains the fixed benchmark. Employer additions are
unverified public-directory seeds until independent identity/portal evidence
has been acquired. A company's industry is not evidence of a suitable job.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from copy import deepcopy
from urllib.parse import urlsplit

PROFILE_SCHEMA = "jap.hannover_profile_employer_seeds.v1"
ROLE_SCHEMA = "jap.market_target_role_families.v1"

PROFILE_TARGETS: dict[str, tuple[str, ...]] = {
    "solution_architecture": (
        "Solution Architect",
        "Solutions Architect",
        "Lösungsarchitekt",
        "IT-Lösungsarchitekt",
        "IT Solution Architect",
        "AI Solution Architect",
        "Cloud Solution Architect",
        "Integration Architect",
        "IT-Architekt",
        "Anwendungsarchitekt",
        "Softwarearchitekt",
        "Enterprise Architect",
        "Technical Architect",
    ),
    "data_engineering": (
        "Data Engineer", "Analytics Engineer", "Data Platform Engineer",
        "Data Warehouse Engineer", "ETL Developer",
    ),
    "product_ownership": ("Product Owner", "Technical Product Owner", "Productowner"),
    "systems_engineering": (
        "System Engineer", "Systems Engineer", "Systemingenieur",
        "IT System Engineer", "IT-Systemingenieur",
    ),
    "ai_engineering": (
        "AI Engineer", "KI-Entwickler", "ML Engineer",
        "MLOps Engineer", "AI Platform Engineer",
    ),
}

# The list is descriptive, not a restriction on what may be discovered.
PROFILE_MARKET_SECTORS = (
    "ICT", "FINANCE_INSURANCE", "ENERGY", "AUTOMOTIVE", "ENGINEERING",
    "LOGISTICS", "HEALTH", "PUBLIC_ADMINISTRATION", "PUBLIC_IT",
    "SCIENCE_RESEARCH", "RETAIL_ECOMMERCE", "CONSULTING",
    "INDUSTRIAL", "CREATIVE_DIGITAL", "TRAVEL_TOURISM", "OTHER",
)

ROLE_PATTERNS = {
    "solution_architecture": (
        r"\bsolutions?\s+architect\b",
        r"\b(?:it\s+)?(?:losungsarchitekt|loesungsarchitekt)(?:in)?\b",
        r"\b(?:it|ai|ki|cloud|integration|anwendungs|software|enterprise|technical)"
        r"\s*architekt(?:in)?\b",
        r"\b(?:cloud|integration|enterprise|technical)\s+architect\b",
    ),
    "data_engineering": (
        r"\b(?:data|analytics|data\s+platform|data\s+warehouse)\s+engineer\b",
        r"\betl\s+(?:developer|entwickler|engineer)\b",
    ),
    "product_ownership": (r"\b(?:technical\s+)?product\s*owner\b",),
    "systems_engineering": (
        r"\bsystems?\s+engineer\b",
        r"\b(?:it\s+)?systemingenieur\b",
    ),
    "ai_engineering": (
        r"\b(?:ai|ki|ml|machine\s+learning|mlops|ai\s+platform)\s+engineer\b",
        r"\bki\s+entwickler\b",
    ),
}


def folded(value: object) -> str:
    raw = str(value or "").casefold()
    transliterated = unicodedata.normalize("NFKD", raw)
    raw = "".join(char for char in transliterated
                  if not unicodedata.combining(char))
    raw = raw.replace("ß", "ss")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", raw)).strip()


def title_role_families(title: str) -> tuple[str, ...]:
    """Title-only acquisition signal; not a proven candidate/job fit decision."""
    text = folded(title)
    if not text:
        return ()
    return tuple(family for family, patterns in ROLE_PATTERNS.items()
                 if any(re.search(pattern, text) for pattern in patterns))


def _name_key(value: str) -> str:
    text = folded(value)
    return re.sub(
        r"\b(gmbh|mbh|ag|se|kg|co|ug|gbr|kgaa|gruppe|group|holding)\b", "",
        text,
    ).replace(" ", "")


def _public_url(value: object) -> str:
    if not isinstance(value, str):
        return ""
    try:
        parsed = urlsplit(value.strip())
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password
                or parsed.port not in (None, 443)):
            return ""
    except ValueError:
        return ""
    return parsed.geturl().rstrip("/")


def expand_hannover_market(
    baseline_tech: list[dict], expansion: dict
) -> tuple[list[dict], dict]:
    """Merge provenance-bearing, REGION_HANNOVER-only seeds into a second cohort.

    Exact normalized name or declared alias is the only automatic identity
    reconciliation. A shared corporate domain alone is not sufficient:
    subsidiaries can share an ATS/site without being the same legal employer.
    """
    if not isinstance(expansion, dict) or expansion.get("schema_version") != PROFILE_SCHEMA:
        raise ValueError("profile_market_seed_schema_invalid")
    if not isinstance(expansion.get("companies"), list):
        raise ValueError("profile_market_company_list_required")

    result: list[dict] = []
    by_name: dict[str, dict] = {}
    for raw in baseline_tech:
        row = deepcopy(raw)
        row["poc_population_segment"] = "TECH_BASELINE"
        row["poc_source_records"] = []
        row["poc_sector_labels"] = sorted(set(
            str(v).upper() for v in row.get("industries", []) if str(v).strip()
        ))
        result.append(row)
        aliases = [row["company_name"]] + list(row.get("aliases") or [])
        for name in aliases:
            norm = _name_key(str(name))
            if norm:
                prior = by_name.get(norm)
                if prior is not None and prior is not row:
                    # Some directories include overlapping alias labels; do not
                    # automatically join distinct employers based on ambiguity.
                    continue
                by_name[norm] = row

    additions = 0
    overlapping = 0
    source_names: Counter[str] = Counter()
    source_sectors: Counter[str] = Counter()
    seen_source_rows: set[tuple[str, str]] = set()
    for raw in expansion["companies"]:
        if not isinstance(raw, dict):
            raise ValueError("profile_market_company_entry_invalid")
        name = str(raw.get("company_name") or "").strip()
        geography = str(raw.get("geography") or "").strip().upper()
        sector = str(raw.get("sector") or "").strip().upper()
        source_name = str(raw.get("source_name") or "").strip()
        source_url = _public_url(raw.get("source_url"))
        company_site = _public_url(raw.get("website"))
        key = _name_key(name)
        if (not name or len(key) < 3 or geography != "REGION_HANNOVER"
                or sector not in PROFILE_MARKET_SECTORS
                or not source_name or not source_url):
            raise ValueError("profile_market_seed_identity_geography_or_lineage_invalid")

        marker = (key, source_url)
        if marker in seen_source_rows:
            raise ValueError("duplicate_profile_market_seed_evidence")
        seen_source_rows.add(marker)
        source_names[source_name] += 1
        source_sectors[sector] += 1
        existing = by_name.get(key)
        evidence = {
            "source_name": source_name, "source_url": source_url,
            "sector": sector, "company_name": name,
            "website_candidate": company_site or None,
            "authority": "UNVERIFIED_DIRECTORY_SEED",
        }
        if existing is not None:
            overlapping += 1
            existing["poc_source_records"].append(evidence)
            existing["poc_sector_labels"] = sorted(
                set(existing["poc_sector_labels"]) | {sector}
            )
            # Do not silently override the original Census corporate website.
            continue

        identity = "profile-" + hashlib.sha256(key.encode()).hexdigest()[:14]
        new_record = {
            "company_key": identity,
            "company_name": name,
            "cohorts": ["PROFILE_MARKET"],
            "geographies": ["REGION_HANNOVER"],
            "scope_memberships": [
                {"geography": "REGION_HANNOVER", "cohort": "PROFILE_MARKET"},
            ],
            "websites": [company_site] if company_site else [],
            "aliases": [],
            "industries": [sector],
            "seed_sources": [source_name],
            "poc_population_segment": "PROFILE_MARKET_ADDITION",
            "poc_source_records": [evidence],
            "poc_sector_labels": [sector],
            "poc_role_fit_status": "NOT_ASSESSED_UNTIL_JOB_EVIDENCE",
        }
        by_name[key] = new_record
        result.append(new_record)
        additions += 1

    result.sort(key=lambda item: str(item["company_key"]))
    return result, {
        "schema_version": PROFILE_SCHEMA,
        "tech_baseline": len(baseline_tech),
        "new_profile_market_candidates": additions,
        "overlapping_source_records": overlapping,
        "expanded_total": len(result),
        "source_row_count": len(seen_source_rows),
        "source_rows_by_name": dict(sorted(source_names.items())),
        "source_rows_by_sector": dict(sorted(source_sectors.items())),
        "denominator_is_full_region_employer_census": False,
        "target_role_families": {
            family: list(terms) for family, terms in PROFILE_TARGETS.items()
        },
        "target_role_family_schema": ROLE_SCHEMA,
    }
