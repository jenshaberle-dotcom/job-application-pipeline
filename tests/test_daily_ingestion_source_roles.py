import pytest

from src.connectors.base import SearchProfile
from src.connectors.registry import SourceRole, source_role
from src.ingest_jobs import select_profiles


def _profile(
    profile_id: int,
    profile_name: str,
    source_name: str,
) -> SearchProfile:
    return SearchProfile(
        id=profile_id,
        profile_name=profile_name,
        source_name=source_name,
        search_location=None,
        search_radius_km=None,
        offer_type=None,
        page_size=25,
    )


class FakeRepository:
    def __init__(
        self,
        profiles: list[SearchProfile],
        recurring_names: set[str],
    ) -> None:
        self._profiles = profiles
        self._recurring_names = recurring_names

    def load_active_search_profiles(self) -> list[SearchProfile]:
        return list(self._profiles)

    def load_recurring_search_profile_names(self) -> set[str]:
        return set(self._recurring_names)


def test_default_registry_separates_sensors_from_generic_employer_origin() -> None:
    assert source_role("bundesagentur_fuer_arbeit") == SourceRole.SENSOR
    assert source_role("stepstone") == SourceRole.SENSOR
    assert source_role("generic_origin:finanz_informatik") == SourceRole.EMPLOYER_ORIGIN
    assert source_role("generic_origin:example") == SourceRole.EMPLOYER_ORIGIN

    for retired_product_source in (
        "greenhouse:stripe",
        "personio:example",
        "successfactors:example",
        "finanz_informatik:hannover",
        "hdi:hannover",
        "enercity:discovery",
        "computacenter:discovery",
        "accompio:discovery",
    ):
        with pytest.raises(ValueError):
            source_role(retired_product_source)


def test_role_selection_uses_only_recurring_enabled_generic_profiles() -> None:
    profiles = [
        _profile(1, "ba", "bundesagentur_fuer_arbeit"),
        _profile(2, "stepstone", "stepstone"),
        _profile(3, "fi", "generic_origin:finanz_informatik"),
        _profile(4, "madsack", "generic_origin:madsack"),
        _profile(5, "computacenter_controlled", "generic_origin:computacenter"),
    ]
    repository = FakeRepository(
        profiles,
        recurring_names={"ba", "stepstone", "fi", "madsack"},
    )

    sensors = select_profiles(
        repository,
        profile_name=None,
        source_filter=None,
        role_filter=SourceRole.SENSOR,
    )
    origins = select_profiles(
        repository,
        profile_name=None,
        source_filter=None,
        role_filter=SourceRole.EMPLOYER_ORIGIN,
    )

    assert [profile.profile_name for profile in sensors] == ["ba", "stepstone"]
    assert [profile.profile_name for profile in origins] == ["fi", "madsack"]


def test_exact_profile_execution_still_bypasses_recurring_role_selection() -> None:
    controlled = _profile(
        5,
        "computacenter_controlled",
        "generic_origin:computacenter",
    )
    repository = FakeRepository([controlled], recurring_names=set())

    selected = select_profiles(
        repository,
        profile_name="computacenter_controlled",
        source_filter=None,
        role_filter=None,
    )

    assert selected == [controlled]
