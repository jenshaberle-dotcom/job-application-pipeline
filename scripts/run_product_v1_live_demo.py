"""Prepare and launch the DEMO-001 Product V1 Control Center.

Default sequence:
1. install/build the existing React Control Center;
2. run the fail-closed live Product V1 demo preflight;
3. probe the selected authoritative Top-5 Application Workspace read-only;
4. start the demo Control Center only when both readiness probes pass.

The launcher never changes pipeline product truth, activates a source, creates an
application, submits, or sends anything. Use ``--reuse-frontend`` after a previously
qualified build when network-independent startup is preferred for the presentation.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from scripts.run_product_v1_demo_control_center import run_server


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "control-center"
DEFAULT_DIST = FRONTEND / "dist"
DEFAULT_PREFLIGHT = ROOT / ".runtime" / "demo" / "product_v1_demo_preflight.json"
DEFAULT_WORKSPACE_PROBE = (
    ROOT / ".runtime" / "demo" / "product_v1_demo_workspace_probe.json"
)
_FRONTEND_LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json")


def _run(command: list[str], *, cwd: Path) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def _frontend_install_command(npm: str) -> tuple[list[str], str]:
    """Choose the strongest npm install mode supported by repository truth.

    ``npm ci`` requires a committed npm lockfile. The Control Center currently has
    no lockfile, matching the repository CI path, so local demo startup must not
    manufacture one merely to build the UI. When a lockfile is added later, the
    launcher automatically ratchets back to ``npm ci``.
    """

    if any((FRONTEND / name).is_file() for name in _FRONTEND_LOCKFILES):
        return [npm, "ci"], "LOCKFILE_CI"
    return [
        npm,
        "install",
        "--package-lock=false",
        "--no-audit",
        "--no-fund",
    ], "LOCKFILE_ABSENT_INSTALL"


def prepare_frontend(*, reuse_frontend: bool) -> Path:
    dist = DEFAULT_DIST.resolve()
    if reuse_frontend:
        if not (dist / "index.html").is_file():
            raise RuntimeError(
                "--reuse-frontend requested but no built Control Center exists"
            )
        print(f"FRONTEND_BUILD=REUSED path={dist}")
        return dist

    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm is required to build the React Control Center")
    install_command, install_mode = _frontend_install_command(npm)
    print(f"FRONTEND_INSTALL_MODE={install_mode}")
    _run(install_command, cwd=FRONTEND)
    _run([npm, "run", "build"], cwd=FRONTEND)
    if not (dist / "index.html").is_file():
        raise RuntimeError("React build completed without dist/index.html")
    print(f"FRONTEND_BUILD=PASS path={dist}")
    return dist


def run_preflight(*, frontend_dist: Path, output: Path) -> int:
    command = [
        sys.executable,
        "-m",
        "scripts.run_product_v1_demo_preflight",
        "--frontend-dist",
        str(frontend_dist),
        "--output",
        str(output),
    ]
    print("+ " + " ".join(command))
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


def run_workspace_probe(*, preflight: Path, output: Path) -> int:
    command = [
        sys.executable,
        "-m",
        "scripts.run_product_v1_demo_workspace_probe",
        "--preflight",
        str(preflight),
        "--output",
        str(output),
    ]
    print("+ " + " ".join(command))
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host",
        default=os.environ.get("PRODUCT_V1_UI_HOST", "127.0.0.1"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PRODUCT_V1_UI_PORT", "8780")),
    )
    parser.add_argument(
        "--reuse-frontend",
        action="store_true",
        help="Reuse an existing dist build instead of installing/building the frontend.",
    )
    parser.add_argument(
        "--preflight-output",
        type=Path,
        default=DEFAULT_PREFLIGHT,
    )
    parser.add_argument(
        "--workspace-probe-output",
        type=Path,
        default=DEFAULT_WORKSPACE_PROBE,
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Build/check full demo readiness without starting the HTTP server.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        frontend_dist = prepare_frontend(reuse_frontend=args.reuse_frontend)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"DEMO_START_BLOCKED=frontend:{exc}", file=sys.stderr)
        return 2

    preflight_output = args.preflight_output.resolve()
    preflight_code = run_preflight(
        frontend_dist=frontend_dist,
        output=preflight_output,
    )
    if preflight_code != 0:
        print("DEMO_START_BLOCKED=live_preflight", file=sys.stderr)
        print(f"PREFLIGHT_ARTIFACT={preflight_output}", file=sys.stderr)
        return preflight_code

    print("DEMO_PREFLIGHT=PASS")
    workspace_probe_output = args.workspace_probe_output.resolve()
    workspace_probe_code = run_workspace_probe(
        preflight=preflight_output,
        output=workspace_probe_output,
    )
    if workspace_probe_code != 0:
        print("DEMO_START_BLOCKED=application_workspace_probe", file=sys.stderr)
        print(f"WORKSPACE_PROBE_ARTIFACT={workspace_probe_output}", file=sys.stderr)
        return workspace_probe_code

    print("DEMO_WORKSPACE_PROBE=PASS")
    print("DEMO_BOUNDARY=no_fake_truth,no_auto_submit,no_send")
    if args.preflight_only:
        print("PRODUCT_V1_LIVE_DEMO=READY")
        return 0

    server_args = argparse.Namespace(
        host=args.host,
        port=args.port,
        frontend_dist=frontend_dist,
    )
    run_server(server_args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
