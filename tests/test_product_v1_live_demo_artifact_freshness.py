from __future__ import annotations

import pytest

from scripts import run_product_v1_live_demo as live_demo


def _set_demo_root(monkeypatch, tmp_path):
    monkeypatch.setattr(live_demo, "DEMO_ARTIFACT_ROOT", tmp_path.resolve())


def test_invalidate_output_artifacts_removes_prior_readiness(monkeypatch, tmp_path) -> None:
    _set_demo_root(monkeypatch, tmp_path)
    preflight = tmp_path / "preflight.json"
    workspace = tmp_path / "workspace.json"
    draft = tmp_path / "draft.json"
    for path in (preflight, workspace, draft):
        path.write_text('{"state":"pass"}\n', encoding="utf-8")

    live_demo._invalidate_output_artifacts(preflight, workspace, draft)

    assert not preflight.exists()
    assert not workspace.exists()
    assert not draft.exists()


def test_invalidate_output_artifacts_is_idempotent(monkeypatch, tmp_path) -> None:
    _set_demo_root(monkeypatch, tmp_path)
    paths = tuple(tmp_path / name for name in ("preflight.json", "workspace.json", "draft.json"))

    live_demo._invalidate_output_artifacts(*paths)
    live_demo._invalidate_output_artifacts(*paths)

    assert all(not path.exists() for path in paths)


def test_invalidation_rejects_path_outside_demo_root(monkeypatch, tmp_path) -> None:
    demo_root = tmp_path / "demo"
    demo_root.mkdir()
    monkeypatch.setattr(live_demo, "DEMO_ARTIFACT_ROOT", demo_root.resolve())
    outside = tmp_path / "do-not-delete.json"
    outside.write_text("important\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="must stay under"):
        live_demo._invalidate_output_artifacts(outside)

    assert outside.read_text(encoding="utf-8") == "important\n"


def test_invalidation_validates_all_paths_before_deleting_any(monkeypatch, tmp_path) -> None:
    demo_root = tmp_path / "demo"
    demo_root.mkdir()
    monkeypatch.setattr(live_demo, "DEMO_ARTIFACT_ROOT", demo_root.resolve())
    valid = demo_root / "preflight.json"
    valid.write_text('{"state":"pass"}\n', encoding="utf-8")
    outside = tmp_path / "outside.json"

    with pytest.raises(RuntimeError, match="must stay under"):
        live_demo._invalidate_output_artifacts(valid, outside)

    assert valid.exists()


def test_invalidation_requires_json_diagnostic(monkeypatch, tmp_path) -> None:
    _set_demo_root(monkeypatch, tmp_path)
    non_json = tmp_path / "preflight.txt"
    non_json.write_text("keep\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"must be a \.json file"):
        live_demo._invalidate_output_artifacts(non_json)

    assert non_json.exists()
