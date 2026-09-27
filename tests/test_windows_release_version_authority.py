from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / ".github" / "workflows" / "jap-windows-desktop-host-release.yml"


def test_automatic_product_release_is_version_authoritative() -> None:
    workflow = RELEASE.read_text(encoding="utf-8")
    trigger = workflow.split("permissions:", 1)[0]

    assert 'branches: [main]' in trigger
    assert '- "windows/JAP.ControlCenter.Desktop/VERSION"' in trigger
    assert "workflow_dispatch:" in trigger

    for forbidden_push_path in (
        '- "src/**"',
        '- "scripts/**"',
        '- "frontend/control-center/**"',
        '- "config/**"',
        '- "contracts/**"',
        '- "db/**"',
        '- ".github/workflows/jap-windows-desktop-host-release.yml"',
    ):
        assert forbidden_push_path not in trigger


def test_immutable_release_collision_remains_fail_closed() -> None:
    workflow = RELEASE.read_text(encoding="utf-8")

    assert "Immutable product release $env:PRODUCT_TAG already points to another source." in workflow
    assert "--target $env:GITHUB_SHA" in workflow
    assert "Published product release target identity mismatch." in workflow
