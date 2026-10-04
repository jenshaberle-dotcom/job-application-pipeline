"""Evaluate discovery coverage before expensive Factory work."""
from __future__ import annotations
from collections import Counter

EXPECTED={"REGION_HANNOVER","WOLFSBURG","INGOLSTADT","STUTTGART_REGION","BERLIN","MUNICH"}
MINIMUM={"REGION_HANNOVER":250,"WOLFSBURG":50,"INGOLSTADT":50,"STUTTGART_REGION":100,"BERLIN":250,"MUNICH":250}


def assess(census: dict[str, object]) -> dict[str, object]:
    counts=Counter()
    cohort_counts=Counter()
    for row in census.get("candidates",[]):
        for geography in row.get("geographies",[]): counts[str(geography)]+=1
        for cohort in row.get("cohorts",[]): cohort_counts[str(cohort)]+=1
    gaps={}
    for geography in sorted(EXPECTED):
        actual=counts[geography]; minimum=MINIMUM[geography]
        if actual<minimum:
            gaps[geography]={"actual":actual,"minimum":minimum,"additional_sources_required":True}
    return {
      "status":"PASS" if not gaps else "SOURCE_COVERAGE_GAP",
      "geography_counts":dict(sorted(counts.items())),
      "cohort_counts":dict(sorted(cohort_counts.items())),
      "coverage_gaps":gaps,
      "factory_run_recommended":bool(counts) and len(counts)>=3,
      "ml_scale_ready":not gaps,
    }
