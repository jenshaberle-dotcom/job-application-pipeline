from __future__ import annotations

from src.search_intelligence.aggregator_novelty import (
    AggregatorEvidenceRow,
    KnownCompanyCandidate,
    PreviousNoveltySnapshot,
    build_aggregator_novelty_snapshot,
)


def row(company_key: str, company_name: str, title: str) -> AggregatorEvidenceRow:
    return AggregatorEvidenceRow(
        evidence_id=1,
        source_name="stepstone",
        company_key=company_key,
        company_name=company_name,
        title=title,
        search_profile_name="hannover_data",
        search_term="Data Engineer",
        observed_at="2026-06-01 10:00:00+00",
    )


def test_novelty_snapshot_distinguishes_unregistered_from_newly_observed() -> None:
    snapshot = build_aggregator_novelty_snapshot(
        source_name="stepstone",
        search_profile_name="hannover_data",
        search_term="Data Engineer",
        rows=[
            row("hdi", "HDI AG", "Platform Engineer Azure"),
            row("new_insurance", "New Insurance GmbH", "Lakehouse Data Engineer"),
        ],
        known_candidates=[
            KnownCompanyCandidate(
                candidate_id=2,
                company_key="hdi",
                company_name="HDI Group",
                status="manual_review_required",
                source_family_candidate="hdi",
            )
        ],
        known_vocabulary_terms={"hdi": {"platform", "azure"}},
        previous_snapshot=PreviousNoveltySnapshot(
            snapshot_id=10,
            company_keys=frozenset({"hdi"}),
            company_term_keys=frozenset({"hdi::platform", "hdi::azure"}),
        ),
    )

    assert snapshot.previous_snapshot_id == 10
    assert snapshot.evidence_count == 2
    assert snapshot.distinct_company_count == 2
    assert snapshot.known_candidate_company_count == 1
    assert snapshot.unregistered_company_count == 1
    assert snapshot.newly_observed_company_count == 1
    assert snapshot.repeated_observed_company_count == 1
    assert snapshot.reassessment_company_count == 1
    assert snapshot.recommended_action == "review_newly_observed_companies"
    assert any(item.novelty_state == "unregistered_company" for item in snapshot.items)
    assert any(item.novelty_state == "known_candidate_reassessment" for item in snapshot.items)
    assert any(item.novelty_state == "new_vocabulary_term" and item.observed_term == "lakehouse" for item in snapshot.items)


def test_first_snapshot_is_baseline_not_saturation_judgement() -> None:
    snapshot = build_aggregator_novelty_snapshot(
        source_name="stepstone",
        search_profile_name="hannover_data",
        search_term="Data Engineer",
        rows=[row("hdi", "HDI AG", "Platform Engineer Azure")],
        known_candidates=[],
        known_vocabulary_terms={},
    )

    assert snapshot.previous_snapshot_id is None
    assert snapshot.saturation_level == "baseline"
    assert snapshot.recommended_action == "persist_baseline_then_rerun"


def test_repeated_unregistered_companies_are_backlog_not_new_discovery() -> None:
    snapshot = build_aggregator_novelty_snapshot(
        source_name="stepstone",
        search_profile_name="hannover_data",
        search_term="Data Engineer",
        rows=[row("new_insurance", "New Insurance GmbH", "Lakehouse Data Engineer")],
        known_candidates=[],
        known_vocabulary_terms={"new_insurance": {"lakehouse", "data", "engineer"}},
        previous_snapshot=PreviousNoveltySnapshot(
            snapshot_id=11,
            company_keys=frozenset({"new_insurance"}),
            company_term_keys=frozenset({"new_insurance::lakehouse", "new_insurance::data", "new_insurance::engineer"}),
        ),
    )

    assert snapshot.unregistered_company_count == 1
    assert snapshot.newly_observed_company_count == 0
    assert snapshot.repeated_observed_company_count == 1
    assert snapshot.saturation_level == "saturated"
    assert snapshot.recommended_action == "review_unregistered_company_backlog"


def test_novelty_snapshot_recommends_reassessment_for_known_unresolved_candidates() -> None:
    snapshot = build_aggregator_novelty_snapshot(
        source_name="stepstone",
        search_profile_name="hannover_data",
        search_term="Python SQL",
        rows=[row("hdi_global", "HDI Global", "Database Specialist Cloud")],
        known_candidates=[
            KnownCompanyCandidate(
                candidate_id=2,
                company_key="hdi",
                company_name="HDI Group",
                status="manual_review_required",
                source_family_candidate="hdi",
            )
        ],
        known_vocabulary_terms={"hdi": {"database", "cloud"}},
        previous_snapshot=PreviousNoveltySnapshot(
            snapshot_id=12,
            company_keys=frozenset({"hdi_global"}),
            company_term_keys=frozenset({"hdi_global::database", "hdi_global::cloud"}),
        ),
    )

    assert snapshot.known_candidate_company_count == 1
    assert snapshot.reassessment_company_count == 1
    assert snapshot.recommended_action == "rerun_gate_reassessment_for_known_candidates"
