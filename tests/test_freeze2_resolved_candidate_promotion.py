from src.search_intelligence.freeze2_resolved_candidate_promotion import (
    build_resolved_promotion_plan,
    cohort_digest,
    report_payload,
    select_resolved_origin_evidence,
)


def _review_payload() -> dict[str, object]:
    return {
        "review": {
            "items": [
                {
                    "company_key": "audi",
                    "company_name": "AUDI AG",
                    "source_name": "linkedin",
                    "decision": "manual_review_required",
                    "priority": 20,
                    "evidence_count": 1,
                    "known_candidate_id": None,
                    "known_candidate_status": None,
                    "recommended_next_action": "review",
                    "reason": "single relevant sensor observation",
                },
                {
                    "company_key": "sonova_gruppe",
                    "company_name": "Sonova Gruppe",
                    "source_name": "linkedin",
                    "decision": "manual_review_required",
                    "priority": 15,
                    "evidence_count": 1,
                    "known_candidate_id": None,
                    "known_candidate_status": None,
                    "recommended_next_action": "review",
                    "reason": "single relevant sensor observation",
                },
                {
                    "company_key": "hdi",
                    "company_name": "HDI Group",
                    "source_name": "linkedin",
                    "decision": "already_known",
                    "priority": 99,
                    "evidence_count": 4,
                    "known_candidate_id": 2,
                    "known_candidate_status": "discovery",
                    "recommended_next_action": "route existing",
                    "reason": "known",
                },
            ]
        }
    }


def _origin_payload() -> dict[str, object]:
    return {
        "results": [
            {
                "company_key": "audi",
                "company_name": "AUDI AG",
                "resolution_state": "direct_source_resolved",
                "origin_decision": "origin_url_candidate_selected",
                "risk_level": "low",
                "selected_url": "https://www.audi.com/en/careers",
                "selected_domain": "www.audi.com",
                "confidence_score": 1.0,
                "sensor_decision": "manual_review_required",
                "sensor_evidence_count": 1,
                "sensor_source_name": "linkedin",
            },
            {
                "company_key": "sonova_gruppe",
                "company_name": "Sonova Gruppe",
                "resolution_state": "direct_source_review_required",
                "origin_decision": "manual_review_required",
                "risk_level": "medium",
                "selected_url": None,
                "selected_domain": None,
                "confidence_score": 0.94,
                "sensor_decision": "manual_review_required",
                "sensor_evidence_count": 1,
                "sensor_source_name": "linkedin",
            },
            {
                "company_key": "hdi",
                "company_name": "HDI Group",
                "resolution_state": "direct_source_resolved",
                "origin_decision": "origin_url_candidate_selected",
                "risk_level": "low",
                "selected_url": "https://www.hdi.de/karriere",
                "selected_domain": "www.hdi.de",
                "confidence_score": 1.0,
                "sensor_decision": "already_known",
                "sensor_evidence_count": 4,
                "sensor_source_name": "linkedin",
            },
        ]
    }


def test_only_low_risk_selected_https_origins_enter_cohort() -> None:
    origins = select_resolved_origin_evidence(_origin_payload())

    assert [item.company_key for item in origins] == ["audi", "hdi"]


def test_review_decision_still_controls_promotion_after_origin_resolution() -> None:
    plan, origins = build_resolved_promotion_plan(
        review_payload=_review_payload(),
        origin_payload=_origin_payload(),
    )

    assert [item.company_key for item in plan.items] == ["audi"]
    assert len(origins) == 2
    assert plan.items[0].source_decision == "manual_review_required"
    assert plan.items[0].action == "create_discovery_candidate_with_manual_review_opt_in"
    assert plan.items[0].create_allowed is True
    assert plan.items[0].candidate_url is None


def test_existing_candidate_recheck_can_only_narrow_effect_set() -> None:
    plan, _ = build_resolved_promotion_plan(
        review_payload=_review_payload(),
        origin_payload=_origin_payload(),
        existing_company_keys={"audi"},
    )

    assert len(plan.items) == 1
    assert plan.items[0].action == "skip_existing_candidate"
    assert plan.items[0].create_allowed is False


def test_cohort_digest_is_stable_and_binds_origin_url() -> None:
    plan, origins = build_resolved_promotion_plan(
        review_payload=_review_payload(),
        origin_payload=_origin_payload(),
    )
    first = cohort_digest(plan, origins)
    second = cohort_digest(plan, origins)

    changed = _origin_payload()
    changed["results"][0]["selected_url"] = "https://www.audi.com/en/careers/changed"
    changed_plan, changed_origins = build_resolved_promotion_plan(
        review_payload=_review_payload(),
        origin_payload=changed,
    )

    assert first == second
    assert first != cohort_digest(changed_plan, changed_origins)


def test_report_boundary_keeps_origin_url_out_of_candidate_url() -> None:
    report = report_payload(
        review_payload=_review_payload(),
        origin_payload=_origin_payload(),
    )

    assert report["summary"]["planned_create_count"] == 1
    assert report["items"][0]["candidate_url"] is None
    assert report["items"][0]["resolved_origin"]["selected_url"] == (
        "https://www.audi.com/en/careers"
    )
    assert report["boundary"]["candidate_url_write"] is False
