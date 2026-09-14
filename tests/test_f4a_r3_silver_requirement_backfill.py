from scripts import run_f4a_r3_silver_requirement_backfill as backfill


def test_origin_unavailable_payload_is_explicit_and_authority_free() -> None:
    payload = backfill._unavailable_payload(
        source_url="https://jobs.example.test/404",
        reason="preview detail returned HTTP 404",
    )

    assert payload["parser_family"] == "origin_unavailable"
    assert payload["raw_html_persisted"] is False
    assert payload["origin_unavailable_reason"] == "preview detail returned HTTP 404"
    assert all(
        field["status"] == "origin_unavailable"
        for field in payload["fields"].values()
    )
    assert payload["authority"]["ranking_authority"] is False
    assert payload["authority"]["application_authority"] is False


def test_plan_keeps_blockers_separate_from_unavailable_longtail(monkeypatch) -> None:
    rows = [
        {"silver_job_id": 1, "source_name": "generic_origin:a"},
        {"silver_job_id": 2, "source_name": "generic_origin:b"},
        {"silver_job_id": 3, "source_name": "generic_origin:c"},
    ]

    def fake_proposal(row):
        silver_job_id = int(row["silver_job_id"])
        if silver_job_id == 3:
            raise backfill.BackfillStop("unsafe redirect")
        unavailable = silver_job_id == 2
        status = "origin_unavailable" if unavailable else "observed_structured"
        return {
            "silver_job_id": silver_job_id,
            "raw_job_id": silver_job_id + 100,
            "source_name": row["source_name"],
            "source_url": f"https://example.test/{silver_job_id}",
            "title": "Data Engineer",
            "company_name": "Example",
            "parser_family": "origin_unavailable" if unavailable else "schema_org_json_ld",
            "structured_jobposting_found": not unavailable,
            "origin_unavailable": unavailable,
            "field_status_counts": {status: 6},
            "evidence_hash": f"hash-{silver_job_id}",
            "previous_evidence_hash": None,
            "would_change": True,
            "payload": {
                "fields": {
                    "job_skills": {"status": status, "values": ["Python"] if not unavailable else []}
                }
            },
        }

    monkeypatch.setattr(backfill, "_proposal", fake_proposal)
    report = backfill.build_plan(rows)

    assert report["candidate_count"] == 3
    assert report["proposal_count"] == 2
    assert report["blocked_count"] == 1
    assert report["origin_unavailable_count"] == 1
    assert report["reachable_count"] == 1
    assert report["reachable_with_any_observed_requirement_ratio"] == 1.0
    assert report["would_change_count"] == 2
