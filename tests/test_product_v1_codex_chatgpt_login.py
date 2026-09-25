from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO
from types import SimpleNamespace

from src.search_intelligence import product_v1_codex_chatgpt_login as login


class FakeProcess:
    def __init__(self, lines: str, *, return_code: int = 0) -> None:
        self.stdout = StringIO(lines)
        self._return_code = return_code

    def wait(self) -> int:
        return self._return_code

    def poll(self):
        return None


def test_already_authenticated_returns_completed_without_new_login(monkeypatch) -> None:
    monkeypatch.setattr(
        login,
        "inspect_codex_runtime_status",
        lambda: SimpleNamespace(
            chatgpt_authenticated=True,
            executable="/runtime/vendor/codex/codex",
        ),
    )

    payload = login.start_codex_chatgpt_login()

    assert payload["status"] == "completed"
    assert payload["verification_url"] is None
    assert payload["user_code"] is None


def test_missing_bundled_runtime_fails_without_starting_oauth(monkeypatch) -> None:
    monkeypatch.setattr(
        login,
        "inspect_codex_runtime_status",
        lambda: SimpleNamespace(
            chatgpt_authenticated=False,
            executable=None,
        ),
    )

    payload = login.start_codex_chatgpt_login()

    assert payload["status"] == "failed"
    assert payload["detail"] == "Bundled Codex runtime is unavailable."


def test_device_login_output_exposes_only_public_url_and_user_code(monkeypatch) -> None:
    process = FakeProcess(
        "\\n".join(
            [
                "Follow these steps to sign in with ChatGPT using device code authorization:",
                "https://auth.openai.com/codex/device",
                "ABCD-12345",
                "Successfully logged in",
            ]
        )
    )
    session = login._LoginSession(
        session_id="session-1",
        status="starting",
        verification_url=None,
        user_code=None,
        started_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        detail=None,
        process=process,
    )
    monkeypatch.setattr(
        login,
        "inspect_codex_runtime_status",
        lambda: SimpleNamespace(chatgpt_authenticated=True),
    )

    login._consume(session)

    snapshot = session.snapshot()
    assert snapshot["status"] == "completed"
    assert snapshot["verification_url"] == "https://auth.openai.com/codex/device"
    assert snapshot["user_code"] == "ABCD-12345"
    assert "token" not in str(snapshot).casefold()


def test_device_login_failure_never_reports_tokens(monkeypatch) -> None:
    process = FakeProcess(
        "Error: device auth timed out after 15 minutes\\n",
        return_code=1,
    )
    session = login._LoginSession(
        session_id="session-2",
        status="starting",
        verification_url=None,
        user_code=None,
        started_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        detail=None,
        process=process,
    )
    monkeypatch.setattr(
        login,
        "inspect_codex_runtime_status",
        lambda: SimpleNamespace(chatgpt_authenticated=False),
    )

    login._consume(session)

    assert session.status == "failed"
    assert "timed out" in (session.detail or "")


def test_codex_device_login_command_is_official_cli_device_auth(monkeypatch) -> None:
    login._SESSION = None
    calls: list[tuple[list[str], dict[str, object]]] = []

    class StartingProcess(FakeProcess):
        def __init__(self, command, **kwargs):
            calls.append((list(command), kwargs))
            super().__init__("", return_code=1)

    monkeypatch.setattr(
        login,
        "inspect_codex_runtime_status",
        lambda: SimpleNamespace(
            chatgpt_authenticated=False,
            executable="/runtime/vendor/codex/codex",
        ),
    )
    monkeypatch.setattr(login.subprocess, "Popen", StartingProcess)
    monkeypatch.setattr(login.threading.Thread, "start", lambda _self: None)

    payload = login.start_codex_chatgpt_login()

    assert payload["status"] == "starting"
    assert calls[0][0] == ["/runtime/vendor/codex/codex", "login", "--device-auth"]
    environment = calls[0][1]["env"]
    assert isinstance(environment, dict)
    assert "OPENAI_API_KEY" not in environment
