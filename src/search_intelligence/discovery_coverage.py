"""Evaluate discovery coverage before expensive Factory work."""

from __future__ import annotations
from collections import Counter

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
    for row in census.get("candidates", []):
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
    return {
        "status": "PASS" if not gaps else "SOURCE_COVERAGE_GAP",
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
        "factory_run_recommended": bool(census.get("candidates")),
        "ml_scale_ready": not gaps,
    }
