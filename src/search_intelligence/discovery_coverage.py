"""Evaluate discovery coverage before expensive Factory work."""

from __future__ import annotations
from collections import Counter
import re

EXPECTED = {"REGION_HANNOVER", "WOLFSBURG", "INGOLSTADT", "STUTTGART_REGION", "BERLIN", "MUNICH"}
MINIMUM = {
    "REGION_HANNOVER": 250,
    "WOLFSBURG": 50,
    "INGOLSTADT": 50,
    "STUTTGART_REGION": 100,
    "BERLIN": 250,
    "MUNICH": 250,
}


def assess(census: dict[str, object]) -> dict[str, object]:
    counts = Counter()
    cohort_counts = Counter()
    scoped_counts = Counter()
    source_counts = Counter()
    exclusive_counts = Counter()
    identity_errors = Counter()
    evidence_owners: dict[str, set[int]] = {}
    candidates = census.get("candidates", [])
    for index, row in enumerate(candidates):
        name = row.get("company_name")
        if not isinstance(name, str) or not name.strip():
            identity_errors["missing_company_name"] += 1
        elif name.strip().casefold() in {
            "homepage", "name", "anschrift", "berufsfeld(er)", "beschreibung", "mitarbeitende",
        }:
            identity_errors["navigation_label_as_company_name"] += 1
        elif re.match(r"(?i)(?:https?://|www\.)", name.strip()):
            identity_errors["url_as_company_name"] += 1
        for evidence_id in set(row.get("discovery_evidence_ids", [])):
            evidence_owners.setdefault(evidence_id, set()).add(index)
        for geography in row.get("geographies", []):
            counts[str(geography)] += 1
        for cohort in row.get("cohorts", []):
            cohort_counts[str(cohort)] += 1
        memberships = row.get("scope_memberships")
        if memberships is None:
            memberships = [
                {"geography": g, "cohort": c}
                for g in row.get("geographies", [])
                for c in row.get("cohorts", [])
                if c != "SOCIAL" or g == "REGION_HANNOVER"
            ]
        for item in memberships:
            scoped_counts[(item["geography"], item["cohort"])] += 1
        sources = set(row.get("seed_sources", []))
        source_counts.update(sources)
        if len(sources) == 1:
            exclusive_counts.update(sources)
    gaps = {}
    for geography in sorted(EXPECTED):
        actual = scoped_counts[(geography, "TECH")]
        minimum = MINIMUM[geography]
        if actual < minimum:
            gaps[geography] = {
                "actual": actual,
                "minimum": minimum,
                "additional_sources_required": True,
            }
    collisions = sum(len(owners) > 1 for owners in evidence_owners.values())
    if collisions:
        identity_errors["discovery_evidence_id_collision"] = collisions
    identities_valid = not identity_errors
    return {
        "status": ("SOURCE_IDENTITY_INVALID" if not identities_valid else
                   "PASS" if not gaps else "SOURCE_COVERAGE_GAP"),
        "identity_errors": dict(sorted(identity_errors.items())),
        "counts_are_unvalidated_observations": not identities_valid,
        "raw_candidate_count": len(candidates),
        "geography_counts": dict(sorted(counts.items())),
        "cohort_counts": dict(sorted(cohort_counts.items())),
        "geography_cohort_counts": {
            g: {c: scoped_counts[(g, c)] for c in ("TECH", "SOCIAL")} for g in sorted(EXPECTED)
        },
        "source_contribution": {
            s: {"unique_companies": n, "exclusive_companies": exclusive_counts[s]}
            for s, n in sorted(source_counts.items())
        },
        "coverage_gaps": gaps,
        "factory_run_recommended": bool(candidates) and identities_valid,
        "ml_scale_ready": not gaps and identities_valid,
    }
