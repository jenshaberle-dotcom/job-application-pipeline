from __future__ import annotations

from pathlib import Path

from scripts.run_product_e2e_golden_path import (
    reconcile_connector_build_status,
)


def build_request(
    *,
    status: str = "artifact_generation_allowed",
    module_path: str = "src/connectors/example.py",
    test_path: str = "tests/test_example_connector.py",
    docs_path: str = "docs/planning/active/source-candidates/example.md",
) -> dict[str, object]:
    return {
        "build_status": status,
        "connector_module_path": module_path,
        "connector_test_path": test_path,
        "connector_docs_path": docs_path,
    }


def write_artifacts(repo_root: Path) -> None:
    for relative_path in (
        "src/connectors/example.py",
        "tests/test_example_connector.py",
        "docs/planning/active/source-candidates/example.md",
    ):
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("bounded artifact\n", encoding="utf-8")


def test_authorized_generated_artifacts_overlay_stale_db_status(
    tmp_path: Path,
) -> None:
    write_artifacts(tmp_path)

    result = reconcile_connector_build_status(
        "artifact_generation_allowed",
        build_request(),
        repo_root=tmp_path,
    )

    assert result == "artifacts_present"


def test_build_request_status_is_preferred_over_stale_lifecycle_view(
    tmp_path: Path,
) -> None:
    write_artifacts(tmp_path)

    result = reconcile_connector_build_status(
        "build_approval_required",
        build_request(status="artifact_generation_allowed"),
        repo_root=tmp_path,
    )

    assert result == "artifacts_present"


def test_missing_artifact_does_not_complete_generation(
    tmp_path: Path,
) -> None:
    write_artifacts(tmp_path)
    (tmp_path / "tests/test_example_connector.py").unlink()

    result = reconcile_connector_build_status(
        "artifact_generation_allowed",
        build_request(),
        repo_root=tmp_path,
    )

    assert result == "artifact_generation_allowed"


def test_file_presence_never_bypasses_build_approval(
    tmp_path: Path,
) -> None:
    write_artifacts(tmp_path)

    result = reconcile_connector_build_status(
        "build_approval_required",
        build_request(status="build_approval_required"),
        repo_root=tmp_path,
    )

    assert result == "build_approval_required"


def test_paths_outside_repo_root_are_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_connector.py"
    outside.write_text("not repo truth\n", encoding="utf-8")

    result = reconcile_connector_build_status(
        "artifact_generation_allowed",
        build_request(module_path="../outside_connector.py"),
        repo_root=tmp_path,
    )

    assert result == "artifact_generation_allowed"


def test_absolute_paths_are_rejected(tmp_path: Path) -> None:
    absolute_path = tmp_path / "absolute_connector.py"
    absolute_path.write_text("not persisted repo-relative truth\n", encoding="utf-8")

    result = reconcile_connector_build_status(
        "artifact_generation_allowed",
        build_request(module_path=str(absolute_path)),
        repo_root=tmp_path,
    )

    assert result == "artifact_generation_allowed"
