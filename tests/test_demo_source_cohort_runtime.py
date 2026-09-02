from __future__ import annotations

from dataclasses import dataclass

import scripts.run_demo_source_cohort_runtime as cohort
from src.connectors.base import SearchProfile, SearchTerm


@dataclass
class FakeRepository:
    profiles: list[SearchProfile]
    recurring: set[str]
    terms: dict[str, list[str]]

    def load_active_search_profiles(self):
        return list(self.profiles)

    def load_recurring_search_profile_names(self):
        return set(self.recurring)

    def load_active_search_terms(self, profile_name):
        profile = next(p for p in self.profiles if p.profile_name == profile_name)
        return [
            (profile, SearchTerm(search_term=value, id=index + 1))
            for index, value in enumerate(self.terms.get(profile_name, []))
        ]


def _profile(profile_name: str, source_name: str) -> SearchProfile:
    return SearchProfile(
        id=1 if "eraneos" in profile_name else 2,
        profile_name=profile_name,
        source_name=source_name,
        search_location="Hannover",
        search_radius_km=50,
        offer_type=1,
        page_size=25,
    )


def _ready_repository() -> FakeRepository:
    profiles = [
        _profile(
            "personio_eraneos_data_engineer_remote",
            "personio:eraneos",
        ),
        _profile(
            "personio_1komma5grad_data_engineer_germany",
            "personio:1komma5grad",
        ),
    ]
    return FakeRepository(
        profiles=profiles,
        recurring={profile.profile_name for profile in profiles},
        terms={
            "personio_eraneos_data_engineer_remote": ["data engineer", "ai engineer"],
            "personio_1komma5grad_data_engineer_germany": ["data engineer", "analytics engineer"],
        },
    )


def test_plan_requires_exact_existing_recurring_profiles(monkeypatch) -> None:
    repository = _ready_repository()
    monkeypatch.setattr(
        cohort,
        "profile_source_role",
        lambda _profile: cohort.SourceRole.EMPLOYER_ORIGIN,
    )

    plan = cohort.build_plan(repository)  # type: ignore[arg-type]

    assert plan["cohort_ready"] is True
    assert plan["blockers"] == []
    assert [row["source_name"] for row in plan["targets"]] == [
        "personio:eraneos",
        "personio:1komma5grad",
    ]
    assert all(row["ready"] is True for row in plan["targets"])
    assert plan["boundaries"]["database_writes"] is False


def test_plan_blocks_missing_profile(monkeypatch) -> None:
    repository = _ready_repository()
    repository.profiles = repository.profiles[:1]
    repository.recurring = {repository.profiles[0].profile_name}
    monkeypatch.setattr(
        cohort,
        "profile_source_role",
        lambda _profile: cohort.SourceRole.EMPLOYER_ORIGIN,
    )

    plan = cohort.build_plan(repository)  # type: ignore[arg-type]

    assert plan["cohort_ready"] is False
    assert (
        "missing_active_profile:personio_1komma5grad_data_engineer_germany"
        in plan["blockers"]
    )


def test_plan_blocks_source_binding_mismatch(monkeypatch) -> None:
    repository = _ready_repository()
    repository.profiles[0] = _profile(
        "personio_eraneos_data_engineer_remote",
        "personio:not-eraneos",
    )
    monkeypatch.setattr(
        cohort,
        "profile_source_role",
        lambda _profile: cohort.SourceRole.EMPLOYER_ORIGIN,
    )

    plan = cohort.build_plan(repository)  # type: ignore[arg-type]

    assert plan["cohort_ready"] is False
    assert any(
        blocker.startswith("source_binding_mismatch:personio_eraneos")
        for blocker in plan["blockers"]
    )


def test_plan_blocks_nonrecurring_or_empty_terms(monkeypatch) -> None:
    repository = _ready_repository()
    repository.recurring.remove("personio:missing") if "personio:missing" in repository.recurring else None
    repository.recurring.remove("personio_eraneos_data_engineer_remote")
    repository.terms["personio_1komma5grad_data_engineer_germany"] = []
    monkeypatch.setattr(
        cohort,
        "profile_source_role",
        lambda _profile: cohort.SourceRole.EMPLOYER_ORIGIN,
    )

    plan = cohort.build_plan(repository)  # type: ignore[arg-type]

    assert "recurring_disabled:personio_eraneos_data_engineer_remote" in plan["blockers"]
    assert "no_active_terms:personio_1komma5grad_data_engineer_germany" in plan["blockers"]
    assert plan["cohort_ready"] is False


def test_execute_refuses_unready_plan() -> None:
    try:
        cohort.execute(object(), {"cohort_ready": False})  # type: ignore[arg-type]
    except RuntimeError as exc:
        assert "not ready" in str(exc)
    else:
        raise AssertionError("execute must refuse an unready cohort")
