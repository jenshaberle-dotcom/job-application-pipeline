"""Prepare and launch the DEMO-001 Product V1 Control Center.

Default sequence:
1. install/build the existing React Control Center;
2. run the fail-closed live Product V1 demo preflight;
3. probe the selected authoritative Top-5 Application Workspace with one detail fetch;
4. validate its carried provider-free evidence-first review-draft proof offline;
5. start the demo Control Center only when all readiness probes pass.

The launcher never changes pipeline product truth, activates a source, persists an
application/draft, submits, or sends anything. The final readiness proof invokes no
provider and performs no second vacancy fetch. Use ``--reuse-frontend`` after a
previously qualified build when network-independent frontend startup is preferred.
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
DEFAULT_WORKSPACE_PROBE = ROOT / ".runtime" / "demo" / "product_v1_demo_workspace_probe.json"
DEFAULT_DRAFT_PROBE = ROOT / ".runtime" / "demo" / "product_v1_demo_draft_probe.json"
_FRONTEND_LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json")


def _run(command: list[str], *, cwd: Path) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def _frontend_install_command(npm: str) -> tuple[list[str], str]:
    if any((FRONTEND / name).is_file() for name in _FRONTEND_LOCKFILES):
        return [npm, "ci"], "LOCKFILE_CI"
    return [npm, "install", "--package-lock=false", "--no-audit", "--no-fund"], "LOCKFILE_ABSENT_INSTALL"


def prepare_frontend(*, reuse_frontend: bool) -> Path:
    dist = DEFAULT_DIST.resolve()
    if reuse_frontend:
        if not (dist / "index.html").is_file():
            raise RuntimeError("--reuse-frontend requested but no built Control Center exists")
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


def _run_module(module: str, *, arguments: list[str]) -> int:
    command = [sys.executable, "-m", module, *arguments]
    print("+ " + " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def run_preflight(*, frontend_dist: Path, output: Path) -> int:
    return _run_module(
        "scripts.run_product_v1_demo_preflight",
        arguments=["--frontend-dist", str(frontend_dist), "--output", str(output)],
    )


def run_workspace_probe(*, preflight: Path, output: Path) -> int:
    return _run_module(
        "scripts.run_product_v1_demo_workspace_probe",
        arguments=["--preflight", str(preflight), "--output", str(output)],
    )


def run_draft_probe(*, preflight: Path, workspace_probe: Path, output: Path) -> int:
    return _run_module(
        "scripts.run_product_v1_demo_draft_handoff",
        arguments=[
            "--preflight",
            str(preflight),
            "--workspace-probe",
            str(workspace_probe),
            "--output",
            str(output),
        ],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("PRODUCT_V1_UI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PRODUCT_V1_UI_PORT", "8780")))
    parser.add_argument(
        "--reuse-frontend",
        action="store_true",
        help="Reuse an existing dist build instead of installing/building the frontend.",
    )
    parser.add_argument("--preflight-output", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--workspace-probe-output", type=Path, default=DEFAULT_WORKSPACE_PROBE)
    parser.add_argument("--draft-probe-output", type=Path, default=DEFAULT_DRAFT_PROBE)
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
    if run_preflight(frontend_dist=frontend_dist, output=preflight_output) != 0:
        print("DEMO_START_BLOCKED=live_preflight", file=sys.stderr)
        print(f"PREFLIGHT_ARTIFACT={preflight_output}", file=sys.stderr)
        return 2

    print("DEMO_PREFLIGHT=PASS")
    workspace_probe_output = args.workspace_probe_output.resolve()
    if run_workspace_probe(preflight=preflight_output, output=workspace_probe_output) != 0:
        print("DEMO_START_BLOCKED=application_workspace_probe", file=sys.stderr)
        print(f"WORKSPACE_PROBE_ARTIFACT={workspace_probe_output}", file=sys.stderr)
        return 2

    print("DEMO_WORKSPACE_PROBE=PASS")
    draft_probe_output = args.draft_probe_output.resolve()
    if run_draft_probe(
        preflight=preflight_output,
        workspace_probe=workspace_probe_output,
        output=draft_probe_output,
    ) != 0:
        print("DEMO_START_BLOCKED=review_draft_probe", file=sys.stderr)
        print(f"DRAFT_PROBE_ARTIFACT={draft_probe_output}", file=sys.stderr)
        return 2

    print("DEMO_DRAFT_PROBE=PASS")
    print("DEMO_NETWORK=single_workspace_detail_fetch,draft_handoff_offline")
    print("DEMO_BOUNDARY=no_fake_truth,no_auto_submit,no_send,no_preflight_provider")
    if args.preflight_only:
        print("PRODUCT_V1_LIVE_DEMO=READY")
        return 0

    run_server(
        argparse.Namespace(host=args.host, port=args.port, frontend_dist=frontend_dist)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
