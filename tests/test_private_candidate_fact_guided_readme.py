from __future__ import annotations

from src.search_intelligence.candidate_fact_authoring_pack import build_private_readme


def test_private_readme_routes_operator_to_guided_authoring() -> None:
    readme = build_private_readme(profile_version="eon-authoring-draft-v1")

    assert "Do not edit the nested JSON files directly" in readme
    assert "scripts.author_private_candidate_facts" in readme
    assert "SPEICHERN" in readme
    assert "New facts remain `proposed`" in readme
    assert "scripts.import_private_candidate_fact_profile" in readme
    assert "scripts.run_private_candidate_fact_authoring_integrity" in readme
    assert "Do not copy facts automatically from chat memory" in readme
