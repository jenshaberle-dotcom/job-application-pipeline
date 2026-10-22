"""Local UI orchestration; OAuth and secrets remain in the private Gmail bridge."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from urllib.parse import urlparse

from scripts.product_v1_runtime_mailbox_sync import (
    _client_config, _runtime_root, _state_root, _token_path, _LOCK as _sync_lock,
)

_lock = threading.Lock()
_attempt: dict[str, object] = {}


def connection_status() -> dict[str, object]:
    with _lock:
        result = dict(_attempt)
    if result:
        return result
    try:
        sync = json.loads((_state_root() / "status.json").read_text())
    except (OSError, ValueError):
        sync = {}
    if "invalid_grant" in str(sync.get("message", "")):
        return {"state": "reauth_required"}
    return {"state": "configured" if _token_path().is_file() else "disconnected"}


def _authorize() -> None:
    process = None
    acquired = _sync_lock.acquire(blocking=False)
    if not acquired:
        with _lock:
            _attempt.clear()
            _attempt["state"] = "sync_running"
        return
    try:
        process = subprocess.Popen(
            [sys.executable, "-u",
             str(_runtime_root() / "scripts/f5_gmail_readonly_bridge.py"),
             "authorize", "--client-config", str(_client_config()),
             "--token-path", str(_token_path()), "--no-browser", "--timeout", "300"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            if line.startswith("GMAIL_OAUTH_URL="):
                url = line.strip().split("=", 1)[1]
                parsed = urlparse(url)
                if (parsed.scheme, parsed.netloc, parsed.path) != (
                    "https", "accounts.google.com", "/o/oauth2/v2/auth"
                ):
                    raise ValueError("Unexpected authorization URL")
                with _lock:
                    _attempt.update(state="awaiting_google", authorization_url=url)
        code = process.wait(timeout=15)
        with _lock:
            _attempt.clear()
            _attempt["state"] = "connected" if code == 0 else "login_failed"
    except Exception:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        with _lock:
            _attempt.clear()
            _attempt["state"] = "login_failed"
    finally:
        _sync_lock.release()


def start_connection() -> dict[str, object]:
    with _lock:
        if _attempt.get("state") in {"starting", "awaiting_google"}:
            return dict(_attempt)
        if not _client_config().is_file() or not (
            _runtime_root() / "scripts/f5_gmail_readonly_bridge.py"
        ).is_file():
            return {"state": "setup_required"}
        _attempt.clear()
        _attempt["state"] = "starting"
    threading.Thread(target=_authorize, daemon=True).start()
    return {"state": "starting"}


def trusted_ui_request(headers, server_address) -> bool:
    """Require an exact local origin and a non-simple request header."""
    try:
        origin = urlparse(headers.get("Origin", ""))
        return (
            headers.get("X-JAP-Action") == "google-connect"
            and origin.scheme == "http"
            and origin.hostname in {"127.0.0.1", "localhost"}
            and origin.port == server_address[1]
        )
    except ValueError:
        return False
