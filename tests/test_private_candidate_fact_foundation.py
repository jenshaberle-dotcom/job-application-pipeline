from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.search_intelligence.candidate_fact_profile import (
    APPROVAL_TOKEN,
    CAPABILITY_EVIDENCE_CLASSES,
    PROFILE_KEY,
    SCHEMA_VERSION,
    candidate_fact_rows,
    capability_evidence_by_tag,
    ensure_no_capability_claim_from_direction,
    load_candidate_fact_profile_json,
    parse_candidate_fact_profile,
)


MIGRATION = Path(
    "db/migrations/088_create_private_candidate_fact_foundation.sql"
).read_text(encoding="utf-8")
RUNNER = Path("scripts/import_private_candidate_fact_profile.py").read_text(
    encoding="utf-8"
)
TEMPLATE_PATH = Path("config/examples/private_candidate_fact_profile.template.json")
TEMPLATE = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))


def provenance(
    source_type: str,
    reference: str = "private evidence reference",
) -> list[dict[str, object]]:
    return [
        {
            "source_type": source_type,
            "reference": reference,
            "observed_at": "2026-08-05T10:00:00+02:00",
        }
    ]


def approved_fact(
    *,
    fact_key: str,
    category: str,
    evidence_class: str,
    statement: str,
    source_type: str,
    tags: list[str] | None = None,
    limitations: list[str] | None = None,
) -> dict[str, object]:
    return {
        "fact_key": fact_key,
        "category": category,
        "evidence_class": evidence_class,
        "approval_status": "approved",
        "statement": statement,
        "capability_tags": tags or [],
        "limitations": limitations or [],
        "provenance": provenance(source_type),
        "valid_from": None,
        "valid_until": None,
        "approved_by": "jens",
        "approved_at": "2026-08-05T10:05:00+02:00",
    }


def approved_profile_payload() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_key": PROFILE_KEY,
        "profile_version": "candidate-profile-2026-08-05-v1",
        "status": "approved",
        "approved_by": "jens",
        "approved_at": "2026-08-05T10:10:00+02:00",
        "facts": [
            approved_fact(
                fact_key="employment.synthetic.engineering-skill",
                category="skill",
                evidence_class="professional_employment",
                statement="Synthetic professional engineering evidence for contract tests.",
                source_type="canonical_cv",
                tags=["python", "systems-engineering"],
                limitations=["synthetic_test_fixture"],
            ),
            approved_fact(
                fact_key="portfolio.synthetic.data-system",
                category="project",
                evidence_class="portfolio_implementation",
                statement="Synthetic implemented data-system evidence for contract tests.",
                source_type="repository",
                tags=["postgresql", "pytest"],
                limitations=["portfolio_not_employment"],
            ),
            approved_fact(
                fact_key="target.synthetic.direction",
                category="target_direction",
                evidence_class="target_direction",
                statement="Synthetic target direction for contract tests.",
                source_type="operator_assertion",
                tags=["machine-learning-engineering"],
                limitations=["not_capability_evidence", "synthetic_test_fixture"],
            ),
            approved_fact(
                fact_key="planned.synthetic.capability",
                category="skill",
                evidence_class="planned_capability",
                statement="Synthetic planned capability for contract tests.",
                source_type="operator_assertion",
                tags=["future-capability"],
                limitations=["not_capability_evidence", "synthetic_test_fixture"],
            ),
        ],
    }


def test_parses_approved_private_profile_and_separates_evidence_classes() -> None:
    profile = parse_candidate_fact_profile(approved_profile_payload())

    assert profile.schema_version == SCHEMA_VERSION
    assert profile.profile_key == PROFILE_KEY
    assert profile.status == "approved"
    assert len(profile.approved_facts) == 4
    assert {fact.fact_key for fact in profile.capability_evidence_facts} == {
        "employment.synthetic.engineering-skill",
        "portfolio.synthetic.data-system",
    }
    assert {fact.fact_key for fact in profile.production_evidence_facts} == {
        "employment.synthetic.engineering-skill"
    }
    assert len(profile.payload_sha256) == 64
    assert profile.revision_key.startswith(profile.profile_version)


def test_target_and_planned_facts_never_become_capability_evidence() -> None:
    profile = parse_candidate_fact_profile(approved_profile_payload())

    ensure_no_capability_claim_from_direction(profile.facts)
    non_capability = {
        fact.fact_key
        for fact in profile.facts
        if fact.evidence_class in {"target_direction", "planned_capability"}
    }
    capability = {fact.fact_key for fact in profile.capability_evidence_facts}
    assert non_capability.isdisjoint(capability)


def test_capability_tag_index_contains_only_eligible_approved_facts() -> None:
    profile = parse_candidate_fact_profile(approved_profile_payload())

    index = capability_evidence_by_tag(profile)

    assert index["python"] == ("employment.synthetic.engineering-skill",)
    assert index["postgresql"] == ("portfolio.synthetic.data-system",)
    assert "machine-learning-engineering" not in index
    assert "future-capability" not in index


def test_canonical_hash_is_stable_across_fact_and_tag_order() -> None:
    first_payload = approved_profile_payload()
    second_payload = deepcopy(first_payload)
    facts = second_payload["facts"]
    assert isinstance(facts, list)
    facts.reverse()
    for fact in facts:
        assert isinstance(fact, dict)
        tags = fact["capability_tags"]
        assert isinstance(tags, list)
        tags.reverse()

    first = parse_candidate_fact_profile(first_payload)
    second = parse_candidate_fact_profile(second_payload)

    assert first.canonical_payload() == second.canonical_payload()
    assert first.payload_sha256 == second.payload_sha256
    assert first.revision_key == second.revision_key


def test_redacted_summary_does_not_emit_statements_or_references() -> None:
    payload = approved_profile_payload()
    profile = parse_candidate_fact_profile(payload)

    summary_text = json.dumps(profile.redacted_summary(), sort_keys=True)

    assert "Synthetic professional engineering evidence" not in summary_text
    assert "private evidence reference" not in summary_text
    assert '"contains_statements": false' in summary_text
    assert '"contains_provenance_references": false' in summary_text


def test_candidate_fact_rows_preserve_private_payload_for_database_only() -> None:
    profile = parse_candidate_fact_profile(approved_profile_payload())

    rows = candidate_fact_rows(profile)

    assert len(rows) == 4
    professional = next(
        row
        for row in rows
        if row["fact_key"] == "employment.synthetic.engineering-skill"
    )
    assert professional["approval_status"] == "approved"
    assert professional["statement"].startswith("Synthetic professional")
    assert professional["fact_payload"]["approved_by"] == "jens"


def test_rejects_approved_profile_without_approver() -> None:
    payload = approved_profile_payload()
    payload["approved_by"] = None

    with pytest.raises(ValueError, match="approved_by"):
        parse_candidate_fact_profile(payload)


def test_rejects_approved_profile_without_approved_fact() -> None:
    payload = approved_profile_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    for fact in facts:
        assert isinstance(fact, dict)
        fact["approval_status"] = "proposed"
        fact["approved_by"] = None
        fact["approved_at"] = None

    with pytest.raises(ValueError, match="at least one approved fact"):
        parse_candidate_fact_profile(payload)


def test_rejects_approved_fact_without_fact_approval_metadata() -> None:
    payload = approved_profile_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    first = facts[0]
    assert isinstance(first, dict)
    first["approved_at"] = None

    with pytest.raises(ValueError, match="approved_at"):
        parse_candidate_fact_profile(payload)


def test_rejects_nonapproved_fact_with_approval_metadata() -> None:
    payload = approved_profile_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    first = facts[0]
    assert isinstance(first, dict)
    first["approval_status"] = "proposed"

    with pytest.raises(ValueError, match="only allowed for approved facts"):
        parse_candidate_fact_profile(payload)


def test_rejects_naive_profile_approval_timestamp() -> None:
    payload = approved_profile_payload()
    payload["approved_at"] = "2026-08-05T10:10:00"

    with pytest.raises(ValueError, match="timezone"):
        parse_candidate_fact_profile(payload)


def test_rejects_portfolio_fact_without_repository_provenance() -> None:
    payload = approved_profile_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    portfolio = next(
        fact
        for fact in facts
        if isinstance(fact, dict)
        and fact["evidence_class"] == "portfolio_implementation"
    )
    portfolio["provenance"] = provenance("operator_assertion")

    with pytest.raises(ValueError, match="repository provenance"):
        parse_candidate_fact_profile(payload)


def test_rejects_professional_fact_without_employment_provenance() -> None:
    payload = approved_profile_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    professional = next(
        fact
        for fact in facts
        if isinstance(fact, dict)
        and fact["evidence_class"] == "professional_employment"
    )
    professional["provenance"] = provenance("repository")

    with pytest.raises(ValueError, match="employment provenance"):
        parse_candidate_fact_profile(payload)


def test_rejects_target_direction_without_not_capability_marker() -> None:
    payload = approved_profile_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    target = next(
        fact
        for fact in facts
        if isinstance(fact, dict) and fact["evidence_class"] == "target_direction"
    )
    target["limitations"] = ["synthetic_test_fixture"]

    with pytest.raises(ValueError, match="not_capability_evidence"):
        parse_candidate_fact_profile(payload)


def test_rejects_planned_capability_without_not_capability_marker() -> None:
    payload = approved_profile_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    planned = next(
        fact
        for fact in facts
        if isinstance(fact, dict) and fact["evidence_class"] == "planned_capability"
    )
    planned["limitations"] = []

    with pytest.raises(ValueError, match="not_capability_evidence"):
        parse_candidate_fact_profile(payload)


def test_rejects_duplicate_fact_keys() -> None:
    payload = approved_profile_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    duplicate = deepcopy(facts[0])
    facts.append(duplicate)

    with pytest.raises(ValueError, match="fact keys must be unique"):
        parse_candidate_fact_profile(payload)


def test_rejects_duplicate_capability_tags() -> None:
    payload = approved_profile_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    first = facts[0]
    assert isinstance(first, dict)
    first["capability_tags"] = ["python", "Python"]

    with pytest.raises(ValueError, match="duplicate value"):
        parse_candidate_fact_profile(payload)


def test_rejects_inverted_validity_range() -> None:
    payload = approved_profile_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    first = facts[0]
    assert isinstance(first, dict)
    first["valid_from"] = "2026-08-05"
    first["valid_until"] = "2026-08-04"

    with pytest.raises(ValueError, match="validity range is inverted"):
        parse_candidate_fact_profile(payload)


def test_rejects_unknown_profile_keys() -> None:
    payload = approved_profile_payload()
    payload["private_notes"] = "must not silently enter the contract"

    with pytest.raises(ValueError, match="unsupported keys"):
        parse_candidate_fact_profile(payload)


def test_rejects_unknown_fact_keys() -> None:
    payload = approved_profile_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    first = facts[0]
    assert isinstance(first, dict)
    first["score"] = 100

    with pytest.raises(ValueError, match="unsupported keys"):
        parse_candidate_fact_profile(payload)


def test_rejects_invalid_json() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        load_candidate_fact_profile_json("{not-json")


def test_synthetic_template_is_valid_draft_and_contains_no_personal_facts() -> None:
    profile = parse_candidate_fact_profile(TEMPLATE)
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")

    assert profile.status == "draft"
    assert profile.approved_facts == ()
    assert profile.profile_version == "replace-with-private-version"
    assert "jens" not in template_text.casefold()
    assert "automotive" not in template_text.casefold()
    assert "product owner" not in template_text.casefold()
    assert "example.invalid" in template_text


def test_schema_declares_private_profiles_facts_and_revisions() -> None:
    assert "CREATE TABLE IF NOT EXISTS candidate_fact_profiles" in MIGRATION
    assert "CREATE TABLE IF NOT EXISTS candidate_facts" in MIGRATION
    assert "CREATE TABLE IF NOT EXISTS candidate_fact_profile_revisions" in MIGRATION
    assert "payload_sha256 ~ '^[0-9a-f]{64}$'" in MIGRATION
    assert "source_type = 'local_private_json'" in MIGRATION
    assert "previous_payload JSONB" in MIGRATION
    assert "next_payload JSONB NOT NULL" in MIGRATION
    assert "UPDATE job_product_assessments" not in MIGRATION
    assert "INSERT INTO job_product_assessments" not in MIGRATION


def test_runner_is_plan_only_by_default_and_approval_gated() -> None:
    assert APPROVAL_TOKEN == "CANDIDATE-FACT-PROFILE-IMPORT-001"
    assert 'parser.add_argument("--apply", action="store_true")' in RUNNER
    assert "args.approval_token != APPROVAL_TOKEN" in RUNNER
    assert "only an approved candidate fact profile may be applied" in RUNNER
    assert "applied_by must match the profile approver" in RUNNER
    assert "pg_advisory_xact_lock" in RUNNER
    assert "content changed without a new profile_version" in RUNNER


def test_runner_is_revisioned_idempotent_and_redacted() -> None:
    assert "INSERT INTO candidate_fact_profile_revisions" in RUNNER
    assert "ON CONFLICT (profile_key, revision_key) DO NOTHING" in RUNNER
    assert "previous[\"payload_sha256\"] == profile.payload_sha256" in RUNNER
    assert "return False, False" in RUNNER
    assert '"personal_statements_emitted": False' in RUNNER
    assert '"provenance_references_emitted": False' in RUNNER
    assert '"capability_fit_decision_created": False' in RUNNER
    assert '"review_output_only_not_pipeline_input": True' in RUNNER


def test_runner_preserves_all_product_and_runtime_boundaries() -> None:
    assert '"weekly_hours_inferred": False' in RUNNER
    assert '"ranking_scores_created": False' in RUNNER
    assert '"hard_filter_pass_forced": False' in RUNNER
    assert '"network_requests": 0' in RUNNER
    assert '"provider_requests": 0' in RUNNER
    assert '"source_or_scheduler_activation": False' in RUNNER
    assert '"application_action_performed": False' in RUNNER
    assert "requests.get" not in RUNNER
    assert "requests.post" not in RUNNER
    assert "job_product_assessments" not in RUNNER


def test_capability_evidence_class_set_excludes_direction_and_planning() -> None:
    assert "professional_employment" in CAPABILITY_EVIDENCE_CLASSES
    assert "portfolio_implementation" in CAPABILITY_EVIDENCE_CLASSES
    assert "target_direction" not in CAPABILITY_EVIDENCE_CLASSES
    assert "planned_capability" not in CAPABILITY_EVIDENCE_CLASSES
    assert "operator_preference" not in CAPABILITY_EVIDENCE_CLASSES
