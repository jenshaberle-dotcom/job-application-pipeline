#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_REPOSITORY_ID="1230805345"
EXPECTED_REPOSITORY="jenshaberle-dotcom/job-application-pipeline"
EXPECTED_RUNNER="job-pipeline-runtime-linux"
MIGRATED_RUNNER="job-pipeline-runtime-warm-01-linux"
READ_ONLY_FETCH_URL="https://github.com/${EXPECTED_REPOSITORY}.git"
DESKTOP_ASSET="JAP-Control-Center-Desktop-win-x64.zip"
INSTALL_SCHEMA="job_application_pipeline.windows_control_center_install.v2"
UPDATE_MODE="gui_prompt_latest_direct_v1"
COMPATIBILITY_LINE="1"
PENDING_SCHEMA="job_application_pipeline.windows_pending_update.v1"
BOOTSTRAP_MIN_VERSION="1.0.5"

blocked() {
  printf 'JAP_LOCAL_DEPLOY=BLOCKED reason=%s\n' "$1" >&2
  exit 2
}

deferred() {
  printf 'JAP_LOCAL_DEPLOY=DEFERRED reason=%s\n' "$1"
  exit 0
}

if [[ "${GITHUB_ACTIONS:-}" == "true" && "${RUNNER_NAME:-}" != "$EXPECTED_RUNNER" && "${RUNNER_NAME:-}" != "$MIGRATED_RUNNER" ]]; then
  blocked "unexpected_runner:${RUNNER_NAME:-missing}"
fi

for command_name in git python3 powershell.exe wslpath curl sha256sum; do
  command -v "$command_name" >/dev/null 2>&1 || blocked "missing_command:${command_name}"
done

SOURCE_SHA="$(git -C "$ROOT" rev-parse HEAD)"
[[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || blocked "invalid_source_sha"
ORIGIN="$(git -C "$ROOT" remote get-url origin)"
[[ "$ORIGIN" == *"$EXPECTED_REPOSITORY"* ]] || blocked "repository_origin_mismatch"

REMOTE_MAIN="$(git ls-remote "$READ_ONLY_FETCH_URL" refs/heads/main | awk 'NR==1 {print $1}')"
[[ "$REMOTE_MAIN" =~ ^[0-9a-f]{40}$ ]] || blocked "main_resolution_failed"
if [[ "$REMOTE_MAIN" != "$SOURCE_SHA" ]]; then
  deferred "source_not_current_main:${SOURCE_SHA}:${REMOTE_MAIN}"
fi

DESKTOP_VERSION="$(tr -d '\r\n' < "$ROOT/windows/JAP.ControlCenter.Desktop/VERSION")"
[[ "$DESKTOP_VERSION" =~ ^1\.[0-9]+\.[0-9]+$ ]] || blocked "desktop_version_outside_compatibility_line:${DESKTOP_VERSION}"
DESKTOP_TAG="jap-winapp-desktop-v${DESKTOP_VERSION}"

mapfile -t compatibility < <(
  python3 - "$ROOT/windows/JAP.ControlCenter.Desktop/UPDATE_COMPATIBILITY.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data.get("schema", ""))
print(data.get("compatibility_line", ""))
print(data.get("policy", ""))
print(data.get("installer_schema", ""))
print(data.get("snooze_hours", ""))
PY
)
[[ "${#compatibility[@]}" -eq 5 ]] || blocked "compatibility_projection_failed"
[[ "${compatibility[0]}" == "job_application_pipeline.windows_update_compatibility.v1" ]] || blocked "compatibility_schema_mismatch"
[[ "${compatibility[1]}" == "$COMPATIBILITY_LINE" ]] || blocked "compatibility_line_mismatch"
[[ "${compatibility[2]}" == "latest_direct" ]] || blocked "compatibility_policy_mismatch"
[[ "${compatibility[3]}" == "$INSTALL_SCHEMA" ]] || blocked "installer_schema_mismatch"
[[ "${compatibility[4]}" == "6" ]] || blocked "snooze_contract_mismatch"

RELEASE_SHA="$(git ls-remote "$READ_ONLY_FETCH_URL" "refs/tags/${DESKTOP_TAG}" | awk 'NR==1 {print $1}')"
if [[ -z "$RELEASE_SHA" ]]; then
  deferred "desktop_release_unavailable:${DESKTOP_TAG}"
fi
[[ "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]] || blocked "desktop_release_sha_invalid:${DESKTOP_TAG}"
if [[ "$RELEASE_SHA" != "$SOURCE_SHA" ]]; then
  deferred "release_not_for_source:${DESKTOP_TAG}:${RELEASE_SHA}:${SOURCE_SHA}"
fi

RELEASE_BASE_URL="https://github.com/${EXPECTED_REPOSITORY}/releases/download/${DESKTOP_TAG}"
RELEASE_ASSET_URL="$RELEASE_BASE_URL/$DESKTOP_ASSET"
if ! curl -fsSIL --connect-timeout 5 --max-time 20 "$RELEASE_ASSET_URL" >/dev/null; then
  deferred "desktop_release_asset_unavailable:${DESKTOP_TAG}"
fi

WINDOWS_LOCALAPPDATA="$(powershell.exe -NoProfile -Command '[Environment]::GetFolderPath("LocalApplicationData")' | tr -d '\r' | tail -n 1)"
[[ -n "$WINDOWS_LOCALAPPDATA" ]] || blocked "localappdata_unavailable"
WSL_LOCALAPPDATA="$(wslpath -u "$WINDOWS_LOCALAPPDATA")"
[[ -n "$WSL_LOCALAPPDATA" ]] || blocked "localappdata_mapping_failed"
INSTALL_ROOT="$WSL_LOCALAPPDATA/JAP-Control-Center"
CURRENT_JSON="$INSTALL_ROOT/current.json"
[[ -f "$CURRENT_JSON" ]] || blocked "installed_product_not_found"

mapfile -t installed < <(
  python3 - "$CURRENT_JSON" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
print(data.get("repository_id", ""))
print(data.get("repository", ""))
print(data.get("pinned_sha", ""))
print(data.get("desktop_host_version", ""))
print(data.get("wsl_distro", ""))
print(data.get("schema", ""))
print(data.get("update_mode", ""))
print(data.get("compatibility_line", ""))
PY
)
[[ "${#installed[@]}" -eq 8 ]] || blocked "installed_config_projection_failed"
[[ "${installed[0]}" == "$EXPECTED_REPOSITORY_ID" ]] || blocked "installed_repository_id_mismatch"
[[ "${installed[1]}" == "$EXPECTED_REPOSITORY" ]] || blocked "installed_repository_name_mismatch"
[[ "${installed[5]}" == "$INSTALL_SCHEMA" ]] || blocked "installed_schema_mismatch:${installed[5]}"

if [[ -n "${WSL_DISTRO_NAME:-}" && -n "${installed[4]}" && "${installed[4]}" != "$WSL_DISTRO_NAME" ]]; then
  blocked "installed_wsl_distro_mismatch:${installed[4]}:${WSL_DISTRO_NAME}"
fi

if [[ "${installed[3]}" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  INSTALLED_MAJOR="${BASH_REMATCH[1]}"
else
  blocked "installed_desktop_version_invalid:${installed[3]}"
fi
[[ "$INSTALLED_MAJOR" == "$COMPATIBILITY_LINE" ]] || blocked "installed_compatibility_line_unsupported:${installed[3]}"

set +e
powershell.exe -NoProfile -Command '$p = Get-Process -Name "JAP.ControlCenter.Desktop" -ErrorAction SilentlyContinue; if ($null -ne $p) { exit 10 }; exit 0' >/dev/null 2>&1
process_status=$?
set -e
if [[ "$process_status" -ne 0 && "$process_status" -ne 10 ]]; then
  blocked "desktop_host_process_probe_failed:${process_status}"
fi
HOST_RUNNING=0
[[ "$process_status" -eq 10 ]] && HOST_RUNNING=1

if [[ "${installed[2]}" == "$SOURCE_SHA" && "${installed[3]}" == "$DESKTOP_VERSION" && "${installed[6]}" == "$UPDATE_MODE" ]]; then
  rm -f "$INSTALL_ROOT/state/pending-update.json"
  printf 'JAP_LOCAL_DEPLOY=NO_CHANGE\n'
  printf 'PINNED_MAIN=%s\n' "$SOURCE_SHA"
  printf 'DESKTOP_HOST_VERSION=%s\n' "$DESKTOP_VERSION"
  exit 0
fi

# One-time bridge from pre-GUI-update installations. After this succeeds the
# local runner never replaces a running/closed product silently again; it stages only.
if [[ "${installed[6]}" != "$UPDATE_MODE" || "${installed[7]}" != "$COMPATIBILITY_LINE" ]]; then
  if ((HOST_RUNNING)); then
    deferred "bootstrap_requires_closed_app:${installed[3]}:${DESKTOP_VERSION}"
  fi
  printf 'JAP_LOCAL_DEPLOY=BOOTSTRAP source=%s desktop=%s\n' "$SOURCE_SHA" "$DESKTOP_VERSION"
  bash "$ROOT/scripts/install_jap_windows_control_center.sh" --no-start

  mapfile -t bootstrapped < <(
    python3 - "$CURRENT_JSON" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
print(data.get("pinned_sha", ""))
print(data.get("desktop_host_version", ""))
print(data.get("update_mode", ""))
print(data.get("compatibility_line", ""))
PY
  )
  [[ "${bootstrapped[0]}" == "$SOURCE_SHA" ]] || blocked "bootstrap_main_sha_mismatch:${bootstrapped[0]}:${SOURCE_SHA}"
  [[ "${bootstrapped[1]}" == "$DESKTOP_VERSION" ]] || blocked "bootstrap_desktop_version_mismatch:${bootstrapped[1]}:${DESKTOP_VERSION}"
  [[ "${bootstrapped[2]}" == "$UPDATE_MODE" ]] || blocked "bootstrap_update_mode_missing"
  [[ "${bootstrapped[3]}" == "$COMPATIBILITY_LINE" ]] || blocked "bootstrap_compatibility_line_missing"
  rm -f "$INSTALL_ROOT/state/pending-update.json" "$INSTALL_ROOT/state/update-snooze.json"
  printf 'JAP_LOCAL_DEPLOY=BOOTSTRAP_PASS\n'
  printf 'PINNED_MAIN=%s\n' "$SOURCE_SHA"
  printf 'DESKTOP_HOST_VERSION=%s\n' "$DESKTOP_VERSION"
  exit 0
fi

# GUI-update capable installations receive only a staged immutable release.
STAGE_BASE="$INSTALL_ROOT/updates"
STAGE_ROOT="$STAGE_BASE/$SOURCE_SHA"
STAGE_TMP="$STAGE_BASE/.staging.$SOURCE_SHA.$$"
SOURCE_ROOT="$STAGE_TMP/source"
PAYLOAD_ROOT="$STAGE_TMP/payload"
rm -rf "$STAGE_TMP"
mkdir -p "$SOURCE_ROOT/scripts" "$SOURCE_ROOT/windows/JAP.ControlCenter.Desktop" "$PAYLOAD_ROOT" "$INSTALL_ROOT/state"

for file in \
  JAP-Control-Center.ps1 \
  Update-JAP-Control-Center.ps1 \
  Stop-JAP-Control-Center.ps1 \
  Apply-JAP-Control-Center-Update.ps1 \
  install-jap-control-center.ps1; do
  cp "$ROOT/$file" "$SOURCE_ROOT/$file"
done
cp "$ROOT/scripts/run_jap_windows_control_center.sh" "$SOURCE_ROOT/scripts/run_jap_windows_control_center.sh"
cp "$ROOT/windows/JAP.ControlCenter.Desktop/VERSION" "$SOURCE_ROOT/windows/JAP.ControlCenter.Desktop/VERSION"
cp "$ROOT/windows/JAP.ControlCenter.Desktop/UPDATE_COMPATIBILITY.json" "$SOURCE_ROOT/windows/JAP.ControlCenter.Desktop/UPDATE_COMPATIBILITY.json"

ARCHIVE="$PAYLOAD_ROOT/$DESKTOP_ASSET"
CHECKSUM="$ARCHIVE.sha256"
curl -fsSL --connect-timeout 5 --max-time 120 "$RELEASE_ASSET_URL" -o "$ARCHIVE"
curl -fsSL --connect-timeout 5 --max-time 30 "$RELEASE_ASSET_URL.sha256" -o "$CHECKSUM"
EXPECTED_HASH="$(awk 'NR==1 {print tolower($1)}' "$CHECKSUM")"
[[ "$EXPECTED_HASH" =~ ^[0-9a-f]{64}$ ]] || blocked "desktop_release_checksum_invalid"
ACTUAL_HASH="$(sha256sum "$ARCHIVE" | awk '{print tolower($1)}')"
[[ "$ACTUAL_HASH" == "$EXPECTED_HASH" ]] || blocked "desktop_release_checksum_mismatch"

rm -rf "$STAGE_ROOT"
mv "$STAGE_TMP" "$STAGE_ROOT"

WINDOWS_SOURCE_ROOT="$(wslpath -w "$STAGE_ROOT/source")"
WINDOWS_ARCHIVE="$(wslpath -w "$STAGE_ROOT/payload/$DESKTOP_ASSET")"
WINDOWS_CHECKSUM="$(wslpath -w "$STAGE_ROOT/payload/$DESKTOP_ASSET.sha256")"
PENDING_JSON="$INSTALL_ROOT/state/pending-update.json"
PENDING_TMP="$PENDING_JSON.tmp"

python3 - "$PENDING_TMP" \
  "$SOURCE_SHA" \
  "$DESKTOP_VERSION" \
  "$DESKTOP_TAG" \
  "$WINDOWS_SOURCE_ROOT" \
  "$WINDOWS_ARCHIVE" \
  "$WINDOWS_CHECKSUM" \
  "$EXPECTED_HASH" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    output,
    target_sha,
    version,
    tag,
    source_root,
    archive,
    checksum,
    sha256,
) = sys.argv[1:]
value = {
    "schema": "job_application_pipeline.windows_pending_update.v1",
    "target_main_sha": target_sha,
    "target_desktop_version": version,
    "target_release_tag": tag,
    "compatibility_line": "1",
    "installer_schema": "job_application_pipeline.windows_control_center_install.v2",
    "policy": "latest_direct",
    "source_root": source_root,
    "desktop_archive": archive,
    "desktop_checksum": checksum,
    "desktop_sha256": sha256,
    "staged_at": datetime.now(timezone.utc).isoformat(),
}
Path(output).write_text(json.dumps(value, indent=2), encoding="utf-8")
PY
mv "$PENDING_TMP" "$PENDING_JSON"

printf 'JAP_LOCAL_DEPLOY=STAGED\n'
printf 'PINNED_MAIN_TARGET=%s\n' "$SOURCE_SHA"
printf 'DESKTOP_HOST_VERSION_TARGET=%s\n' "$DESKTOP_VERSION"
printf 'UPDATE_POLICY=latest_direct\n'
printf 'UPDATE_COMPATIBILITY_LINE=%s\n' "$COMPATIBILITY_LINE"
printf 'PENDING_UPDATE=%s\n' "$WINDOWS_LOCALAPPDATA\\JAP-Control-Center\\state\\pending-update.json"
