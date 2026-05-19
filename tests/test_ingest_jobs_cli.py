from src.connectors.base import SearchProfile
from src.ingest_jobs import select_profiles, source_matches


def make_profile(profile_name: str, source_name: str) -> SearchProfile:
    return SearchProfile(
        id=1,
        profile_name=profile_name,
        source_name=source_name,
        search_location=None,
        search_radius_km=None,
        offer_type=None,
        page_size=25,
    )


def test_source_matches_exact_source_name() -> None:
    assert source_matches(
        source_name="bundesagentur_fuer_arbeit",
        source_filter="bundesagentur_fuer_arbeit",
    )


def test_source_matches_source_family_for_colon_separated_targets() -> None:
    assert source_matches(
        source_name="greenhouse:stripe",
        source_filter="greenhouse",
    )


def test_source_does_not_match_partial_prefix() -> None:
    assert not source_matches(
        source_name="greenhouse_custom:stripe",
        source_filter="greenhouse",
    )


def test_select_profiles_without_filter_returns_all_active_profiles() -> None:
    class FakeRepository:
        def load_active_search_profiles(self):
            return [
                make_profile("ba_data_engineer_30629_50km", "bundesagentur_fuer_arbeit"),
                make_profile("greenhouse_stripe", "greenhouse:stripe"),
            ]

    selected = select_profiles(
        repository=FakeRepository(),
        profile_name=None,
        source_filter=None,
    )

    assert [profile.profile_name for profile in selected] == [
        "ba_data_engineer_30629_50km",
        "greenhouse_stripe",
    ]


def test_select_profiles_by_source_family() -> None:
    class FakeRepository:
        def load_active_search_profiles(self):
            return [
                make_profile("ba_data_engineer_30629_50km", "bundesagentur_fuer_arbeit"),
                make_profile("greenhouse_stripe", "greenhouse:stripe"),
            ]

    selected = select_profiles(
        repository=FakeRepository(),
        profile_name=None,
        source_filter="greenhouse",
    )

    assert [profile.profile_name for profile in selected] == ["greenhouse_stripe"]


def test_select_profiles_by_exact_profile_name() -> None:
    class FakeRepository:
        def load_search_profile(self, profile_name):
            return make_profile(profile_name, "bundesagentur_fuer_arbeit")

    selected = select_profiles(
        repository=FakeRepository(),
        profile_name="ba_data_engineer_30629_50km",
        source_filter=None,
    )

    assert [profile.profile_name for profile in selected] == [
        "ba_data_engineer_30629_50km"
    ]
