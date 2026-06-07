from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_doc001i_old_diagram_paths_are_physically_archived() -> None:
    assert not (ROOT / "docs/diagrams/architecture.md").exists()
    assert not (ROOT / "docs/diagrams/bronze_data_model.md").exists()

    for path in [
        "docs/archive/diagrams/architecture.md",
        "docs/archive/diagrams/bronze_data_model.md",
        "docs/archive/diagrams/README.md",
    ]:
        assert (ROOT / path).exists()


def test_doc001i_archived_diagrams_have_current_replacements() -> None:
    architecture = read("docs/archive/diagrams/architecture.md")
    bronze = read("docs/archive/diagrams/bronze_data_model.md")
    archive_readme = read("docs/archive/diagrams/README.md")

    assert "Status: archived historical diagram" in architecture
    assert "docs/architecture/system_diagrams.md" in architecture
    assert "Status: archived historical diagram" in bronze
    assert "docs/database/schema_relationships.md" in bronze
    assert "Current replacement" in archive_readme


def test_doc001i_docs_navigation_points_to_archive_and_replacements() -> None:
    docs_readme = read("docs/README.md")
    archive_readme = read("docs/archive/README.md")
    path_status = read("docs/archive/documentation_path_status.md")
    truth_map = read("docs/architecture/current_truth_documentation_map.md")

    for phrase in [
        "docs/archive/diagrams/",
        "docs/architecture/system_diagrams.md",
        "docs/database/schema_relationships.md",
    ]:
        assert phrase in docs_readme + archive_readme + path_status + truth_map

    assert "Completed physical archive moves" in path_status
    assert "DOC-001I physical archive note" in truth_map


def test_doc001i_database_and_adr_links_no_longer_point_to_removed_diagram_file() -> None:
    tracked_docs = [
        "docs/database/tables.md",
        "docs/adr/014_document_database_schema_and_constraints.md",
    ]

    for path in tracked_docs:
        text = read(path)
        assert "docs/archive/diagrams/bronze_data_model.md" in text
        assert "docs/diagrams/bronze_data_model.md" not in text


def test_doc001i_planning_log_records_safe_small_archive_pass() -> None:
    text = read("docs/planning/doc001i_physical_diagram_archive.md")

    for phrase in [
        "first physical archive move",
        "docs/archive/diagrams/architecture.md",
        "docs/archive/diagrams/bronze_data_model.md",
        "does not mass-move",
        "dedicated reference",
    ]:
        assert phrase in text
