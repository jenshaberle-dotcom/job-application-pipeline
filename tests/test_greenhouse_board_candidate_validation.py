from pathlib import Path

from scripts import validate_greenhouse_board_candidates as validator
from src.connectors.base import RawJobRecord


def make_record(job_id: str, title: str, location: str = "Berlin") -> RawJobRecord:
    return RawJobRecord(
        source_name="greenhouse:contentful",
        external_job_id=job_id,
        source_url=f"https://boards.greenhouse.io/contentful/jobs/{job_id}",
        raw_data={
            "job": {
                "id": int(job_id),
                "title": title,
                "absolute_url": f"https://boards.greenhouse.io/contentful/jobs/{job_id}",
                "location": {"name": location},
                "offices": [{"name": location}],
            }
        },
    )


class FakeConnector:
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, board_token: str) -> None:
        self.board_token = board_token
        self.source_name = f"greenhouse:{board_token}"

    def fetch_jobs(self, profile, search_term):
        return (
            [
                make_record("1", "Senior Data Engineer", "Berlin"),
                make_record("2", "Customer Success Manager", "Remote"),
            ],
            f"{self.BASE_URL}/{self.board_token}/jobs",
        )


class FailingConnector(FakeConnector):
    def fetch_jobs(self, profile, search_term):
        raise RuntimeError("boom")


def test_default_candidate_selection_excludes_reserve() -> None:
    candidates = validator.select_candidates(candidate_keys=[], include_reserve=False)

    assert [candidate.board_token for candidate in candidates] == [
        "contentful",
        "commercetools",
    ]


def test_candidate_selection_can_include_reserve() -> None:
    candidates = validator.select_candidates(candidate_keys=[], include_reserve=True)

    assert [candidate.board_token for candidate in candidates] == [
        "contentful",
        "commercetools",
        "celonis",
    ]


def test_make_search_terms_assigns_stable_ids() -> None:
    terms = validator.make_search_terms(["Data Engineer", "Analytics Engineer"])

    assert [term.id for term in terms] == [1, 2]
    assert [term.search_term for term in terms] == [
        "Data Engineer",
        "Analytics Engineer",
    ]


def test_validate_candidate_matches_jobs_without_database_writes(monkeypatch) -> None:
    monkeypatch.setattr(validator, "GreenhouseConnector", FakeConnector)

    result = validator.validate_candidate(
        candidate=validator.CANDIDATES["contentful"],
        search_terms=validator.make_search_terms(["Data Engineer"]),
        match_limit=10,
    )

    assert result.board_token == "contentful"
    assert result.source_name == "greenhouse:contentful"
    assert result.status == "reachable"
    assert result.total_jobs == 2
    assert result.total_matching_jobs == 1
    assert len(result.matching_jobs) == 1
    assert result.matching_jobs[0].title == "Senior Data Engineer"
    assert result.matched_term_counts == {"Data Engineer": 1}
    assert result.recommendation == "candidate_for_controlled_profile_activation"


def test_validate_candidate_applies_match_limit(monkeypatch) -> None:
    monkeypatch.setattr(validator, "GreenhouseConnector", FakeConnector)

    result = validator.validate_candidate(
        candidate=validator.CANDIDATES["contentful"],
        search_terms=validator.make_search_terms(["Data Engineer"]),
        match_limit=0,
    )

    assert result.total_matching_jobs == 1
    assert len(result.matching_jobs) == 0
    assert result.matched_term_counts == {"Data Engineer": 1}
    assert result.recommendation == "candidate_for_controlled_profile_activation"


def test_validate_candidate_records_request_failures(monkeypatch) -> None:
    monkeypatch.setattr(validator, "GreenhouseConnector", FailingConnector)

    result = validator.validate_candidate(
        candidate=validator.CANDIDATES["contentful"],
        search_terms=validator.make_search_terms(["Data Engineer"]),
        match_limit=10,
    )

    assert result.status == "request_failed"
    assert result.total_matching_jobs == 0
    assert result.recommendation == "defer_source_request_failed"
    assert "RuntimeError: boom" == result.error


def test_classify_recommendation() -> None:
    match = validator.MatchedJobPreview(
        external_job_id="1",
        title="Data Engineer",
        location="Berlin",
        absolute_url="https://example.test",
        matched_terms=("Data Engineer",),
    )

    assert (
        validator.classify_recommendation("request_failed", 0, [])
        == "defer_source_request_failed"
    )
    assert validator.classify_recommendation("reachable", 0, []) == "defer_empty_board"
    assert (
        validator.classify_recommendation("reachable", 2, [])
        == "reachable_no_current_matches"
    )
    assert (
        validator.classify_recommendation("reachable", 2, [match])
        == "candidate_for_controlled_profile_activation"
    )


def test_write_exports_includes_headers(tmp_path: Path) -> None:
    result = validator.GreenhouseBoardValidationResult(
        board_token="contentful",
        source_name="greenhouse:contentful",
        selection_status="batch_1_candidate",
        requested_url="https://boards-api.greenhouse.io/v1/boards/contentful/jobs",
        status="reachable",
        total_jobs=0,
        total_matching_jobs=0,
        matching_jobs=(),
        matched_term_counts={},
        recommendation="defer_empty_board",
        rationale="test",
    )

    validator.write_exports(results=[result], output_dir=tmp_path)

    summary = tmp_path / "greenhouse_board_candidate_validation.csv"
    matches = tmp_path / "greenhouse_board_candidate_matches.csv"

    assert summary.exists()
    assert matches.exists()
    assert summary.read_text(encoding="utf-8").startswith("board_token,")
    assert matches.read_text(encoding="utf-8").startswith("board_token,")
