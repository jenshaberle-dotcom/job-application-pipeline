from datetime import UTC, datetime, timedelta

from src.search_intelligence.stepstone_decoupled_cycle_policy import (
    BaselineCompanyObservation,
    BaselineCycleState,
    DecoupledCyclePolicy,
    OriginConnectorState,
    StepStoneCardVocabularyObservation,
    aggregate_company_title_vocabulary,
    build_suppression_set_from_baseline,
    decide_stepstone_run_mode,
    plan_origin_refresh_decisions,
)


NOW = datetime(2026, 8, 3, 8, 0, tzinfo=UTC)
POLICY = DecoupledCyclePolicy(
    requested_filter_count=5,
    baseline_refresh_interval_hours=24,
    max_filtered_runs_between_baselines=3,
    vocabulary_staleness_hours=72,
    origin_refresh_cooldown_hours=12,
    dominance_min_cards=5,
    dominance_min_share=0.40,
    policy_version="test-v1",
)


def _company(
    key: str,
    count: int,
    position: int,
    name: str | None = None,
) -> BaselineCompanyObservation:
    return BaselineCompanyObservation(
        company_key=key,
        company_name=name or key,
        card_count=count,
        first_position=position,
    )


def test_initial_cycle_requires_one_unfiltered_baseline() -> None:
    decision = decide_stepstone_run_mode(
        state=BaselineCycleState(
            last_baseline_at=None,
            next_baseline_due_at=None,
        ),
        policy=POLICY,
        now=NOW,
        has_active_suppression_set=False,
    )

    assert decision.mode == "baseline"
    assert decision.reason == "no_valid_baseline_exists"
    assert not decision.uses_active_suppression_set


def test_filtered_runs_reuse_the_same_active_baseline_suppression_set() -> None:
    decision = decide_stepstone_run_mode(
        state=BaselineCycleState(
            last_baseline_at=NOW - timedelta(hours=4),
            next_baseline_due_at=NOW + timedelta(hours=20),
            filtered_runs_since_baseline=1,
        ),
        policy=POLICY,
        now=NOW,
        has_active_suppression_set=True,
    )

    assert decision.mode == "filtered"
    assert decision.reason == "reuse_last_valid_baseline_suppression_set"
    assert decision.uses_active_suppression_set


def test_maximum_filtered_runs_forces_baseline_recalibration() -> None:
    decision = decide_stepstone_run_mode(
        state=BaselineCycleState(
            last_baseline_at=NOW - timedelta(hours=8),
            next_baseline_due_at=NOW + timedelta(hours=16),
            filtered_runs_since_baseline=3,
        ),
        policy=POLICY,
        now=NOW,
        has_active_suppression_set=True,
    )

    assert decision.mode == "baseline"
    assert decision.reason == "maximum_filtered_runs_since_baseline_reached"


def test_vocabulary_staleness_can_bring_baseline_forward() -> None:
    decision = decide_stepstone_run_mode(
        state=BaselineCycleState(
            last_baseline_at=NOW - timedelta(hours=4),
            next_baseline_due_at=NOW + timedelta(hours=20),
            filtered_runs_since_baseline=1,
            vocabulary_refresh_due=True,
        ),
        policy=POLICY,
        now=NOW,
        has_active_suppression_set=True,
    )

    assert decision.mode == "baseline"
    assert decision.reason == "company_vocabulary_refresh_due"


def test_missing_active_suppression_set_fails_closed_to_baseline() -> None:
    decision = decide_stepstone_run_mode(
        state=BaselineCycleState(
            last_baseline_at=NOW - timedelta(hours=4),
            next_baseline_due_at=NOW + timedelta(hours=20),
            filtered_runs_since_baseline=1,
        ),
        policy=POLICY,
        now=NOW,
        has_active_suppression_set=False,
    )

    assert decision.mode == "baseline"
    assert decision.reason == "active_suppression_set_missing"


def test_suppression_set_is_derived_from_baseline_and_bounded_by_capacity() -> None:
    observations = [
        _company("hdi", 8, 1, "HDI AG"),
        _company("tib", 5, 2, "Technische Informationsbibliothek (TIB)"),
        _company("sopra_steria", 4, 3, "Sopra Steria"),
        _company("adesso", 3, 4, "adesso SE"),
        _company("enercity", 2, 5, "enercity AG"),
        _company("other", 1, 6, "Other GmbH"),
    ]

    suppression = build_suppression_set_from_baseline(
        observations=observations,
        policy=POLICY,
        baseline_review_id=42,
    )

    assert suppression.baseline_review_id == 42
    assert suppression.baseline_observed_count == 23
    assert suppression.baseline_distinct_company_count == 6
    assert suppression.selected_filter_count == 5
    assert suppression.company_keys == (
        "hdi",
        "tib",
        "sopra_steria",
        "adesso",
        "enercity",
    )
    assert suppression.aliases[0] == "HDI"
    assert suppression.aliases[3] == "adesso"
    assert "other" not in suppression.company_keys


def test_filtered_observations_do_not_rewrite_the_baseline_suppression_set() -> None:
    baseline = build_suppression_set_from_baseline(
        observations=[
            _company("hdi", 8, 1),
            _company("tib", 5, 2),
            _company("sopra", 3, 3),
            _company("adesso", 2, 4),
            _company("enercity", 1, 5),
        ],
        policy=POLICY,
    )
    filtered_page = [
        _company("new_a", 10, 1),
        _company("new_b", 8, 2),
    ]

    assert filtered_page
    assert baseline.company_keys == ("hdi", "tib", "sopra", "adesso", "enercity")


def test_dominant_known_company_triggers_one_origin_refresh_signal() -> None:
    decisions = plan_origin_refresh_decisions(
        baseline_observations=[
            _company("hdi", 25, 1, "HDI AG"),
            _company("hdi", 0, 2, "HDI AG"),
        ],
        connector_states=[
            OriginConnectorState(
                company_key="hdi",
                has_origin_connector=True,
            )
        ],
        policy=POLICY,
        now=NOW,
    )

    assert len(decisions) == 1
    assert decisions[0].company_key == "hdi"
    assert decisions[0].card_count == 25
    assert decisions[0].card_share == 1.0
    assert decisions[0].action == "trigger_origin_refresh"


def test_origin_refresh_pending_deduplicates_repeated_stepstone_evidence() -> None:
    decisions = plan_origin_refresh_decisions(
        baseline_observations=[_company("hdi", 10, 1, "HDI AG")],
        connector_states=[
            OriginConnectorState(
                company_key="hdi",
                has_origin_connector=True,
                refresh_pending=True,
            )
        ],
        policy=POLICY,
        now=NOW,
    )

    assert decisions[0].action == "deduplicated_refresh_pending"
    assert decisions[0].reason == "origin_refresh_already_pending"


def test_origin_refresh_cooldown_is_independent_from_company_suppression() -> None:
    suppression = build_suppression_set_from_baseline(
        observations=[_company("hdi", 25, 1, "HDI AG")],
        policy=POLICY,
    )
    decisions = plan_origin_refresh_decisions(
        baseline_observations=[_company("hdi", 25, 1, "HDI AG")],
        connector_states=[
            OriginConnectorState(
                company_key="hdi",
                has_origin_connector=True,
                refresh_cooldown_until=NOW + timedelta(hours=6),
            )
        ],
        policy=POLICY,
        now=NOW,
    )

    assert suppression.company_keys == ("hdi",)
    assert decisions[0].action == "deduplicated_refresh_cooldown"
    assert decisions[0].reason == "origin_refresh_cooldown_active"


def test_dominant_company_without_connector_emits_origin_discovery_signal() -> None:
    decisions = plan_origin_refresh_decisions(
        baseline_observations=[_company("new_company", 12, 1)],
        connector_states=[],
        policy=POLICY,
        now=NOW,
    )

    assert decisions[0].action == "origin_discovery_signal"
    assert decisions[0].reason == "dominant_company_has_no_origin_connector"


def test_company_title_vocabulary_is_compact_and_deduplicated() -> None:
    vocabulary = aggregate_company_title_vocabulary(
        [
            StepStoneCardVocabularyObservation(
                company_key="hdi",
                company_name="HDI AG",
                raw_title="Machine Learning Engineer",
                job_key="job-1",
            ),
            StepStoneCardVocabularyObservation(
                company_key="hdi",
                company_name="HDI AG",
                raw_title="  Machine   Learning Engineer ",
                job_key="job-1",
            ),
            StepStoneCardVocabularyObservation(
                company_key="hdi",
                company_name="HDI AG",
                raw_title="MLOps Engineer",
                job_key="job-2",
            ),
        ]
    )

    assert len(vocabulary) == 2
    ml = next(item for item in vocabulary if item.normalized_title == "machine learning engineer")
    assert ml.observation_count == 2
    assert ml.job_keys == ("job-1",)
    assert ml.raw_title == "Machine Learning Engineer"
