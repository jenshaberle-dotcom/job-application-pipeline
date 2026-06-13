from src.search_intelligence.generic009a_positive_proof_inventory import build_positive_proof_inventory
from src.search_intelligence.generic009b_positive_proof_evidence import (
    build_positive_proof_evidence_report,
    build_positive_proof_expand003_report,
    build_positive_proof_rows_from_inventory,
)


def _row(company_key, company_name, candidate_url, notes, status="discovery", risk_level="unknown"):
    return {
        "company_key": company_key,
        "company_name": company_name,
        "candidate_url": candidate_url,
        "source_name_candidate": f"{company_key}:discovery",
        "source_family_candidate": company_key,
        "source_target_candidate": "hannover",
        "source_type_candidate": "employer_origin_career_site",
        "status": status,
        "risk_level": risk_level,
        "notes": notes,
    }


def _inventory():
    create = "source_decision=create_candidate_recommended; reviewed_by=jens"
    manual = "source_decision=manual_review_required; reviewed_by=jens"
    return build_positive_proof_inventory(
        [
            _row("deloitte", "Deloitte", "https://careers.deloitte.com/", create, "manual_review_required"),
            _row("computacenter", "Computacenter AG & Co. oHG", "https://jobs.computacenter.com/", create),
            _row("x1f", "x1F GmbH", None, create),
            _row("ivv", "ivv GmbH", None, create),
            _row("msg_systems", "msg systems ag", None, create),
            _row("e_on_grid_solutions", "E.ON Grid Solutions GmbH", "https://jobs.eon.com/en", manual),
            _row("hannover_ruck", "Hannover Rück SE", "https://jobs.hannover-re.com/", manual),
            _row("adesso", "adesso SE", "https://jobs.adesso-group.com/", "bounded origin recovery"),
            _row("deutsche_bahn", "Deutsche Bahn AG", "https://db.jobs/de-de/jobs", "blocked", "abort_documented", "blocked"),
        ]
    )


def test_positive_proof_evidence_selects_balanced_bounded_controls() -> None:
    report = build_positive_proof_evidence_report(_inventory(), generated_at="2026-06-13T01:30:00+00:00")

    assert report["overall_status"] == "ready_for_generic005_positive_proof_rerun"
    assert report["summary"]["accepted_positive_control_count"] == 8
    assert "provider_backed_origin_coverage" in report["summary"]["missing_gap_ids"]
    assert "deutsche_bahn" not in report["summary"]["positive_control_keys"]


def test_positive_proof_expand003_replaces_broad_artifact_for_generics_only() -> None:
    rows = build_positive_proof_rows_from_inventory(_inventory())
    expand003 = {
        "schema_version": "expand003.candidate_review_delta_report.v1",
        "candidate_review_items": [{"company_key": f"broad_{index}"} for index in range(52)],
    }

    augmented = build_positive_proof_expand003_report(expand003, rows)

    assert len(augmented["candidate_review_items"]) == 8
    assert augmented["generic009b_benchmark_augmentation"]["original_candidate_review_item_count"] == 52
    assert augmented["generic009b_benchmark_augmentation"]["boundary"] == "benchmark_review_artifact_only_no_candidate_or_gate_write"


def test_selection_skips_weak_rows_without_positive_control_coverage() -> None:
    create = "source_decision=create_candidate_recommended; reviewed_by=jens"
    manual = "source_decision=manual_review_required; reviewed_by=jens"
    inventory = build_positive_proof_inventory(
        [
            _row("deloitte", "Deloitte", "https://careers.deloitte.com/", create, "manual_review_required"),
            _row("computacenter", "Computacenter AG & Co. oHG", "https://jobs.computacenter.com/", create),
            _row("clarios_germany", "Clarios Germany GmbH & Co. KG", "https://jobs.clarios.com/", create),
            _row("materna_information_communications", "Materna Information & Communications SE", None, create),
            _row("x1f", "x1F GmbH", None, create),
            _row("e_on_grid_solutions", "E.ON Grid Solutions GmbH", "https://jobs.eon.com/en", manual, risk_level="medium"),
            _row("hannover_ruck", "Hannover Rück SE", "https://jobs.hannover-re.com/", manual, risk_level="medium"),
            _row("vhv_gruppe", "VHV Gruppe", None, manual, risk_level="medium"),
            _row("adesso", "adesso SE", "https://jobs.adesso-group.com/", "bounded origin recovery"),
        ]
    )

    rows = build_positive_proof_rows_from_inventory(inventory)
    accepted = [row for row in rows if row.status == "accepted_positive_control"]

    assert "vhv_gruppe" not in [row.company_key for row in accepted]
    assert "adesso" in [row.company_key for row in accepted]
    weak_count = sum("weak_candidate_count" in row.candidate_gap_coverage for row in accepted)
    assert weak_count >= 3
