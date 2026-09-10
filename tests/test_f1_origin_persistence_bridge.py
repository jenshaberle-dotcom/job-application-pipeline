from __future__ import annotations

from pathlib import Path

from scripts.run_f1_origin_persistence_bridge import BOUNDARY, build_cand001_replay


def test_f1_bridge_replays_selected_url_as_evidence_not_writer_authority() -> None:
    rows = build_cand001_replay(
        company_key="example",
        company_name="Example GmbH",
        selected_url="https://example.com/careers",
    )

    assert rows == [
        {
            "company_key": "example",
            "url": "https://example.com/careers",
            "title": "Example GmbH careers",
            "snippet": (
                "F1 bounded official-domain/career-surface discovery selected this "
                "URL; CAND-001 must independently revalidate it before persistence."
            ),
            "query": "f1-origin-jobspace-replay",
            "provider": "f1_jobspace_bridge",
        }
    ]
    assert BOUNDARY["f1_discovery_is_evidence_only"] is True
    assert BOUNDARY["cand001_is_sole_candidate_url_writer"] is True
    assert BOUNDARY["cand001_revalidates_selected_url"] is True
    assert BOUNDARY["no_source_activation"] is True


def test_f1_bridge_source_contains_no_direct_candidate_url_update() -> None:
    source = Path("scripts/run_f1_origin_persistence_bridge.py").read_text(
        encoding="utf-8"
    )

    assert "UPDATE employer_origin_source_candidates" not in source
    assert "run_cand001" in source
    assert "--apply requires --approval-token" in source
