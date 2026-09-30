"""Build and launch the local JAP Control Center.

The launcher owns only local runtime preparation:
- configure the private document root;
- build or reuse the React frontend;
- publish installed application identity;
- verify the immutable installed-runtime feature contract when requested;
- start the reviewed operator Control Center.

It does not materialize employer connectors, run ingestion, mutate ranking truth,
submit applications, or perform startup provider calls.
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

ROOT = Path(__file__).resolve().parents[1]
if not __package__ and str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_product_v1_operator_control_center import (  # noqa: E402
    configure_private_document_root,
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
    "assessment_cohort_policy": "bounded_current_product_truth",
    "combined_score_authority": False,
    "static_cache_control": "no-store,max-age=0",
    "frontend_generation_binding": "source_sha",
}
_FRONTEND_LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json")


def _configure_launcher_private_document_root() -> Path:
    raw = os.environ.get("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", "").strip()
    if not raw:
        os.environ["PRODUCT_V1_PRIVATE_DOCUMENT_ROOT"] = str(
            (ROOT / "private_application_sources").resolve()
        )
    return configure_private_document_root()


def _run(command: list[str], *, cwd: Path) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def _frontend_install_command(npm: str) -> tuple[list[str], str]:
    if any((FRONTEND / name).is_file() for name in _FRONTEND_LOCKFILES):
        return [npm, "ci"], "LOCKFILE_CI"
    return (
        [npm, "install", "--package-lock=false", "--no-audit", "--no-fund"],
        "LOCKFILE_ABSENT_INSTALL",
    )


def _installed_source_revision() -> str | None:
    raw = os.environ.get("JAP_CONTROL_CENTER_PINNED_SHA", "").strip().lower()
    if len(raw) == 40 and all(ch in "0123456789abcdef" for ch in raw):
        return raw
    return None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_marker_path(frontend_dist: Path) -> Path:
    return frontend_dist / FRONTEND_SOURCE_MARKER


def _verify_installed_runtime_feature_contract(
    frontend_dist: Path,
) -> dict[str, object]:
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
        if (
            not relative_text
            or relative_text.startswith("../")
            or "/../" in relative_text
        ):
            raise RuntimeError(f"invalid critical runtime path: {relative!r}")
        target = (ROOT / relative_text).resolve()
        if ROOT.resolve() not in {target, *target.parents}:
            raise RuntimeError(
                f"critical runtime path escaped runtime root: {relative_text}"
            )
        if not target.is_file():
            raise RuntimeError(f"critical runtime file is missing: {relative_text}")
        if _file_sha256(target) != str(expected_hash or "").strip().lower():
            raise RuntimeError(
                f"critical runtime file hash mismatch: {relative_text}"
            )

    marker = _source_marker_path(frontend_dist)
    if (
        not marker.is_file()
        or marker.read_text(encoding="utf-8").strip().lower() != expected_source
    ):
        raise RuntimeError("installed frontend source marker mismatch")

    print(
        "JAP_RUNTIME_FEATURE_CONTRACT=PASS "
        f"version={version} source={expected_source} files={len(critical_files)}"
    )
    return raw


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
            f"--reuse-frontend source mismatch: built={actual or 'unknown'} "
            f"installed={expected}"
        )


def _publish_app_info(frontend_dist: Path) -> None:
    desktop_version = DESKTOP_VERSION_FILE.read_text(encoding="utf-8").strip()
    if not desktop_version:
        raise RuntimeError("desktop VERSION is empty")
    compatibility = json.loads(
        UPDATE_COMPATIBILITY_FILE.read_text(encoding="utf-8")
    )
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
        "compatibility_line": str(
            compatibility.get("compatibility_line") or "unknown"
        ),
    }
    target = frontend_dist / "app-info.json"
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"JAP_APP_INFO=PASS version={desktop_version} source={source_revision}"
    )


def prepare_frontend(*, reuse_frontend: bool) -> Path:
    dist = DEFAULT_DIST.resolve()
    if reuse_frontend:
        if not (dist / "index.html").is_file():
            raise RuntimeError(
                "--reuse-frontend requested but no built Control Center exists"
            )
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
        help="Reuse an existing source-bound frontend build.",
    )
    parser.add_argument(
        "--installed-runtime",
        action="store_true",
        help="Verify immutable installed runtime identity before serving.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        private_document_root = _configure_launcher_private_document_root()
    except OSError as exc:
        print(f"JAP_START_BLOCKED=private_document_root:{exc}", file=sys.stderr)
        return 2
    print(f"JAP_PRIVATE_DOCUMENT_ROOT={private_document_root}")

    try:
        frontend_dist = prepare_frontend(reuse_frontend=args.reuse_frontend)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"JAP_START_BLOCKED=frontend:{exc}", file=sys.stderr)
        return 2

    try:
        _publish_app_info(frontend_dist)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"JAP_APP_INFO=UNAVAILABLE reason={exc}", file=sys.stderr)

    if args.installed_runtime:
        try:
            _verify_installed_runtime_feature_contract(frontend_dist)
        except (OSError, RuntimeError, json.JSONDecodeError) as exc:
            print(
                f"JAP_START_BLOCKED=runtime_feature_contract:{exc}",
                file=sys.stderr,
            )
            return 2

    print("JAP_CONTROL_CENTER=READY_TO_SERVE")
    print("JAP_STARTUP_NETWORK=local_only")
    print("JAP_STARTUP_BOUNDARY=no_connector_activation,no_ingestion,no_auto_submit,no_send")
    run_server(
        argparse.Namespace(
            host=args.host,
            port=args.port,
            frontend_dist=frontend_dist,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
