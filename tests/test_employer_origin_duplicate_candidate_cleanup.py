from scripts.run_employer_origin_duplicate_candidate_cleanup import (
    CleanupCandidate,
    candidate_snapshot,
    normalize_candidate_url,
    validate_cleanup_pair,
)


def candidate(
    candidate_id: int,
    *,
    company_key: str = "dirk_rossmann",
    source_name_candidate: str = "dirk_rossmann:discovery",
    candidate_url: str | None = None,
    status: str = "discovery",
) -> CleanupCandidate:
    return CleanupCandidate(
        id=candidate_id,
        company_key=company_key,
        company_name="Dirk Rossmann GmbH",
        candidate_url=candidate_url,
        source_name_candidate=source_name_candidate,
        source_family_candidate="dirk_rossmann",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status=status,
        risk_level="unknown",
        notes=None,
    )


def test_normalize_candidate_url_treats_none_like_values_as_missing() -> None:
    assert normalize_candidate_url(None) is None
    assert normalize_candidate_url("") is None
    assert normalize_candidate_url("   ") is None
    assert normalize_candidate_url("None") is None
    assert normalize_candidate_url("null") is None
    assert normalize_candidate_url("https://jobs.example.com/") == "https://jobs.example.com/"


def test_validate_cleanup_pair_accepts_exact_duplicate_with_missing_url() -> None:
    errors = validate_cleanup_pair(
        keep=candidate(3, candidate_url=None),
        duplicate=candidate(21, candidate_url="None", status="abort_documented"),
    )

    assert errors == []


def test_validate_cleanup_pair_rejects_different_identity() -> None:
    errors = validate_cleanup_pair(
        keep=candidate(3),
        duplicate=candidate(21, source_name_candidate="other:discovery", status="abort_documented"),
    )

    assert "candidate source_name_candidate values differ" in errors


def test_validate_cleanup_pair_rejects_protected_active_candidate() -> None:
    errors = validate_cleanup_pair(
        keep=candidate(3),
        duplicate=candidate(21, status="active_controlled"),
    )

    assert "duplicate candidate has protected status: active_controlled" in errors


def test_validate_cleanup_pair_rejects_usable_duplicate_url() -> None:
    errors = validate_cleanup_pair(
        keep=candidate(3),
        duplicate=candidate(21, candidate_url="https://jobs.rossmann.de/", status="abort_documented"),
    )

    assert "duplicate candidate has a usable candidate_url; cleanup requires manual design review" in errors


def test_candidate_snapshot_preserves_cleanup_evidence_fields() -> None:
    snapshot = candidate_snapshot(candidate(21, candidate_url="None", status="abort_documented"))

    assert snapshot["id"] == 21
    assert snapshot["company_key"] == "dirk_rossmann"
    assert snapshot["candidate_url"] == "None"
    assert snapshot["status"] == "abort_documented"
