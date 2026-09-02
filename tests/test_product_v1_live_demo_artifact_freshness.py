from __future__ import annotations

from scripts import run_product_v1_live_demo as live_demo


def test_invalidate_output_artifacts_removes_prior_readiness(tmp_path) -> None:
    preflight = tmp_path / "preflight.json"
    workspace = tmp_path / "workspace.json"
    draft = tmp_path / "draft.json"
    for path in (preflight, workspace, draft):
        path.write_text('{"state":"pass"}\n', encoding="utf-8")

    live_demo._invalidate_output_artifacts(preflight, workspace, draft)

    assert not preflight.exists()
    assert not workspace.exists()
    assert not draft.exists()


def test_invalidate_output_artifacts_is_idempotent(tmp_path) -> None:
    preflight = tmp_path / "preflight.json"
    workspace = tmp_path / "workspace.json"
    draft = tmp_path / "draft.json"

    live_demo._invalidate_output_artifacts(preflight, workspace, draft)
    live_demo._invalidate_output_artifacts(preflight, workspace, draft)

    assert not preflight.exists()
    assert not workspace.exists()
    assert not draft.exists()
