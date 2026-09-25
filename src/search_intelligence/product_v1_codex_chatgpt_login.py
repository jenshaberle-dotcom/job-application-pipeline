"""One-time ChatGPT device login for the bundled Codex runtime.

The browser UI never receives Codex tokens. It receives only the public device
verification URL, one-time user code, and coarse session state. The official
Codex CLI owns OAuth/device-code exchange and credential persistence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re
import subprocess
import threading
import uuid

from src.search_intelligence.product_v1_codex_application_adapter import (
    _codex_environment,
    inspect_codex_runtime_status,
)


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_URL_RE = re.compile(r"https://[^\s]+/codex/device")
_CODE_RE = re.compile(r"\b[A-Z0-9]{4,}(?:-[A-Z0-9]{3,})+\b")
_LOCK = threading.Lock()
_SESSION: "_LoginSession | None" = None


@dataclass
class _LoginSession:
    session_id: str
    status: str
    verification_url: str | None
    user_code: str | None
    started_at: datetime
    expires_at: datetime
    detail: str | None
    process: subprocess.Popen[str]

    def snapshot(self) -> dict[str, object]:
        return {
            "schema": "job_application_pipeline.codex_chatgpt_login.v1",
            "session_id": self.session_id,
            "status": self.status,
            "verification_url": self.verification_url,
            "user_code": self.user_code,
            "started_at": self.started_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "detail": self.detail,
        }


def _clean(line: str) -> str:
    return _ANSI_RE.sub("", line).strip()


def _safe_detail(line: str) -> str:
    line = _clean(line)
    if not line:
        return "Codex login did not complete."
    return line[:500]


def _consume(session: _LoginSession) -> None:
    recent: list[str] = []
    assert session.process.stdout is not None
    try:
        for raw_line in session.process.stdout:
            line = _clean(raw_line)
            if not line:
                continue
            recent.append(line)
            recent[:] = recent[-8:]
            url_match = _URL_RE.search(line)
            with _LOCK:
                if url_match:
                    session.verification_url = url_match.group(0)
                    session.status = "awaiting_user"
                else:
                    code_match = _CODE_RE.search(line)
                    if code_match:
                        session.user_code = code_match.group(0)
                        session.status = "awaiting_user"
        return_code = session.process.wait()
        runtime = inspect_codex_runtime_status()
        with _LOCK:
            if return_code == 0 and runtime.chatgpt_authenticated:
                session.status = "completed"
                session.detail = "ChatGPT Codex authentication connected."
            else:
                session.status = "failed"
                session.detail = _safe_detail(recent[-1] if recent else "")
    except Exception as exc:  # pragma: no cover - defensive runtime boundary
        with _LOCK:
            session.status = "failed"
            session.detail = _safe_detail(str(exc))


def start_codex_chatgpt_login() -> dict[str, object]:
    """Start or reuse one official Codex device-auth session."""

    global _SESSION
    runtime = inspect_codex_runtime_status()
    if runtime.chatgpt_authenticated:
        return {
            "schema": "job_application_pipeline.codex_chatgpt_login.v1",
            "status": "completed",
            "verification_url": None,
            "user_code": None,
            "detail": "ChatGPT Codex authentication is already connected.",
        }
    if not runtime.executable:
        return {
            "schema": "job_application_pipeline.codex_chatgpt_login.v1",
            "status": "failed",
            "verification_url": None,
            "user_code": None,
            "detail": "Bundled Codex runtime is unavailable.",
        }

    with _LOCK:
        if _SESSION is not None and _SESSION.process.poll() is None:
            return _SESSION.snapshot()

        process = subprocess.Popen(
            [runtime.executable, "login", "--device-auth"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=_codex_environment(),
        )
        now = datetime.now(UTC)
        _SESSION = _LoginSession(
            session_id=str(uuid.uuid4()),
            status="starting",
            verification_url=None,
            user_code=None,
            started_at=now,
            expires_at=now + timedelta(minutes=15),
            detail=None,
            process=process,
        )
        thread = threading.Thread(
            target=_consume,
            args=(_SESSION,),
            name="jap-codex-chatgpt-login",
            daemon=True,
        )
        thread.start()
        return _SESSION.snapshot()


def codex_chatgpt_login_status() -> dict[str, object]:
    """Return only public device-login state; never expose persisted tokens."""

    runtime = inspect_codex_runtime_status()
    if runtime.chatgpt_authenticated:
        return {
            "schema": "job_application_pipeline.codex_chatgpt_login.v1",
            "status": "completed",
            "verification_url": None,
            "user_code": None,
            "detail": "ChatGPT Codex authentication connected.",
        }
    with _LOCK:
        if _SESSION is None:
            return {
                "schema": "job_application_pipeline.codex_chatgpt_login.v1",
                "status": "idle",
                "verification_url": None,
                "user_code": None,
                "detail": None,
            }
        return _SESSION.snapshot()


__all__ = [
    "codex_chatgpt_login_status",
    "start_codex_chatgpt_login",
]
