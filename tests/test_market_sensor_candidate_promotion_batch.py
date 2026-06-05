from src.search_intelligence.market_sensor_candidate_promotion_batch import (
    MarketSensorPromotionInput,
    build_creation_plan_for_item,
    build_promotion_batch_plan,
)


def item(
    company_key: str = "clarios_germany",
    *,
    decision: str = "create_candidate_recommended",
    known_candidate_id: int | None = None,
) -> MarketSensorPromotionInput:
    return MarketSensorPromotionInput(
        item_id=2,
        review_id=1,
        company_key=company_key,
        company_name="Clarios Germany GmbH & Co. KG",
        source_name="stepstone",
        decision=decision,
        priority=146,
        evidence_count=8,
        known_candidate_id=known_candidate_id,
        reason="repeated observations",
    )


def test_create_candidate_recommended_is_allowed_as_discovery_candidate() -> None:
    plan = build_creation_plan_for_item(
        item(),
        include_manual_review_required=False,
        existing_company_keys=set(),
    )

    assert plan.create_allowed is True
    assert plan.action == "create_discovery_candidate"
    assert plan.candidate_url is None
    assert plan.source_name_candidate == "clarios_germany:discovery"
    assert plan.source_family_candidate == "clarios_germany"
    assert plan.source_type_candidate == "employer_origin_career_site"
    assert plan.risk_level == "unknown"


def test_manual_review_candidate_requires_explicit_opt_in() -> None:
    plan = build_creation_plan_for_item(
        item("vhv_gruppe", decision="manual_review_required"),
        include_manual_review_required=False,
        existing_company_keys=set(),
    )

    assert plan.create_allowed is False
    assert plan.action == "requires_manual_review_opt_in"

    opted_in = build_creation_plan_for_item(
        item("vhv_gruppe", decision="manual_review_required"),
        include_manual_review_required=True,
        existing_company_keys=set(),
    )

    assert opted_in.create_allowed is True
    assert opted_in.action == "create_discovery_candidate_with_manual_review_opt_in"
    assert opted_in.risk_level == "medium"


def test_existing_candidate_is_not_created_again() -> None:
    plan = build_creation_plan_for_item(
        item(known_candidate_id=42),
        include_manual_review_required=True,
        existing_company_keys=set(),
    )

    assert plan.create_allowed is False
    assert plan.action == "skip_existing_candidate"

    existing_by_table = build_creation_plan_for_item(
        item(),
        include_manual_review_required=True,
        existing_company_keys={"clarios_germany"},
    )

    assert existing_by_table.create_allowed is False
    assert existing_by_table.action == "skip_existing_candidate"


def test_batch_plan_preserves_explicit_requested_order_and_reports_missing_keys() -> None:
    batch = build_promotion_batch_plan(
        [
            item("computacenter"),
            item("clarios_germany"),
        ],
        requested_company_keys=("clarios_germany", "missing_company", "computacenter"),
        include_manual_review_required=False,
        existing_company_keys=set(),
    )

    assert [plan.company_key for plan in batch.items] == ["clarios_germany", "missing_company", "computacenter"]
    assert batch.items[1].action == "missing_market_sensor_item"
    assert batch.create_count == 2
    assert batch.blocked_count == 1
