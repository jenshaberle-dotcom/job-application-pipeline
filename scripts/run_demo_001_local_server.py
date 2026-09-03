"""Start the local DEMO-001 server and wait for actual HTTP readiness.

This operator helper exists because the live-demo launcher intentionally completes
preflight, workspace and draft probes before binding the HTTP port. A fixed sleep is
therefore not a readiness contract. The helper owns only its recorded child PID and
never kills an unrelated port listener.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME = ROOT / ".runtime" / "demo"


def _tail(path: Path, lines: int = 80) -> str:
    if not path.is_file():
        return "<no log>"
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def _stop_recorded_pid(pid_file: Path) -> None:
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pid_file.unlink(missing_ok=True)
        return
    for _ in range(40):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            pid_file.unlink(missing_ok=True)
            return
        time.sleep(0.25)
    raise RuntimeError(f"recorded demo process did not stop: {pid}")


def _ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=2) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8781)
    parser.add_argument("--wait-seconds", type=int, default=90)
    parser.add_argument(
        "--canonical-repo",
        type=Path,
        default=Path.home() / "projects" / "job-application-pipeline",
    )
    parser.add_argument("--no-restart", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if not 5 <= args.wait_seconds <= 300:
        raise SystemExit("--wait-seconds must be between 5 and 300")

    canonical_repo = args.canonical_repo.expanduser().resolve()
    env_file = canonical_repo / ".env"
    if not env_file.is_file():
        raise SystemExit(f"canonical dotenv missing: {env_file}")
    load_dotenv(env_file, override=False)

    private_root = canonical_repo / "private_application_sources"
    if not private_root.is_dir():
        raise SystemExit(f"private application root missing: {private_root}")

    runtime = DEFAULT_RUNTIME.resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    pid_file = runtime / f"product_v1_demo_{args.port}.pid"
    log_file = runtime / f"product_v1_demo_{args.port}.log"

    if not args.no_restart:
        _stop_recorded_pid(pid_file)

    env = dict(os.environ)
    env["PRODUCT_V1_PRIVATE_DOCUMENT_ROOT"] = str(private_root)
    env["PRODUCT_V1_UI_PORT"] = str(args.port)

    log_handle = log_file.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "scripts.run_product_v1_live_demo", "--reuse-frontend"],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    log_handle.close()
    pid_file.write_text(f"{process.pid}\n", encoding="utf-8")

    url = f"http://127.0.0.1:{args.port}/api/v1/product-v1"
    started = time.monotonic()
    while time.monotonic() - started < args.wait_seconds:
        return_code = process.poll()
        if return_code is not None:
            print(f"DEMO_SERVER_EXITED={return_code}")
            print(_tail(log_file))
            return 2
        if _ready(url):
            elapsed = time.monotonic() - started
            print("DEMO_SERVER_READY=YES")
            print(f"PID={process.pid}")
            print(f"READY_SECONDS={elapsed:.2f}")
            print(f"URL=http://127.0.0.1:{args.port}/")
            print(f"LOG={log_file}")
            return 0
        time.sleep(1)

    print("DEMO_SERVER_READY=NO")
    print(_tail(log_file))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
