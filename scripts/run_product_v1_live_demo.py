"""Prepare and launch the DEMO-001 Product V1 Control Center.

Default sequence:
1. invalidate stale readiness artifacts from any previous launcher run;
2. install/build the existing React Control Center;
3. run the fail-closed live Product V1 demo preflight;
4. probe the selected authoritative Top-5 Application Workspace with one detail fetch;
5. validate its carried provider-free evidence-first review-draft proof offline;
6. start the demo Control Center only when all readiness probes pass.

The installed Windows application uses ``--installed-runtime``. That mode keeps the
same reviewed server/action boundaries but does not block every interactive startup
on the external demo workspace probe. It still binds the generated frontend bundle
to the exact installed source SHA and publishes local app identity for About.

The launcher never changes ranking/application truth, submits, or sends anything.
Installed-demo mode may materialize the explicitly approved non-recurring ivv
generic-origin execution profile when its qualified local candidate already exists;
this grants no recurring scheduler authority and performs no ingestion. The final
readiness proof invokes no provider and performs no second vacancy fetch. Readiness
diagnostics are published
atomically only after the staged artifact parses as a JSON object and its readiness
state agrees with the child exit status. Interrupted or contradictory child output
therefore cannot become canonical. Use ``--reuse-frontend`` only for a source-bound
build matching the current installed revision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if not __package__ and str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_product_v1_demo_control_center import (  # noqa: E402
    configure_demo_private_document_root,
    run_server,
)
FRONTEND = ROOT / "frontend" / "control-center"
DEFAULT_DIST = FRONTEND / "dist"
FRONTEND_SOURCE_MARKER = ".jap-source-sha"
DESKTOP_VERSION_FILE = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "VERSION"
UPDATE_COMPATIBILITY_FILE = (
    ROOT / "windows" / "JAP.ControlCenter.Desktop" / "UPDATE_COMPATIBILITY.json"
)
RUNTIME_FEATURE_CONTRACT_FILE = ROOT / "runtime-feature-contract.json"
RUNTIME_FEATURE_CONTRACT_SCHEMA = "job_application_pipeline.runtime_feature_contract.v1"
REQUIRED_INSTALLED_FEATURES = {
    "candidate_fit_scope": "job_skills_vs_cv_skills",
    "demo_cohort_policy": "frozen_runtime_identity",
    "candidate_fit_required_count": 10,
    "affinity_required_count": 10,
    "combined_score_authority": False,
    "static_cache_control": "no-store,max-age=0",
    "frontend_generation_binding": "source_sha",
}
DEMO_ARTIFACT_ROOT = (ROOT / ".runtime" / "demo").resolve()
DEFAULT_PREFLIGHT = DEMO_ARTIFACT_ROOT / "product_v1_demo_preflight.json"
DEFAULT_WORKSPACE_PROBE = DEMO_ARTIFACT_ROOT / "product_v1_demo_workspace_probe.json"
_FRONTEND_LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json")


def _configure_launcher_private_document_root() -> Path:
    raw = os.environ.get("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", "").strip()
    if not raw:
        os.environ["PRODUCT_V1_PRIVATE_DOCUMENT_ROOT"] = str(
            (ROOT / "private_application_sources").resolve()
        )
    return configure_demo_private_document_root()


def _run(command: list[str], *, cwd: Path) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def _prepare_installed_demo_connectors() -> None:
    """Materialize demo-only, non-recurring connector profiles without ingestion."""

    command = [
        sys.executable,
        "-m",
        "scripts.run_generic_origin_demo_profile",
        "--company-key",
        "ivv",
        "--apply",
        "--approval-token",
        "DEMO-GENERIC-ORIGIN-PROFILE-001",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        reason = (completed.stderr or completed.stdout or "unknown").strip()
        print(
            f"JAP_DEMO_CONNECTOR=SKIPPED source=generic_origin:ivv reason={reason}",
            file=sys.stderr,
        )
        return
    print("JAP_DEMO_CONNECTOR=READY source=generic_origin:ivv recurring=false")


def _frontend_install_command(npm: str) -> tuple[list[str], str]:
    if any((FRONTEND / name).is_file() for name in _FRONTEND_LOCKFILES):
        return [npm, "ci"], "LOCKFILE_CI"
    return [npm, "install", "--package-lock=false", "--no-audit", "--no-fund"], "LOCKFILE_ABSENT_INSTALL"


def _installed_source_revision() -> str | None:
    raw = os.environ.get("JAP_CONTROL_CENTER_PINNED_SHA", "").strip().lower()
    if len(raw) == 40 and all(character in "0123456789abcdef" for character in raw):
        return raw
    return None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_installed_runtime_feature_contract(frontend_dist: Path) -> dict[str, object]:
    expected_source = _installed_source_revision()
    if expected_source is None:
        raise RuntimeError("installed runtime source revision is unavailable")
    if not RUNTIME_FEATURE_CONTRACT_FILE.is_file():
        raise RuntimeError("runtime feature contract is missing")

    raw = json.loads(RUNTIME_FEATURE_CONTRACT_FILE.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise RuntimeError("runtime feature contract root is not an object")
    if raw.get("schema") != RUNTIME_FEATURE_CONTRACT_SCHEMA:
        raise RuntimeError("runtime feature contract schema mismatch")
    if str(raw.get("source_sha") or "").strip().lower() != expected_source:
        raise RuntimeError("runtime feature contract source mismatch")

    version = DESKTOP_VERSION_FILE.read_text(encoding="utf-8").strip()
    if str(raw.get("version") or "").strip() != version:
        raise RuntimeError("runtime feature contract version mismatch")

    features = raw.get("features")
    if not isinstance(features, dict):
        raise RuntimeError("runtime feature contract features are missing")
    drift = {
        key: {"expected": value, "actual": features.get(key)}
        for key, value in REQUIRED_INSTALLED_FEATURES.items()
        if features.get(key) != value
    }
    if drift:
        raise RuntimeError(
            "runtime feature contract drift: "
            + json.dumps(drift, sort_keys=True, ensure_ascii=False)
        )

    critical_files = raw.get("critical_files")
    if not isinstance(critical_files, dict) or not critical_files:
        raise RuntimeError("runtime feature contract critical files are missing")
    for relative, expected_hash in sorted(critical_files.items()):
        relative_text = str(relative or "").replace("\\", "/").strip("/")
        if not relative_text or relative_text.startswith("../") or "/../" in relative_text:
            raise RuntimeError(f"invalid critical runtime path: {relative!r}")
        target = (ROOT / relative_text).resolve()
        if ROOT.resolve() not in {target, *target.parents}:
            raise RuntimeError(f"critical runtime path escaped runtime root: {relative_text}")
        if not target.is_file():
            raise RuntimeError(f"critical runtime file is missing: {relative_text}")
        actual_hash = _file_sha256(target)
        if actual_hash != str(expected_hash or "").strip().lower():
            raise RuntimeError(f"critical runtime file hash mismatch: {relative_text}")

    marker = _source_marker_path(frontend_dist)
    if not marker.is_file() or marker.read_text(encoding="utf-8").strip().lower() != expected_source:
        raise RuntimeError("installed frontend source marker mismatch")

    print(
        "JAP_RUNTIME_FEATURE_CONTRACT=PASS "
        f"version={version} source={expected_source} files={len(critical_files)}"
    )
    return raw


def _source_marker_path(frontend_dist: Path) -> Path:
    return frontend_dist / FRONTEND_SOURCE_MARKER


def _write_frontend_source_marker(frontend_dist: Path) -> None:
    source_revision = _installed_source_revision()
    if source_revision is None:
        return
    _source_marker_path(frontend_dist).write_text(
        source_revision + "\n",
        encoding="utf-8",
    )
    print(f"FRONTEND_BUILD_SOURCE={source_revision}")


def _assert_reusable_frontend_source(frontend_dist: Path) -> None:
    expected = _installed_source_revision()
    if expected is None:
        return
    marker = _source_marker_path(frontend_dist)
    if not marker.is_file():
        raise RuntimeError(
            "--reuse-frontend requested for installed runtime without source marker"
        )
    actual = marker.read_text(encoding="utf-8").strip().lower()
    if actual != expected:
        raise RuntimeError(
            f"--reuse-frontend source mismatch: built={actual or 'unknown'} installed={expected}"
        )


def _publish_app_info(frontend_dist: Path) -> None:
    """Publish local install identity into generated frontend state only."""
    desktop_version = DESKTOP_VERSION_FILE.read_text(encoding="utf-8").strip()
    if not desktop_version:
        raise RuntimeError("desktop VERSION is empty")
    compatibility = json.loads(UPDATE_COMPATIBILITY_FILE.read_text(encoding="utf-8"))
    if not isinstance(compatibility, dict):
        raise RuntimeError("update compatibility root is not an object")

    source_revision = _installed_source_revision() or "development"

    payload = {
        "schema": "job_application_pipeline.control_center_app_info.v1",
        "app_name": "JAP Control Center",
        "product_name": "Job Application Pipeline",
        "desktop_version": desktop_version,
        "source_revision": source_revision,
        "desktop_host": "WebView2 WinForms",
        "runtime_surface": "WSL-backed local runtime",
        "data_truth": "PostgreSQL / DB-backed",
        "product_mode": "review-first",
        "update_policy": str(compatibility.get("policy") or "unknown"),
        "compatibility_line": str(compatibility.get("compatibility_line") or "unknown"),
    }
    target = frontend_dist / "app-info.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"JAP_APP_INFO=PASS version={desktop_version} source={source_revision}")


def _demo_artifact_path(path: Path) -> Path:
    """Resolve one launcher diagnostic path inside the bounded demo artifact root."""
    resolved = path.resolve()
    root = DEMO_ARTIFACT_ROOT.resolve()
    if root not in {resolved, *resolved.parents}:
        raise RuntimeError(
            f"demo readiness artifact must stay under {root}: {resolved}"
        )
    if resolved.suffix.lower() != ".json":
        raise RuntimeError(f"demo readiness artifact must be a .json file: {resolved}")
    return resolved


def _invalidate_output_artifacts(*paths: Path) -> None:
    """Remove only bounded prior-run demo diagnostics before a new readiness attempt."""
    resolved_paths = tuple(_demo_artifact_path(path) for path in paths)
    for resolved in resolved_paths:
        try:
            resolved.unlink()
        except FileNotFoundError:
            continue
        print(f"DEMO_ARTIFACT_INVALIDATED={resolved}")


def prepare_frontend(*, reuse_frontend: bool) -> Path:
    dist = DEFAULT_DIST.resolve()
    if reuse_frontend:
        if not (dist / "index.html").is_file():
            raise RuntimeError("--reuse-frontend requested but no built Control Center exists")
        _assert_reusable_frontend_source(dist)
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
    _write_frontend_source_marker(dist)
    print(f"FRONTEND_BUILD=PASS path={dist}")
    return dist


def _run_module(module: str, *, arguments: list[str]) -> int:
    command = [sys.executable, "-m", module, *arguments]
    print("+ " + " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def _validate_staged_json(staged: Path, *, module: str, code: int) -> None:
    if not staged.is_file() or staged.stat().st_size == 0:
        raise RuntimeError(f"diagnostic child produced no artifact: {module}")
    try:
        payload = json.loads(staged.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"diagnostic child produced invalid JSON: {module}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"diagnostic child artifact root is not an object: {module}")
    state = str(payload.get("state") or "").casefold()
    if state not in {"pass", "blocked"}:
        raise RuntimeError(f"diagnostic child artifact has invalid readiness state: {module}")
    if (code == 0) != (state == "pass"):
        raise RuntimeError(
            f"diagnostic child exit/status disagreement: {module} code={code} state={state}"
        )


def _run_module_with_atomic_output(
    module: str,
    *,
    arguments: list[str],
    output: Path,
) -> int:
    """Run a diagnostic child against a same-directory staging file, then publish it."""
    target = _demo_artifact_path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_staged = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".pending.json",
    )
    os.close(fd)
    staged = Path(raw_staged)
    try:
        code = _run_module(module, arguments=[*arguments, "--output", str(staged)])
        _validate_staged_json(staged, module=module, code=code)
        os.replace(staged, target)
        print(f"DEMO_ARTIFACT_PUBLISHED={target}")
        return code
    finally:
        try:
            staged.unlink()
        except FileNotFoundError:
            pass


def run_preflight(*, frontend_dist: Path, output: Path) -> int:
    return _run_module_with_atomic_output(
        "scripts.run_product_v1_demo_preflight",
        arguments=["--frontend-dist", str(frontend_dist)],
        output=output,
    )


def run_workspace_probe(*, preflight: Path, output: Path) -> int:
    return _run_module_with_atomic_output(
        "scripts.run_product_v1_demo_workspace_probe",
        arguments=["--preflight", str(preflight)],
        output=output,
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
    parser.add_argument(
        "--installed-runtime",
        action="store_true",
        help=(
            "Start the installed interactive Control Center after local frontend preparation "
            "without rerunning the external demo workspace readiness probe."
        ),
    )
    parser.add_argument("--preflight-output", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--workspace-probe-output", type=Path, default=DEFAULT_WORKSPACE_PROBE)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Build/check full demo readiness without starting the HTTP server.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        private_document_root = _configure_launcher_private_document_root()
    except OSError as exc:
        print(f"DEMO_START_BLOCKED=private_document_root:{exc}", file=sys.stderr)
        return 2
    print(f"DEMO_PRIVATE_DOCUMENT_ROOT={private_document_root}")

    if args.preflight_only and args.installed_runtime:
        print(
            "DEMO_START_BLOCKED=arguments:--preflight-only and --installed-runtime are mutually exclusive",
            file=sys.stderr,
        )
        return 2

    try:
        frontend_dist = prepare_frontend(reuse_frontend=args.reuse_frontend)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"DEMO_START_BLOCKED=frontend:{exc}", file=sys.stderr)
        return 2

    try:
        _publish_app_info(frontend_dist)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"JAP_APP_INFO=UNAVAILABLE reason={exc}", file=sys.stderr)

    if args.installed_runtime:
        try:
            _verify_installed_runtime_feature_contract(frontend_dist)
        except (OSError, RuntimeError, json.JSONDecodeError) as exc:
            print(f"DEMO_START_BLOCKED=runtime_feature_contract:{exc}", file=sys.stderr)
            return 2
        _prepare_installed_demo_connectors()
        print("JAP_INSTALLED_RUNTIME=READY_TO_SERVE")
        print("JAP_INSTALLED_RUNTIME_NETWORK=startup_local_only")
        print("JAP_INSTALLED_RUNTIME_BOUNDARY=no_auto_submit,no_send,no_startup_provider")
        run_server(
            argparse.Namespace(host=args.host, port=args.port, frontend_dist=frontend_dist)
        )
        return 0

    try:
        preflight_output = _demo_artifact_path(args.preflight_output)
        workspace_probe_output = _demo_artifact_path(args.workspace_probe_output)
        _invalidate_output_artifacts(
            preflight_output,
            workspace_probe_output,
        )
    except RuntimeError as exc:
        print(f"DEMO_START_BLOCKED=artifact_path:{exc}", file=sys.stderr)
        return 2

    try:
        preflight_code = run_preflight(frontend_dist=frontend_dist, output=preflight_output)
    except RuntimeError as exc:
        print(f"DEMO_START_BLOCKED=preflight_artifact:{exc}", file=sys.stderr)
        return 2
    if preflight_code != 0:
        print("DEMO_START_BLOCKED=live_preflight", file=sys.stderr)
        print(f"PREFLIGHT_ARTIFACT={preflight_output}", file=sys.stderr)
        return 2

    print("DEMO_PREFLIGHT=PASS")
    try:
        workspace_code = run_workspace_probe(
            preflight=preflight_output,
            output=workspace_probe_output,
        )
    except RuntimeError as exc:
        print(f"DEMO_START_BLOCKED=workspace_artifact:{exc}", file=sys.stderr)
        return 2
    if workspace_code != 0:
        print("DEMO_START_BLOCKED=application_workspace_probe", file=sys.stderr)
        print(f"WORKSPACE_PROBE_ARTIFACT={workspace_probe_output}", file=sys.stderr)
        return 2

    print("DEMO_WORKSPACE_PROBE=PASS")
    print("DEMO_NETWORK=single_workspace_detail_fetch,no_generation_in_preflight")
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
