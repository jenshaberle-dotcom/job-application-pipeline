from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REMOTE_SCRIPT = ROOT / "scripts" / "windows" / "Start-JAP-Classic-Remote-Demo.ps1"
LOCAL_RUNTIME = ROOT / "scripts" / "run_jap_windows_control_center.sh"
GUIDE = ROOT / "docs" / "guides" / "jap_classic_remote_demo_backup.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_remote_demo_backup_files_are_present() -> None:
    assert REMOTE_SCRIPT.is_file()
    assert GUIDE.is_file()


def test_remote_demo_does_not_change_jap_local_bind_authority() -> None:
    remote = _text(REMOTE_SCRIPT)
    runtime = _text(LOCAL_RUNTIME)

    assert '$Origin = "http://127.0.0.1:8780"' in remote
    assert 'export PRODUCT_V1_UI_HOST="127.0.0.1"' in runtime
    assert 'export PRODUCT_V1_UI_PORT="8780"' in runtime
    assert "0.0.0.0" not in remote


def test_remote_demo_requires_named_authenticated_tunnel() -> None:
    remote = _text(REMOTE_SCRIPT)

    assert "JAP_DEMO_CLOUDFLARE_TUNNEL_TOKEN" in remote
    assert 'EnvironmentVariables["TUNNEL_TOKEN"]' in remote
    assert '$startInfo.Arguments = "tunnel --no-autoupdate run"' in remote
    assert "--token" not in remote
    assert "trycloudflare.com" not in remote
    assert "cloudflare_access_not_enforced" in remote
    assert "PUBLIC_HTTP_200" in remote
    assert ".cloudflareaccess.com" in remote
    assert "/cdn-cgi/access/" in remote


def test_remote_demo_stop_is_owned_pid_and_path_only() -> None:
    remote = _text(REMOTE_SCRIPT)

    assert "cloudflared-process.json" in remote
    assert "Get-Process -Id $pidValue" in remote
    assert "$process.ProcessName -ne \"cloudflared\"" in remote
    assert "$actualPath" in remote
    assert "$expectedPath" in remote
    assert "Stop-Process -Id $process.Id" in remote
    assert "Get-Process -Name" not in remote


def test_remote_demo_guide_keeps_classic_local() -> None:
    guide = _text(GUIDE)

    assert "does **not** make JAP Classic a cloud product" in guide
    assert "http://127.0.0.1:8780" in guide
    assert "Protect with Access" in guide
    assert "no cloud database" in guide
    assert "no multi-user JAP" in guide
    assert "no router port-forward" in guide
