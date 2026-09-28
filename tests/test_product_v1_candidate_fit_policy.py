from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.search_intelligence.product_v1_candidate_fit_policy import (
    load_candidate_fit_preference_policy,
    parse_candidate_fit_preference_policy,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "product_v1_candidate_fit_policy.json"


def test_tracked_candidate_fit_policy_is_approved_and_complete() -> None:
    policy = load_candidate_fit_preference_policy(POLICY_PATH)

    assert policy.status == "approved"
    assert policy.regional_cities == ("hannover",)
    assert policy.remote_countries == ("de",)
    assert policy.work_models == ("hybrid", "onsite", "remote")
    assert policy.commute_max_minutes == 45
    assert policy.preference_tags() == (
        "profile-fit.city.hannover",
        "profile-fit.commute.max-45",
        "profile-fit.country.de",
        "profile-fit.work-model.hybrid",
        "profile-fit.work-model.onsite",
        "profile-fit.work-model.remote",
    )


def test_candidate_fit_policy_rejects_unapproved_or_invalid_scope() -> None:
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    payload["status"] = "draft"
    with pytest.raises(ValueError, match="approved"):
        parse_candidate_fit_preference_policy(payload)

    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    payload["geography"]["work_models"] = ["teleport"]
    with pytest.raises(ValueError, match="work model"):
        parse_candidate_fit_preference_policy(payload)


def test_control_center_prefers_private_profile_tags_before_tracked_fallback() -> None:
    source = (ROOT / "scripts" / "product_v1_control_center_base.py").read_text(
        encoding="utf-8"
    )

    assert "private_tags or _tracked_profile_fit_preference_tags()" in source
    assert "product_v1_candidate_fit_policy.json" in source
    assert "profile-fit.%" in source
