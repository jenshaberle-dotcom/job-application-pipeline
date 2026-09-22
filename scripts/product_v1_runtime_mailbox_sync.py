"""Consumer-local mailbox sync orchestration for installed JAP.

The public Product runtime owns classification/persistence semantics but never Gmail
credentials or Gmail API access.  This module invokes the separately installed
private runtime bridge, consumes only its normalized JSONL, and idempotently applies
bounded evidence to PostgreSQL.  It is safe for startup, a 30-minute cadence and
explicit operator refresh.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from typing import Callable

from scripts.run_product_v1_f5_mailbox_persistence_apply import (
    _assert_plan_is_safe,
    _load_existing_application_identities,
    _load_live_state,
    _select_apply_rows,
    _summarize_results,
)
from scripts.run_product_v1_f5_mailbox_persistence_preflight import plan_rows
from scripts.product_v1_f5_mailbox_ingest import (
    ingest_normalized_mailbox_observation,
    parse_normalized_mailbox_observation,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTERVAL_SECONDS = 30 * 60
DEFAULT_RUNTIME_ROOT = Path.home() / "projects" / "job-pipeline-runtime"
DEFAULT_CLIENT_CONFIG = Path.home() / ".config/DeepOceanInfrastructure/JAP/gmail-oauth-client.json"
DEFAULT_TOKEN_PATH = Path.home() / ".config/DeepOceanInfrastructure/JAP/gmail-readonly-token.json"
DEFAULT_STATE_ROOT = Path.home() / ".local/state/jap/mailbox-sync"
_LOCK = threading.Lock()


class MailboxRuntimeSyncError(RuntimeError):
    pass


def _runtime_root() -> Path:
    return Path(os.environ.get("JAP_PRIVATE_RUNTIME_ROOT", str(DEFAULT_RUNTIME_ROOT))).expanduser()


def _client_config() -> Path:
    return Path(os.environ.get("JAP_GMAIL_OAUTH_CLIENT_JSON", str(DEFAULT_CLIENT_CONFIG))).expanduser()


def _token_path() -> Path:
    return Path(os.environ.get("JAP_GMAIL_TOKEN_JSON", str(DEFAULT_TOKEN_PATH))).expanduser()


def _state_root() -> Path:
    return Path(os.environ.get("JAP_MAILBOX_SYNC_STATE_ROOT", str(DEFAULT_STATE_ROOT))).expanduser()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_status(payload: dict[str, object]) -> None:
    root = _state_root()
    root.mkdir(parents=True, exist_ok=True)
    target = root / "status.json"
    fd, raw = tempfile.mkstemp(dir=root, prefix=".status.", suffix=".json")
    os.close(fd)
    staged = Path(raw)
    try:
        staged.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(staged, target)
    finally:
        staged.unlink(missing_ok=True)


def _scan_normalized(output: Path) -> dict[str, object]:
    bridge = _runtime_root() / "scripts" / "f5_gmail_readonly_bridge.py"
    if not bridge.is_file():
        raise MailboxRuntimeSyncError(f"private_runtime_bridge_missing:{bridge}")
    client = _client_config()
    token = _token_path()
    if not client.is_file():
        raise MailboxRuntimeSyncError(f"gmail_oauth_client_missing:{client}")
    if not token.is_file():
        raise MailboxRuntimeSyncError(f"gmail_readonly_token_missing:{token}")

    command = [
        sys.executable,
        str(bridge),
        "scan",
        "--client-config",
        str(client),
        "--token-path",
        str(token),
        "--max-messages",
        os.environ.get("JAP_MAILBOX_SYNC_MAX_MESSAGES", "1000"),
        "--progress-every",
        "0",
        "--output",
        str(output),
    ]
    completed = subprocess.run(
        command,
        cwd=_runtime_root(),
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "bridge_failed").strip()[-1200:]
        raise MailboxRuntimeSyncError(f"private_runtime_bridge_failed:{detail}")
    if not output.is_file():
        raise MailboxRuntimeSyncError("normalized_mailbox_output_missing")
    return {
        "bridge_exit_code": completed.returncode,
        "normalized_sha256": _sha256(output),
    }


def _load_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise MailboxRuntimeSyncError(f"normalized_row_not_object:{line_no}")
        rows.append(payload)
    return rows


def _apply_idempotent(rows: list[dict[str, object]]) -> dict[str, object]:
    import psycopg
    from psycopg.rows import dict_row
    from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig

    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            application_keys, active = _load_live_state(conn)
            identities = _load_existing_application_identities(conn)
            plan = plan_rows(
                rows,
                existing_application_keys=application_keys,
                existing_application_identities=identities,
                active_candidates=active,
            )
            _assert_plan_is_safe(plan)
            selected = _select_apply_rows(rows, active_candidates=active, since=None, until=None)
            if len(selected) != plan.persistence_candidate_rows:
                raise MailboxRuntimeSyncError("selected_row_count_mismatch")

            results: list[dict[str, object]] = []
            for payload in selected:
                results.append(
                    ingest_normalized_mailbox_observation(
                        parse_normalized_mailbox_observation(payload),
                        connection=conn,
                    )
                )
            actual = _summarize_results(results)
            if actual["application_inserts"] != plan.application_inserts:
                raise MailboxRuntimeSyncError("application_insert_delta_mismatch")
            if actual["candidate_inserts"] != plan.candidate_inserts:
                raise MailboxRuntimeSyncError("candidate_insert_delta_mismatch")
            if actual["candidate_noops"] != plan.candidate_noops:
                raise MailboxRuntimeSyncError("candidate_noop_delta_mismatch")
            if actual["candidate_supersessions"] != plan.candidate_supersessions:
                raise MailboxRuntimeSyncError("candidate_supersession_delta_mismatch")

    return {
        "plan": asdict(plan),
        "actual": actual,
    }


def sync_mailbox(*, reason: str) -> dict[str, object]:
    started = datetime.now(timezone.utc)
    if not _LOCK.acquire(blocking=False):
        return {
            "schema": "jap.runtime.mailbox_sync.v1",
            "status": "already_running",
            "reason": reason,
            "started_at": started.isoformat(),
        }
    try:
        root = _state_root()
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=root, prefix="normalized.", suffix=".jsonl", delete=False
        ) as handle:
            normalized = Path(handle.name)
        try:
            scan = _scan_normalized(normalized)
            rows = _load_rows(normalized)
            applied = _apply_idempotent(rows)
            result = {
                "schema": "jap.runtime.mailbox_sync.v1",
                "status": "pass",
                "reason": reason,
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "normalized_rows": len(rows),
                **scan,
                **applied,
                "gmail_scope": "gmail.readonly",
                "gmail_writes": 0,
                "email_actions": 0,
                "application_submission_actions": 0,
                "authoritative_lifecycle_mutations": 0,
            }
            _write_status(result)
            return result
        finally:
            normalized.unlink(missing_ok=True)
    except Exception as exc:
        result = {
            "schema": "jap.runtime.mailbox_sync.v1",
            "status": "error",
            "reason": reason,
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__,
            "message": str(exc)[:1200],
            "gmail_writes": 0,
            "email_actions": 0,
            "application_submission_actions": 0,
            "authoritative_lifecycle_mutations": 0,
        }
        _write_status(result)
        return result
    finally:
        _LOCK.release()


class MailboxSyncScheduler:
    def __init__(
        self,
        *,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
        sync: Callable[..., dict[str, object]] = sync_mailbox,
    ) -> None:
        if interval_seconds < 60:
            raise ValueError("mailbox sync interval must be at least 60 seconds")
        self.interval_seconds = interval_seconds
        self._sync = sync
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name="jap-mailbox-sync",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        self._sync(reason="startup")
        while not self._stop.wait(self.interval_seconds):
            self._sync(reason="scheduled_30m")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
