"""Discovery scope for the Connector Factory / ML corpus.

The corpus deliberately separates sector cohorts from geography cohorts. A company may
belong to multiple cohorts after deduplication; that overlap is useful training evidence.
"""

PRIMARY_GEOGRAPHY = "REGION_HANNOVER"
EXPANSION_GEOGRAPHIES = (
    "WOLFSBURG",
    "INGOLSTADT",
    "STUTTGART_REGION",
    "BERLIN",
    "MUNICH",
)
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

# Expansion is evidence-driven. These are minimum corpus properties, not production SLAs.
MIN_UNIQUE_COMPANIES_BEFORE_GEOGRAPHY_EXPANSION = 1500
MIN_STRUCTURAL_FINGERPRINTS_BEFORE_GEOGRAPHY_EXPANSION = 50
MIN_FAILURE_EXAMPLES_FOR_ML = 250


def expansion_required(summary: dict[str, object]) -> bool:
    """Expand if Hannover does not provide enough volume *or* structural diversity."""
    return (
        int(summary.get("unique_company_count", 0)) < MIN_UNIQUE_COMPANIES_BEFORE_GEOGRAPHY_EXPANSION
        or int(summary.get("structural_fingerprint_count", 0)) < MIN_STRUCTURAL_FINGERPRINTS_BEFORE_GEOGRAPHY_EXPANSION
        or int(summary.get("negative_or_gap_example_count", 0)) < MIN_FAILURE_EXAMPLES_FOR_ML
    )
