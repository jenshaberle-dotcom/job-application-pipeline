from src.search_intelligence.stepstone_candidate_persistence import (
    ExistingEmployerCandidate,
    StepStoneObservedCompany,
    plan_stepstone_candidate_persistence,
)


def _observation(
    *,
    company_key: str = "new_employer",
    company_name: str = "New Employer GmbH",
) -> StepStoneObservedCompany:
    return StepStoneObservedCompany(
        review_id=7,
        review_item_id=9,
        source_name="stepstone",
        search_profile_name="stepstone_data_engineer_hannover",
        search_term="Machine Learning Engineer",
        company_key=company_key,
        company_name=company_name,
        evidence_count=3,
        sample_titles=("ML Engineer", "AI Platform Engineer"),
        source_mode="baseline",
    )


def test_new_stepstone_employer_becomes_low_risk_discovery_candidate() -> None:
    plan = plan_stepstone_candidate_persistence(_observation(), ())

    assert plan.action == "created_discovery_candidate"
    assert plan.create_allowed
    assert plan.normalized_company_key == "new_employer"
    assert plan.source_name_candidate == "new_employer:discovery"
    assert plan.source_family_candidate == "new_employer"
    assert plan.source_type_candidate == "employer_origin_career_site"
    assert plan.risk_level == "unknown"
    assert plan.matched_candidate_id is None


def test_exact_existing_candidate_is_not_duplicated() -> None:
    existing = ExistingEmployerCandidate(
        candidate_id=42,
        company_key="hdi",
        company_name="HDI AG",
        status="active_controlled",
    )

    plan = plan_stepstone_candidate_persistence(
        _observation(company_key="hdi", company_name="HDI AG"),
        (existing,),
    )

    assert plan.action == "matched_existing_candidate"
    assert not plan.create_allowed
    assert plan.matched_candidate_id == 42
    assert plan.matched_candidate_key == "hdi"


def test_company_family_variant_matches_existing_candidate() -> None:
    existing = ExistingEmployerCandidate(
        candidate_id=43,
        company_key="hdi",
        company_name="HDI AG",
        status="discovery",
    )

    plan = plan_stepstone_candidate_persistence(
        _observation(
            company_key="hdi_global",
            company_name="HDI Global SE",
        ),
        (existing,),
    )

    assert plan.action == "matched_existing_candidate"
    assert not plan.create_allowed
    assert plan.matched_candidate_id == 43
    assert plan.matched_candidate_key == "hdi"


def test_invalid_company_is_audited_but_not_created() -> None:
    plan = plan_stepstone_candidate_persistence(
        _observation(company_key="", company_name=""),
        (),
    )

    assert plan.action == "skipped_invalid_company"
    assert not plan.create_allowed
    assert plan.matched_candidate_id is None
