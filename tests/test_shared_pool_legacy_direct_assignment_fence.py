#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROAD = "runs-on: [self-hosted, Linux, X64, job-pipeline-runtime-linux]"
FENCE = "vars.RCC_JAP_LEGACY_DIRECT_ASSIGNMENT_ALLOWED == 'true'"
ACTIVE = [
    ".github/workflows/demo-top5-rankable-refill.yml",
    ".github/workflows/f5-application-lifecycle-reconciliation.yml",
    ".github/workflows/f5-candidate-supersession-preflight.yml",
    ".github/workflows/f6-initial-assessment-materialization.yml",
    ".github/workflows/freeze2-ingestion-stall-diagnostic.yml",
    ".github/workflows/freeze2-job-first-census-comparison.yml",
    ".github/workflows/freeze2-linkedin-indeed-market-sensors.yml",
    ".github/workflows/freeze2-resolved-candidate-promotion.yml",
    ".github/workflows/freeze2-s0-source-truth-baseline.yml",
    ".github/workflows/freeze2-s1-s2-residual-classification.yml",
    ".github/workflows/freeze2-sensor-candidate-expansion-review.yml",
    ".github/workflows/p1-generic-origin-product-activate.yml",
    ".github/workflows/p1-generic-origin-product-proof.yml",
    ".github/workflows/p1-generic-origin-systematic-search.yml",
    ".github/workflows/trusted-local-product-campaign.yml",
]

def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)

def main() -> int:
    for rel in ACTIVE:
        text = (ROOT / rel).read_text(encoding="utf-8")
        require(BROAD in text, f"legacy broad route identity drifted: {rel}")
        require(FENCE in text, f"legacy broad route must be fail-closed: {rel}")

    canary = (ROOT / ".github/workflows/rcc-real-warm-canary.yml").read_text(encoding="utf-8")
    require("fromJSON(inputs.runs_on_json)" in canary, "shared canary must use exact RCC pre-assignment selector")
    require("rcc-general-linux-01--jap" in canary, "shared canary exact JAP facade is missing")
    require(FENCE not in canary, "reservation-bound shared canary must not depend on legacy direct-assignment variable")

    print("JAP_LEGACY_DIRECT_ASSIGNMENT_FENCE=PASS")
    print("JAP_SHARED_POOL_EXACT_CANARY_ROUTE=PASS")
    print(f"JAP_FENCED_BROAD_WORKFLOWS={len(ACTIVE)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
