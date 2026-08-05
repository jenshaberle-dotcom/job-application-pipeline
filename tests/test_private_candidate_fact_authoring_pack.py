from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.search_intelligence.candidate_fact_authoring_pack import (
    EON_DESCRIPTION_SHA256,
    EON_SECTION_SHA256,
    EON_TAG_MAP_SHA256,
    OVERWRITE_TOKEN,
    PROFILE_FILENAME,
    README_FILENAME,
    WORKBOOK_FILENAME,
    build_empty_draft_profile,
    build_eon_authoring_workbook,
    build_private_readme,
    write_candidate_fact_authoring_pack,
)
from src.search_intelligence.candidate_fact_profile import parse_candidate_fact_profile


def test_generated_profile_is_valid_empty_draft() -> None:
    payload = build_empty_draft_profile(profile_version="eon-authoring-draft-v1")

    profile = parse_candidate_fact_profile(payload)

    assert profile.profile_key == "default"
    assert profile.profile_version == "eon-authoring-draft-v1"
    assert profile.status == "draft"
    assert profile.approved_by is None
    assert profile.approved_at is None
    assert profile.facts == ()


def test_workbook_is_exact_source_bound_and_contains_8_statements_26_tags() -> None:
    workbook = build_eon_authoring_workbook(
        profile_version="eon-authoring-draft-v1"
    )

    assert workbook["review_output_only_not_pipeline_input"] is True
    assert workbook["candidate_truth_state"] == "not_authored"
    assert workbook["source_binding"] == {
        "raw_job_id": 26342,
        "silver_job_id": 466,
        "description_sha256": EON_DESCRIPTION_SHA256,
        "section_sha256": EON_SECTION_SHA256,
        "tag_map_sha256": EON_TAG_MAP_SHA256,
        "statement_count": 8,
        "unique_tag_count": 26,
    }
    requirements = workbook["requirements"]
    assert len(requirements) == 8
    tags = {
        tag
        for requirement in requirements
        for tag in requirement["canonical_employer_tags"]
    }
    assert len(tags) == 26
    assert requirements[0]["statement_key"] == "eon-req-0530ca76d323450e"
    assert requirements[-1]["statement_key"] == "eon-req-07ac7c640b8105d6"


def test_workbook_contains_only_blank_operator_candidate_fields() -> None:
    workbook = build_eon_authoring_workbook(
        profile_version="eon-authoring-draft-v1"
    )

    assert workbook["instructions"]["employer_tags_are_candidate_truth"] is False
    assert (
        workbook["instructions"]["automatic_personal_fact_extraction_allowed"]
        is False
    )
    assert workbook["instructions"]["operator_must_author_every_candidate_fact"] is True
    assert workbook["instructions"]["target_directions_are_capability_evidence"] is False
    assert workbook["instructions"]["planned_capabilities_are_capability_evidence"] is False

    for requirement in workbook["requirements"]:
        assert requirement["operator_review"] == {
            "evidence_decision": "unreviewed",
            "candidate_fact_keys": [],
            "private_notes": "",
        }
        assert requirement["obligation_strength"] == "unspecified"


def test_private_readme_requires_operator_authorship_and_plan_only_validation() -> None:
    readme = build_private_readme(profile_version="eon-authoring-draft-v1")

    assert "Do not copy facts automatically from chat memory" in readme
    assert "Do not convert an employer requirement into a candidate claim" in readme
    assert "plan-only" in readme
    assert "scripts.import_private_candidate_fact_profile" in readme
    assert "Do not commit any file from this directory" in readme


def test_pack_writes_expected_files_and_redacted_defaults(tmp_path: Path) -> None:
    output_dir = tmp_path / "private_candidate_facts"

    pack = write_candidate_fact_authoring_pack(
        output_dir=output_dir,
        profile_version="eon-authoring-draft-v1",
    )

    assert pack.profile_path == output_dir / PROFILE_FILENAME
    assert pack.workbook_path == output_dir / WORKBOOK_FILENAME
    assert pack.readme_path == output_dir / README_FILENAME
    assert pack.statement_count == 8
    assert pack.unique_tag_count == 26

    profile_payload = json.loads(pack.profile_path.read_text(encoding="utf-8"))
    workbook_payload = json.loads(pack.workbook_path.read_text(encoding="utf-8"))
    assert profile_payload["facts"] == []
    assert profile_payload["status"] == "draft"
    assert workbook_payload["candidate_truth_state"] == "not_authored"
    assert pack.canonical_summary()["candidate_fact_statements_generated"] == 0
    assert pack.canonical_summary()["provenance_references_generated"] == 0
    assert pack.canonical_summary()["capability_claims_inferred"] == 0


def test_pack_refuses_existing_files_without_exact_token(tmp_path: Path) -> None:
    output_dir = tmp_path / "private_candidate_facts"
    write_candidate_fact_authoring_pack(
        output_dir=output_dir,
        profile_version="eon-authoring-draft-v1",
    )

    with pytest.raises(FileExistsError, match="refusing overwrite"):
        write_candidate_fact_authoring_pack(
            output_dir=output_dir,
            profile_version="eon-authoring-draft-v2",
        )

    with pytest.raises(ValueError, match="invalid private authoring pack overwrite token"):
        write_candidate_fact_authoring_pack(
            output_dir=tmp_path / "other-private-dir",
            profile_version="eon-authoring-draft-v2",
            overwrite_token="wrong-token",
        )


def test_exact_token_allows_controlled_overwrite(tmp_path: Path) -> None:
    output_dir = tmp_path / "private_candidate_facts"
    write_candidate_fact_authoring_pack(
        output_dir=output_dir,
        profile_version="eon-authoring-draft-v1",
    )

    pack = write_candidate_fact_authoring_pack(
        output_dir=output_dir,
        profile_version="eon-authoring-draft-v2",
        overwrite_token=OVERWRITE_TOKEN,
    )

    payload = json.loads(pack.profile_path.read_text(encoding="utf-8"))
    assert payload["profile_version"] == "eon-authoring-draft-v2"


def test_profile_version_validation_is_fail_closed() -> None:
    for value in ("", "V1", "contains spaces", "../escape", "ab"):
        with pytest.raises(ValueError, match="profile_version"):
            build_empty_draft_profile(profile_version=value)


def test_cli_has_no_database_network_import_or_fit_authority() -> None:
    source = Path(
        "scripts/create_private_candidate_fact_authoring_pack.py"
    ).read_text(encoding="utf-8")

    assert "psycopg" not in source
    assert "requests" not in source
    assert "get_database_config" not in source
    assert "apply_profile" not in source
    assert "capability_fit_decision_created: false" in source
    assert "candidate_fact_import_performed: false" in source
    assert "candidate_fact_approval_performed: false" in source
    assert "private_candidate_facts" in source
