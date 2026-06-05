from __future__ import annotations

from src.search_intelligence.origin_pattern_promotion import ObservedPattern, promote_observed_pattern


def test_promotes_safe_job_path_pattern_as_detail_discovery_not_relevance_signal() -> None:
    decision = promote_observed_pattern(
        ObservedPattern(
            pattern_type="url_path_pattern",
            pattern_value="/job/...",
            evidence_count=1,
            confidence=0.4,
        )
    )

    assert decision.promotion_status == "promoted"
    assert decision.pattern_category == "url_detail_pattern"
    assert decision.usage_scope == "detail_url_discovery"
    assert decision.usable_by_url_finder is True
    assert decision.usable_by_relevance_probe is False


def test_promotes_search_path_pattern_as_listing_discovery_only() -> None:
    decision = promote_observed_pattern(
        ObservedPattern(
            pattern_type="url_path_pattern",
            pattern_value="/search/...",
            evidence_count=1,
            confidence=0.4,
        )
    )

    assert decision.promotion_status == "promoted"
    assert decision.pattern_category == "url_listing_pattern"
    assert decision.usage_scope == "listing_url_discovery"
    assert decision.usable_by_url_finder is True
    assert decision.usable_by_relevance_probe is False


def test_promotes_home_office_as_remote_signal_and_multi_location_as_location_signal() -> None:
    home_office = promote_observed_pattern(
        ObservedPattern(
            pattern_type="remote_signal",
            pattern_value="home-office",
            evidence_count=1,
            confidence=0.4,
        )
    )
    multi_location = promote_observed_pattern(
        ObservedPattern(
            pattern_type="location_signal",
            pattern_value="+ weitere",
            evidence_count=1,
            confidence=0.4,
        )
    )

    assert home_office.promotion_status == "promoted"
    assert home_office.pattern_category == "remote_work_signal"
    assert home_office.usage_scope == "relevance_remote"
    assert home_office.usable_by_relevance_probe is True
    assert multi_location.promotion_status == "promoted"
    assert multi_location.pattern_category == "location_multi_signal"
    assert multi_location.usage_scope == "relevance_location"
    assert multi_location.signal_strength == "medium"
    assert multi_location.usable_by_relevance_probe is True


def test_does_not_promote_multi_location_as_remote_signal() -> None:
    decision = promote_observed_pattern(
        ObservedPattern(
            pattern_type="remote_signal",
            pattern_value="+ weitere",
            evidence_count=1,
            confidence=0.95,
        )
    )

    assert decision.promotion_status == "candidate"
    assert decision.pattern_category == "location_multi_signal"
    assert decision.usage_scope == "diagnostics_only"
    assert decision.usable_by_relevance_probe is False
    assert "not a remote-work signal" in decision.reason


def test_keeps_short_ambiguous_profile_signal_as_candidate() -> None:
    decision = promote_observed_pattern(
        ObservedPattern(
            pattern_type="profile_signal",
            pattern_value="bi",
            evidence_count=3,
            confidence=0.76,
        )
    )

    assert decision.promotion_status == "candidate"
    assert decision.pattern_category == "profile_ambiguous_signal"
    assert decision.usage_scope == "diagnostics_only"
    assert decision.usable_by_relevance_probe is False


def test_keeps_unknown_signals_as_candidates_not_promoted() -> None:
    decision = promote_observed_pattern(
        ObservedPattern(
            pattern_type="remote_signal",
            pattern_value="mega flexible vibes",
            evidence_count=1,
            confidence=0.4,
        )
    )

    assert decision.promotion_status == "candidate"
    assert decision.usable_by_relevance_probe is False


def test_promotes_profile_domain_signal_separately_from_skill_signal() -> None:
    decision = promote_observed_pattern(
        ObservedPattern(
            pattern_type="profile_signal",
            pattern_value="data & analytics",
            evidence_count=2,
            confidence=0.70,
        )
    )

    assert decision.promotion_status == "promoted"
    assert decision.pattern_category == "profile_domain_signal"
    assert decision.usage_scope == "relevance_profile"
    assert decision.usable_by_relevance_probe is True


def test_structural_markers_are_diagnostics_only_not_url_finder_strategy() -> None:
    decision = promote_observed_pattern(
        ObservedPattern(
            pattern_type="structural_marker",
            pattern_value="page_type:job_detail",
            evidence_count=3,
            confidence=0.95,
        )
    )

    assert decision.promotion_status == "promoted"
    assert decision.pattern_category == "structural_marker"
    assert decision.usage_scope == "diagnostics_only"
    assert decision.usable_by_url_finder is False
    assert decision.usable_by_relevance_probe is False
