from __future__ import annotations

from src.search_intelligence.origin_seed_pool import (
    classify_seed_row,
    deduplicate_seeds,
    generate_company_url_candidates,
    observation_url_seeds,
    seed_type_counts,
)


def test_classifies_origin_url_seed_as_observable_learning_input() -> None:
    seed = classify_seed_row(
        {
            "seed_source_table": "employer_origin_source_candidates",
            "company_key": "adesso",
            "company_name": "adesso SE",
            "source_name_candidate": "adesso:discovery",
            "source_family_candidate": "adesso",
            "candidate_url": "https://jobs.adesso-group.com/",
        }
    )

    assert seed.seed_type == "origin_url_seed"
    assert seed.observation_role == "origin_url_observation"
    assert seed.url_allowed_for_observation is True
    assert seed.priority_score >= 0.75
    assert seed.evidence["boundary"]["learning_input_only"] is True
    assert seed.evidence["boundary"]["no_gate_decision"] is True


def test_classifies_company_name_only_seed_for_url_discovery_not_observation() -> None:
    seed = classify_seed_row(
        {
            "seed_source_table": "candidate_expansion_review_items",
            "company_key": "dirk_rossmann",
            "company_name": "Dirk Rossmann GmbH",
            "source_name": "stepstone",
            "distinct_search_term_count": 3,
        }
    )

    assert seed.seed_type == "company_name_only_seed"
    assert seed.observation_role == "url_discovery_input"
    assert seed.url_allowed_for_observation is False
    assert seed.priority_score > 0.60


def test_classifies_ba_as_text_signal_seed_not_origin_structure() -> None:
    seed = classify_seed_row(
        {
            "seed_source_table": "raw_jobs",
            "source_name": "bundesagentur_fuer_arbeit",
            "source_url": "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs/123",
        }
    )

    assert seed.seed_type == "job_text_signal_seed"
    assert seed.observation_role == "text_signal_learning"
    assert seed.url_allowed_for_observation is False


def test_classifies_greenhouse_and_personio_as_bounded_ats_structure_seed() -> None:
    greenhouse = classify_seed_row(
        {
            "seed_source_table": "raw_jobs",
            "source_name": "greenhouse:contentful",
            "source_url": "https://boards.greenhouse.io/contentful/jobs/123",
        }
    )
    personio = classify_seed_row(
        {
            "seed_source_table": "raw_jobs",
            "source_name": "personio:eraneos",
            "source_url": "https://eraneos.jobs.personio.de/job/123",
        }
    )

    assert greenhouse.seed_type == "ats_structure_seed"
    assert greenhouse.url_allowed_for_observation is True
    assert personio.seed_type == "ats_structure_seed"
    assert personio.url_allowed_for_observation is True


def test_classifies_stepstone_as_company_discovery_only() -> None:
    seed = classify_seed_row(
        {
            "seed_source_table": "aggregator_novelty_items",
            "source_name": "stepstone",
            "company_key": "example",
            "company_name": "Example GmbH",
            "evidence_url": "https://www.stepstone.de/jobs/example",
        }
    )

    assert seed.seed_type == "aggregator_company_seed"
    assert seed.observation_role == "company_discovery_only"
    assert seed.url_allowed_for_observation is False


def test_deduplicate_seeds_keeps_highest_priority_for_same_seed_key() -> None:
    lower = classify_seed_row(
        {
            "seed_source_table": "raw_jobs",
            "source_name": "greenhouse:stripe",
            "source_url": "https://boards.greenhouse.io/stripe/jobs/123",
        }
    )
    higher = classify_seed_row(
        {
            "seed_source_table": "employer_origin_source_candidates",
            "company_key": "stripe",
            "company_name": "Stripe",
            "candidate_url": "https://boards.greenhouse.io/stripe/jobs/123",
        }
    )

    result = deduplicate_seeds([lower, higher])

    assert len(result) == 2  # different seed type keeps source-role distinction
    assert seed_type_counts(result)["ats_structure_seed"] == 1
    assert seed_type_counts(result)["origin_url_seed"] == 1


def test_observation_url_seeds_excludes_company_and_text_signal_seeds() -> None:
    seeds = [
        classify_seed_row({"seed_source_table": "candidate_expansion_review_items", "company_name": "Rossmann"}),
        classify_seed_row({"seed_source_table": "raw_jobs", "source_name": "bundesagentur_fuer_arbeit", "source_url": "https://example.com/ba"}),
        classify_seed_row({"seed_source_table": "raw_jobs", "source_name": "personio:demo", "source_url": "https://demo.jobs.personio.de/job/1"}),
    ]

    assert [seed.seed_type for seed in observation_url_seeds(seeds)] == ["ats_structure_seed"]


def test_company_url_candidates_use_promoted_patterns_without_claiming_evidence() -> None:
    urls = generate_company_url_candidates(
        "dirk_rossmann",
        "Dirk Rossmann GmbH",
        promoted_path_patterns=("/job/...", "/search/..."),
    )

    assert "https://jobs.dirk-rossmann.de/" in urls
    assert "https://jobs.dirk-rossmann.de/job" in urls
    assert "https://www.dirk-rossmann.de/karriere" in urls
