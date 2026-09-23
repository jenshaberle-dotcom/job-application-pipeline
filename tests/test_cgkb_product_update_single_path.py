from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_routine_update_is_product_local_and_has_single_authority():
    agent = read("windows/JAP.ControlCenter.Desktop/ProductUpdateAgent.cs")
    coordinator = read("windows/JAP.ControlCenter.Desktop/UpdateCoordinator.cs")
    assert "product_local_update_agent_v1" in agent
    assert "pending-update.json" in agent
    assert "accepted-update.json" in coordinator
    assert "Apply-JAP-Control-Center-Update.ps1" not in coordinator
    assert "update_accept_blocked" in coordinator
    assert "powershell.exe" not in coordinator
    assert "wsl.exe" not in coordinator.lower()
    assert "git " not in coordinator.lower()


def test_release_payload_does_not_ship_legacy_update_control_plane():
    workflow = read(".github/workflows/jap-windows-desktop-host-release.yml")
    assert 'Copy-Item -Force "Apply-JAP-Control-Center-Update.ps1"' not in workflow
    assert 'Copy-Item -Force "scripts/run_jap_windows_control_center.sh"' not in workflow


def test_legacy_routine_update_surfaces_are_physically_absent():
    forbidden = [
        "Update-JAP-Control-Center.ps1",
        "Apply-JAP-Control-Center-Update.ps1",
        "scripts/deploy_jap_windows_control_center_local.sh",
        ".github/workflows/jap-windows-control-center-local-deploy.yml",
        "tests/test_jap_windows_control_center_local_deploy.py",
    ]
    for relative in forbidden:
        assert not (ROOT / relative).exists(), f"legacy update surface returned: {relative}"


def test_no_legacy_authority_references_remain_in_active_update_surfaces():
    active = [
        "install-jap-control-center.ps1",
        ".github/workflows/jap-windows-desktop-host-release.yml",
        "windows/JAP.ControlCenter.Desktop/UpdateCoordinator.cs",
    ]
    forbidden = [
        "Apply-JAP-Control-Center-Update.ps1",
        "Update-JAP-Control-Center.ps1",
        "deploy_jap_windows_control_center_local.sh",
        "jap-windows-control-center-local-deploy.yml",
    ]
    for relative in active:
        body = read(relative)
        for token in forbidden:
            assert token not in body, f"{token} returned in {relative}"
