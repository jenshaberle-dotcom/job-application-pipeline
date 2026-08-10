import json

import pytest

import scripts.review_silver_selection as review_silver_selection
from src.silver.repository import SilverJobRepository


class PreviewCursor:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []
        self.last_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(
        self,
        sql: str,
        params: tuple[object, ...] | None = None,
    ) -> None:
        self.last_sql = sql
        self.calls.append((sql, params))

    def fetchone(self) -> dict | None:
        if self.last_sql == "SHOW transaction_read_only":
            return {"transaction_read_only": "on"}
        return None

    def fetchall(self) -> list[dict]:
        return self.rows


class PreviewConnection:
    def __init__(self, cursor: PreviewCursor) -> None:
        self.preview_cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def cursor(self) -> PreviewCursor:
        return self.preview_cursor


def test_repository_preview_enforces_read_only_and_exact_run() -> None:
    expected_rows = [
        {
            "id": 31563,
            "source_name": "computacenter:discovery",
            "external_job_id": "562378801:b7365bdf1b62",
            "source_url": "https://jobs.computacenter.com/job/example/562378801/",
            "raw_data": {"source_type": "employer_origin_career_site"},
        }
    ]
    cursor = PreviewCursor(expected_rows)
    connection = PreviewConnection(cursor)
    repository = SilverJobRepository.__new__(SilverJobRepository)
    repository.get_connection = lambda: connection

    rows, transaction_read_only = repository.preview_unprocessed_raw_jobs(
        limit=3,
        source_patterns=["computacenter:discovery"],
        ingestion_run_id=2596,
    )

    assert rows == expected_rows
    assert transaction_read_only == "on"
    assert cursor.calls[0] == ("SET TRANSACTION READ ONLY", None)
    assert cursor.calls[1] == ("SHOW transaction_read_only", None)
    selection_sql, selection_params = cursor.calls[2]
    assert "r.source_name = %s" in selection_sql
    assert "r.ingestion_run_id = %s" in selection_sql
    assert selection_params == ("computacenter:discovery", 2596, 3)


def test_main_emits_read_only_exact_run_manifest(monkeypatch, capsys) -> None:
    raw_job = {
        "id": 31563,
        "source_name": "computacenter:discovery",
        "external_job_id": "562378801:b7365bdf1b62",
        "source_url": "https://jobs.computacenter.com/job/example/562378801/",
        "raw_data": {"source_type": "employer_origin_career_site"},
    }
    captured: dict[str, object] = {}

    class FakeRepository:
        def preview_unprocessed_raw_jobs(
            self,
            limit: int,
            source_patterns: list[str],
            ingestion_run_id: int | None,
        ) -> tuple[list[dict], str]:
            captured.update(
                limit=limit,
                source_patterns=source_patterns,
                ingestion_run_id=ingestion_run_id,
            )
            return [raw_job], "on"

    monkeypatch.setattr(
        review_silver_selection,
        "SilverJobRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        review_silver_selection,
        "get_role_matches",
        lambda raw: ["data_engineer"],
    )
    monkeypatch.setattr(
        review_silver_selection,
        "get_skill_matches",
        lambda raw: ["python"],
    )
    monkeypatch.setattr(
        review_silver_selection,
        "get_accessibility_matches",
        lambda raw: ["hannover"],
    )
    monkeypatch.setattr(
        review_silver_selection,
        "is_relevant_for_silver",
        lambda raw: True,
    )
    monkeypatch.setattr(
        review_silver_selection,
        "get_silver_decision_reason",
        lambda raw: "relevant_for_silver",
    )
    monkeypatch.setattr(
        review_silver_selection,
        "transform_raw_job_to_silver",
        lambda raw: {
            "raw_job_id": raw["id"],
            "source_url": raw["source_url"],
            "title": "Data Engineer",
            "company_name": "Computacenter",
            "city": "Hannover",
            "postal_code": None,
            "country": "DE",
            "canonical_source_type": "employer_origin_career_site",
            "canonical_key_candidate": "computacenter :: data engineer :: hannover",
        },
    )

    review_silver_selection.main(
        [
            "--source",
            "computacenter:discovery",
            "--ingestion-run-id",
            "2596",
            "--limit",
            "3",
        ]
    )

    manifest = json.loads(capsys.readouterr().out)
    assert captured == {
        "limit": 3,
        "source_patterns": ["computacenter:discovery"],
        "ingestion_run_id": 2596,
    }
    assert manifest["transaction_read_only"] == "on"
    assert manifest["selection"]["selected_raw_job_ids"] == [31563]
    assert manifest["summary"] == {
        "relevant_count": 1,
        "non_relevant_count": 0,
    }
    assert manifest["rows"][0]["transformed_if_relevant"]["title"] == "Data Engineer"
    assert manifest["boundary"]["database_writes"] is False
    assert manifest["boundary"]["network_requests"] is False


def test_non_relevant_preview_never_transforms(monkeypatch) -> None:
    raw_job = {
        "id": 31564,
        "source_name": "computacenter:discovery",
        "external_job_id": "1054982701:a82bbb7d59df",
        "source_url": "https://jobs.computacenter.com/job/example/1054982701/",
        "raw_data": {"source_type": "employer_origin_career_site"},
    }

    monkeypatch.setattr(
        review_silver_selection,
        "get_role_matches",
        lambda raw: [],
    )
    monkeypatch.setattr(
        review_silver_selection,
        "get_skill_matches",
        lambda raw: [],
    )
    monkeypatch.setattr(
        review_silver_selection,
        "get_accessibility_matches",
        lambda raw: [],
    )
    monkeypatch.setattr(
        review_silver_selection,
        "is_relevant_for_silver",
        lambda raw: False,
    )
    monkeypatch.setattr(
        review_silver_selection,
        "get_silver_decision_reason",
        lambda raw: "missing_role_or_skill_signal",
    )

    def fail_transform(raw: dict) -> dict:
        pytest.fail("non-relevant rows must not be transformed")

    monkeypatch.setattr(
        review_silver_selection,
        "transform_raw_job_to_silver",
        fail_transform,
    )

    manifest = review_silver_selection.build_manifest(
        source="computacenter:discovery",
        ingestion_run_id=2596,
        limit=3,
        rows=[raw_job],
        transaction_read_only="on",
    )

    assert manifest["rows"][0]["relevant"] is False
    assert manifest["rows"][0]["transformed_if_relevant"] is None
    assert manifest["summary"] == {
        "relevant_count": 0,
        "non_relevant_count": 1,
    }


def test_manifest_rejects_missing_read_only_proof() -> None:
    with pytest.raises(RuntimeError, match="not read-only"):
        review_silver_selection.build_manifest(
            source=None,
            ingestion_run_id=None,
            limit=3,
            rows=[],
            transaction_read_only="off",
        )
