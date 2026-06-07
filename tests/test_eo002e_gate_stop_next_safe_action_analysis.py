from __future__ import annotations

from pathlib import Path

from src.search_intelligence.eo002e_gate_stop_next_safe_analysis import (
    ActionRunSnapshot,
    CandidateSnapshot,
    GateReviewSnapshot,
    UrlFinderEvidence,
    analyze_candidate,
    load_url_finder_evidence,
    report_payload,
    summarize_analyses,
)

SCRIPT = Path("scripts/run_eo002e_gate_stop_next_safe_action_analysis.py")
DOC = Path("docs/planning/eo002e_gate_stop_next_safe_action_evidence_analysis.md")
SENSOR_DOC = Path("docs/planning/sensor001_ba_remote_nationwide_coverage_validation.md")


def test_validated_url_report_without_persisted_url_requires_sz1_review() -> None:
    candidate = CandidateSnapshot(
        candidate_id=36,
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        status="discovery",
        candidate_url="",
        risk_level="medium",
    )
    url_finder = UrlFinderEvidence(
        company_key="hannover_ruck",
        selected_url="https://jobs.hannover-re.com/",
        success_tier="A",
        decision="origin_url_candidate_selected",
        confidence_score=1.0,
        false_negative_candidate=True,
    )

    analysis = analyze_candidate(candidate, [], url_finder=url_finder)

    assert analysis.effective_origin_url == "https://jobs.hannover-re.com/"
    assert analysis.effective_origin_url_source == "validated_url_finder_report"
    assert analysis.recommended_next_safe_action == "review_candidate_url_write_from_validated_report"
    assert analysis.safety_zone == "SZ1_CANDIDATE_METADATA"
    assert analysis.manual_review_required is True
    assert analysis.false_negative_candidate is True


def test_persisted_url_with_missing_early_gate_recommends_initial_gate_review() -> None:
    candidate = CandidateSnapshot(
        candidate_id=37,
        company_key="e_on_grid_solutions",
        company_name="E.ON Grid Solutions GmbH",
        status="discovery",
        candidate_url="https://jobs.eon.com/en",
        risk_level="medium",
    )

    analysis = analyze_candidate(candidate, [])

    assert analysis.effective_origin_url_source == "persisted_candidate_url"
    assert analysis.first_missing_step == "candidate_url_persistence"
    assert analysis.recommended_next_safe_action == "run_initial_gate_review_plan"
    assert analysis.safety_zone == "SZ2_EVIDENCE_AND_GATES"


def test_detail_evidence_stop_is_classified_as_detail_discovery_gap() -> None:
    candidate = CandidateSnapshot(
        candidate_id=2,
        company_key="hdi",
        company_name="HDI Group",
        status="discovery",
        candidate_url="https://careers.hdi.group/jobs",
    )
    gates = [
        GateReviewSnapshot("candidate_url_persistence", 1, "passed", "continue", None),
        GateReviewSnapshot("technical_reachability_gate", 2, "passed", "continue", None),
        GateReviewSnapshot("risk_gate", 3, "passed", "continue", None),
        GateReviewSnapshot("relevance_gate", 4, "passed", "continue", None),
        GateReviewSnapshot(
            "detail_evidence_gate",
            8,
            "manual_review_required",
            "manual_review_required",
            "bounded repair found no concrete detail pages with profile and target/remote signals",
        ),
    ]

    analysis = analyze_candidate(candidate, gates)

    assert analysis.gate_stop == "detail_evidence_gate"
    assert analysis.gate_stop_category == "detail_discovery_gap"
    assert analysis.gate_stop_terminal is False
    assert analysis.recommended_next_safe_action == "run_detail_evidence_discovery_plan"


def test_summary_counts_recommendations_and_boundaries() -> None:
    analyses = [
        analyze_candidate(
            CandidateSnapshot(1, "a", "A", "discovery", ""),
            [],
            url_finder=UrlFinderEvidence("a", "https://jobs.example.com/", "A", "origin_url_candidate_selected", 0.9),
        ),
        analyze_candidate(CandidateSnapshot(2, "b", "B", "discovery", None), []),
    ]

    summary = summarize_analyses(analyses)

    assert summary.candidate_count == 2
    assert summary.report_selected_url_only_count == 1
    assert summary.no_origin_url_count == 1
    assert summary.boundary["no_gate_write"] is True
    assert summary.recommendation_counts["review_candidate_url_write_from_validated_report"] == 1


def test_url_finder_report_loader_reads_metrics(tmp_path: Path) -> None:
    report = tmp_path / "eo002b.json"
    report.write_text(
        """
        {
          "metrics": [
            {
              "company_key": "hannover_ruck",
              "selected_url": "https://jobs.hannover-re.com/",
              "success_tier": "A",
              "decision": "origin_url_candidate_selected",
              "confidence_score": 1.0,
              "alternative_url_count": 6,
              "rejected_url_count": 5,
              "false_negative_candidate": true
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    evidence = load_url_finder_evidence([report])

    assert evidence["hannover_ruck"].selected_url == "https://jobs.hannover-re.com/"
    assert evidence["hannover_ruck"].alternative_url_count == 6
    assert evidence["hannover_ruck"].false_negative_candidate is True


def test_report_payload_and_markdown_ready_fields() -> None:
    analysis = analyze_candidate(
        CandidateSnapshot(36, "hannover_ruck", "Hannover Rück SE", "discovery", ""),
        [],
        url_finder=UrlFinderEvidence("hannover_ruck", "https://jobs.hannover-re.com/", "A", "origin_url_candidate_selected", 1.0),
        action_runs=[ActionRunSnapshot("run_next_safe_action", "success")],
    )
    payload = report_payload([analysis], benchmark_label="eo002e_smoke", source_url_finder_reports=["eo002b.json"])

    assert payload["campaign"] == "EO-002E Gate Stop / Next-Safe-Action Evidence Analysis"
    assert payload["summary"]["boundary"]["no_candidate_url_write"] is True
    assert payload["source_url_finder_reports"] == ["eo002b.json"]


def test_script_and_docs_preserve_freeze_boundaries() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    sensor_doc = SENSOR_DOC.read_text(encoding="utf-8")

    assert "read-only" in script.lower()
    assert "INSERT INTO" not in script
    assert "UPDATE " not in script
    assert "no candidate URL write" in doc
    assert "SENSOR-001" in sensor_doc
    assert "must not immediately activate" in sensor_doc
