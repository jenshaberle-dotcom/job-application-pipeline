import pytest

import src.run_silver_jobs as run_silver_jobs
from src.run_silver_jobs import build_parser, resolve_source_patterns
from src.silver.repository import SilverJobRepository


def test_resolve_source_patterns_defaults_to_supported_sources() -> None:
    assert "enercity:%" in resolve_source_patterns(None)


def test_resolve_source_patterns_accepts_exact_enercity_source() -> None:
    assert resolve_source_patterns("enercity:discovery") == ["enercity:discovery"]


def test_resolve_source_patterns_accepts_enercity_family() -> None:
    assert resolve_source_patterns("enercity") == ["enercity:%"]


def test_ingestion_run_id_must_be_positive() -> None:
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(["--ingestion-run-id", "0"])

    assert exc_info.value.code == 2


def test_main_forwards_exact_source_and_ingestion_run(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeRepository:
        def load_unprocessed_raw_jobs(
            self,
            limit: int,
            source_patterns: list[str],
            ingestion_run_id: int | None,
        ) -> list[dict]:
            captured.update(
                limit=limit,
                source_patterns=source_patterns,
                ingestion_run_id=ingestion_run_id,
            )
            return []

    monkeypatch.setattr(run_silver_jobs, "SilverJobRepository", FakeRepository)

    run_silver_jobs.main(
        [
            "--source",
            "computacenter:discovery",
            "--ingestion-run-id",
            "2596",
            "--limit",
            "3",
        ]
    )

    assert captured == {
        "limit": 3,
        "source_patterns": ["computacenter:discovery"],
        "ingestion_run_id": 2596,
    }


class RecordingCursor:
    def __init__(self) -> None:
        self.sql = ""
        self.params: tuple[object, ...] = ()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.sql = sql
        self.params = params

    def fetchall(self) -> list[dict]:
        return []


class RecordingConnection:
    def __init__(self, cursor: RecordingCursor) -> None:
        self.recording_cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def cursor(self) -> RecordingCursor:
        return self.recording_cursor


def build_recording_repository() -> tuple[SilverJobRepository, RecordingCursor]:
    cursor = RecordingCursor()
    connection = RecordingConnection(cursor)
    repository = SilverJobRepository.__new__(SilverJobRepository)
    repository.get_connection = lambda: connection
    return repository, cursor


def test_repository_composes_source_and_ingestion_run_filters() -> None:
    repository, cursor = build_recording_repository()

    repository.load_unprocessed_raw_jobs(
        limit=3,
        source_patterns=["computacenter:discovery"],
        ingestion_run_id=2596,
    )

    assert "r.source_name = %s" in cursor.sql
    assert "r.ingestion_run_id = %s" in cursor.sql
    assert cursor.params == ("computacenter:discovery", 2596, 3)


def test_repository_preserves_source_only_selection() -> None:
    repository, cursor = build_recording_repository()

    repository.load_unprocessed_raw_jobs(
        limit=3,
        source_patterns=["computacenter:discovery"],
    )

    assert "r.source_name = %s" in cursor.sql
    assert "r.ingestion_run_id = %s" not in cursor.sql
    assert cursor.params == ("computacenter:discovery", 3)
