import pytest

from scripts import run_f5_application_tracking_product_proof as proof


def _payload() -> dict[str, object]:
    return {
        "schema_version": "job_application_pipeline.f5.application_tracking.v2",
        "available": True,
        "summary": {
            "application_count": 1,
            "submitted_count": 0,
            "mailbox_discovered_count": 1,
            "observed_status_count": 1,
            "attention_count": 1,
            "unmatched_candidate_count": 0,
            "stage_counts": {"applied": 1},
        },
        "applications": [
            {
                "application_id": 1,
                "silver_job_id": None,
                "job_link_status": "external",
                "authoritative_stage": "prepared",
                "observed_stage": "applied",
                "effective_stage": "applied",
                "evidence_candidates": [
                    {
                        "authority": "evidence_only",
                        "evidence": {"reason_code": "deterministic_ack"},
                    }
                ],
            }
        ],
        "boundaries": {
            "read_only_projection": True,
            "mailbox_observed_status_is_separate_from_authoritative_history": True,
            "unknown_job_application_supported": True,
            "gmail_credentials_present": False,
            "raw_mail_body_exposed": False,
            "email_send_authority": False,
            "automatic_application_submission": False,
        },
    }


def test_tracking_proof_accepts_mailbox_first_bounded_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(proof, "load_application_tracking_payload", _payload)

    report = proof.build_report(source_sha="abc123")

    assert report["proof"] == "PASS"
    assert report["source_sha"] == "abc123"
    assert report["summary"]["mailbox_discovered_count"] == 1
    assert report["summary"]["observed_status_count"] == 1


def test_tracking_proof_rejects_raw_mail_exposure(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _payload()
    payload["applications"][0]["evidence_candidates"][0]["evidence"]["raw_body"] = "secret"
    monkeypatch.setattr(proof, "load_application_tracking_payload", lambda: payload)

    with pytest.raises(RuntimeError, match="F5_TRACKING_RAW_MAIL_EXPOSED"):
        proof.build_report(source_sha="abc123")


def test_tracking_proof_rejects_candidate_authority_escalation(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _payload()
    payload["applications"][0]["evidence_candidates"][0]["authority"] = "lifecycle_authority"
    monkeypatch.setattr(proof, "load_application_tracking_payload", lambda: payload)

    with pytest.raises(RuntimeError, match="F5_TRACKING_CANDIDATE_AUTHORITY_INVALID"):
        proof.build_report(source_sha="abc123")


def test_tracking_proof_rejects_unknown_job_marked_as_linked(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _payload()
    payload["applications"][0]["job_link_status"] = "linked"
    monkeypatch.setattr(proof, "load_application_tracking_payload", lambda: payload)

    with pytest.raises(RuntimeError, match="F5_TRACKING_UNKNOWN_JOB_LINK_STATUS_INVALID"):
        proof.build_report(source_sha="abc123")
