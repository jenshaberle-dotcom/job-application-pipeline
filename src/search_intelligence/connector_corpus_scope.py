"""Discovery scope for the Connector Factory / ML corpus.

TECH is intentionally multi-region from day one. SOCIAL is a Hannover-only contrast
cohort. Geography is therefore an experimental dimension, not an expansion fallback.
"""

TECH_GEOGRAPHIES = (
    "REGION_HANNOVER",
    "WOLFSBURG",
    "INGOLSTADT",
    "STUTTGART_REGION",
    "BERLIN",
    "MUNICH",
)
SOCIAL_GEOGRAPHIES = ("REGION_HANNOVER",)

SECTOR_COHORTS = (
    "TECH",
    "SOCIAL",
    "HEALTH",
    "ENGINEERING",
    "AUTOMOTIVE",
    "ENERGY",
    "LOGISTICS",
    "FINANCE_INSURANCE",
    "SCIENCE_RESEARCH",
    "CREATIVE_DIGITAL",
)

MIN_STRUCTURAL_FINGERPRINTS_FOR_ML = 50
MIN_FAILURE_EXAMPLES_FOR_ML = 250
MIN_SUCCESS_EXAMPLES_FOR_ML = 250


def geography_allowed(cohort: str, geography: str) -> bool:
    cohort = cohort.strip().upper()
    geography = geography.strip().upper()
    if cohort == "SOCIAL":
        return geography in SOCIAL_GEOGRAPHIES
    return geography in TECH_GEOGRAPHIES


def ml_readiness(summary: dict[str, object]) -> dict[str, object]:
    """Return explicit readiness signals; volume never suppresses discovery."""
    checks = {
        "structural_diversity": int(summary.get("structural_fingerprint_count", 0)) >= MIN_STRUCTURAL_FINGERPRINTS_FOR_ML,
        "negative_examples": int(summary.get("negative_or_gap_example_count", 0)) >= MIN_FAILURE_EXAMPLES_FOR_ML,
        "positive_examples": int(summary.get("success_example_count", 0)) >= MIN_SUCCESS_EXAMPLES_FOR_ML,
        "multi_geography": int(summary.get("geography_count", 0)) >= len(TECH_GEOGRAPHIES),
    }
    return {"ready": all(checks.values()), "checks": checks}
