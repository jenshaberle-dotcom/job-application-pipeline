from __future__ import annotations

import json
from pathlib import Path

from src.connectors.factory_aggressive_policy import FactoryCandidate, evaluate_population


CATALOG = Path("contracts/connector-capability-catalog-v1.json")


def catalog():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def test_aggressive_policy_reuses_generic_recipe_and_queues_unknown_gap():
    candidates = [
        FactoryCandidate(
            company_key="known",
            company_name="Known GmbH",
            cohort="TECH",
            origin_url="https://known.example/jobs",
            source_type="employer_origin_career_site",
            fingerprint_tags=("structured_jobposting_inventory", "structured_jobposting_detail"),
            evidence_ids=("e:1",),
            origin_verified=True,
        ),
        FactoryCandidate(
            company_key="unknown",
            company_name="Unknown e.V.",
            cohort="SOCIAL",
            origin_url="https://unknown.example/karriere",
            source_type="employer_origin_career_site",
            fingerprint_tags=("novel:list", "novel:detail"),
            evidence_ids=("e:2",),
            origin_verified=True,
        ),
    ]

    result = evaluate_population(candidates, catalog())

    assert result["candidate_count"] == 2
    assert result["disposition_counts"] == {"capability_gap": 1, "recipe_ready": 1}
    assert result["policy"]["process_every_candidate"] is True
    assert result["policy"]["silent_drop_allowed"] is False
    assert len(result["engineering_queue"]) == 1
    gap = result["engineering_queue"][0]
    assert gap["candidate_keys"] == ["unknown"]
    assert gap["next_action"] == "BUILD_OR_EXTEND_GENERIC_CAPABILITY"
    assert gap["employer_specific_code_allowed"] is False


def test_missing_origin_is_not_dropped_but_becomes_evidence_work():
    result = evaluate_population(
        [FactoryCandidate("acme", "Acme", "TECH", None, None)],
        catalog(),
    )

    assert result["disposition_counts"] == {"evidence_gap": 1}
    assert result["engineering_queue"][0]["next_action"] == "ACQUIRE_ORIGIN_EVIDENCE"
