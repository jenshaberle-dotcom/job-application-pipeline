from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / ".github" / "workflows" / "jap-windows-desktop-host-release.yml"
RUNNER = ROOT / "scripts" / "run_jap_windows_control_center.sh"
AGENT = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "ProductUpdateAgent.cs"
APPLIER = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "ProductUpdateApplier.cs"
INSTALLER = ROOT / "install-jap-control-center.ps1"
SERVER = ROOT / "scripts" / "run_product_v1_demo_control_center.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_product_release_bundles_one_pinned_official_codex_binary() -> None:
    release = _text(RELEASE)

    assert '$CodexVersion = "0.154.0"' in release
    assert '$CodexArchiveName = "codex-x86_64-unknown-linux-musl.tar.gz"' in release
    assert (
        '$CodexArchiveSha256 = '
        '"d7e18b2597ae8f242f5f31ee9e90deef48dbc9edd634d9868fb6435d08c07f02"'
    ) in release
    assert (
        '"https://github.com/openai/codex/releases/download/'
        'rust-v$CodexVersion/$CodexArchiveName"'
    ) in release
    assert "Official Codex archive checksum mismatch." in release
    assert '"vendor\\codex\\codex"' in release
    assert '"vendor\\codex\\codex-info.json"' in release
    assert '"job_application_pipeline.codex_runtime.v1"' in release
    assert '"chatgpt_cli_login"' in release
    assert '"chatgpt_included_allowance_then_eligible_credits"' in release
    assert "auto_purchase = $false" in release
    assert "auto_api_key_fallback = $false" in release


def test_installed_runtime_uses_bundled_codex_without_runtime_install_or_download() -> None:
    runner = _text(RUNNER)

    assert 'CODEX_BINARY="${RUNTIME_ROOT}/vendor/codex/codex"' in runner
    assert 'CODEX_INFO="${RUNTIME_ROOT}/vendor/codex/codex-info.json"' in runner
    assert 'export JAP_CODEX_EXECUTABLE="$CODEX_BINARY"' in runner
    assert 'chmod 0755 "$CODEX_BINARY"' in runner
    assert "job_application_pipeline.codex_runtime.v1" in runner
    assert '"0.154.0"' in runner
    assert "codex binary checksum mismatch" in runner
    assert "JAP_WINDOWS_APP_CODEX_VERSION=" in runner
    assert "JAP_WINDOWS_APP_CODEX_SHA256=" in runner

    runtime_section = runner.lower()
    for forbidden in (
        "npm install",
        "npm ci",
        "npm run build",
        "curl ",
        "wget ",
        "codex update",
        "npm install -g @openai/codex",
    ):
        assert forbidden not in runtime_section


def test_update_and_bootstrap_authority_require_codex_before_cutover() -> None:
    for source in (_text(AGENT), _text(APPLIER), _text(INSTALLER)):
        assert "vendor" in source
        assert "codex" in source
        assert "codex-info.json" in source

    agent = _text(AGENT)
    applier = _text(APPLIER)
    assert "Staged bundled Codex executable is missing." in agent
    assert "Staged bundled Codex identity is missing." in agent
    assert "Staged bundled Codex executable is missing." in applier
    assert "Staged bundled Codex identity is missing." in applier


def test_control_center_exposes_codex_runtime_and_chatgpt_auth_truth() -> None:
    server = _text(SERVER)
    adapter = _text(
        ROOT / "src" / "search_intelligence" / "product_v1_codex_application_adapter.py"
    )
    workspace = _text(ROOT / "frontend" / "control-center" / "src" / "ApplicationWorkspace.tsx")
    about = _text(ROOT / "frontend" / "control-center" / "src" / "AboutPanel.tsx")

    assert 'CODEX_STATUS_PATH = "/api/v1/product-v1/codex-status"' in server
    assert "inspect_codex_runtime_status().to_json()" in server
    assert '"logged in using chatgpt" in output.casefold()' in adapter
    assert "codex_chatgpt_auth_required" in adapter
    assert '"/api/v1/product-v1/codex-status"' in workspace
    assert "Embedded Codex" in workspace
    assert "ChatGPT Codex connection required" in workspace
    assert "JAP will not switch to API-key billing" in workspace
    assert '"/api/v1/product-v1/codex-status"' in about
    assert "Usage authority" in about
    assert "ChatGPT allowance / eligible credits" in about


def test_codex_availability_is_a_product_state_not_http_transport_failure() -> None:
    server = _text(SERVER)

    assert '{"draft_for_review", "draft_unavailable"}' in server
    assert "HTTPStatus.OK" in server
    assert "HTTPStatus.CONFLICT" in server
