#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_REPOSITORY_ID="1230805345"
EXPECTED_REPOSITORY="jenshaberle-dotcom/job-application-pipeline"
EXPECTED_RUNNER="job-pipeline-runtime-linux"
READ_ONLY_FETCH_URL="https://github.com/${EXPECTED_REPOSITORY}.git"
DESKTOP_ASSET="JAP-Control-Center-Desktop-win-x64.zip"

blocked() {
  printf 'JAP_LOCAL_DEPLOY=BLOCKED reason=%s\n' "$1" >&2
  exit 2
}

deferred() {
  printf 'JAP_LOCAL_DEPLOY=DEFERRED reason=%s\n' "$1"
  exit 0
}

if [[ "${GITHUB_ACTIONS:-}" == "true" && "${RUNNER_NAME:-}" != "$EXPECTED_RUNNER" ]]; then
  blocked "unexpected_runner:${RUNNER_NAME:-missing}"
fi

for command_name in git python3 powershell.exe wslpath curl; do
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
[[ "$DESKTOP_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || blocked "invalid_desktop_version"
DESKTOP_TAG="jap-winapp-desktop-v${DESKTOP_VERSION}"
RELEASE_ASSET_URL="https://github.com/${EXPECTED_REPOSITORY}/releases/download/${DESKTOP_TAG}/${DESKTOP_ASSET}"
if ! curl -fsSIL --connect-timeout 5 --max-time 20 "$RELEASE_ASSET_URL" >/dev/null; then
  deferred "desktop_release_unavailable:${DESKTOP_TAG}"
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

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8-sig"))
print(data.get("repository_id", ""))
print(data.get("repository", ""))
print(data.get("pinned_sha", ""))
print(data.get("desktop_host_version", ""))
print(data.get("wsl_distro", ""))
PY
)
[[ "${#installed[@]}" -eq 5 ]] || blocked "installed_config_projection_failed"
[[ "${installed[0]}" == "$EXPECTED_REPOSITORY_ID" ]] || blocked "installed_repository_id_mismatch"
[[ "${installed[1]}" == "$EXPECTED_REPOSITORY" ]] || blocked "installed_repository_name_mismatch"

if [[ -n "${WSL_DISTRO_NAME:-}" && -n "${installed[4]}" && "${installed[4]}" != "$WSL_DISTRO_NAME" ]]; then
  blocked "installed_wsl_distro_mismatch:${installed[4]}:${WSL_DISTRO_NAME}"
fi

set +e
powershell.exe -NoProfile -Command '$p = Get-Process -Name "JAP.ControlCenter.Desktop" -ErrorAction SilentlyContinue; if ($null -ne $p) { exit 10 }; exit 0' >/dev/null 2>&1
process_status=$?
set -e
if [[ "$process_status" -eq 10 ]]; then
  deferred "desktop_host_running"
elif [[ "$process_status" -ne 0 ]]; then
  blocked "desktop_host_process_probe_failed:${process_status}"
fi

if [[ "${installed[2]}" == "$SOURCE_SHA" && "${installed[3]}" == "$DESKTOP_VERSION" ]]; then
  printf 'JAP_LOCAL_DEPLOY=NO_CHANGE\n'
  printf 'PINNED_MAIN=%s\n' "$SOURCE_SHA"
  printf 'DESKTOP_HOST_VERSION=%s\n' "$DESKTOP_VERSION"
  exit 0
fi

printf 'JAP_LOCAL_DEPLOY=APPLY source=%s desktop=%s\n' "$SOURCE_SHA" "$DESKTOP_VERSION"
bash "$ROOT/scripts/install_jap_windows_control_center.sh" --no-start

mapfile -t deployed < <(
  python3 - "$CURRENT_JSON" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
print(data.get("repository_id", ""))
print(data.get("repository", ""))
print(data.get("pinned_sha", ""))
print(data.get("desktop_host_version", ""))
PY
)
[[ "${#deployed[@]}" -eq 4 ]] || blocked "deployed_config_projection_failed"
[[ "${deployed[0]}" == "$EXPECTED_REPOSITORY_ID" ]] || blocked "deployed_repository_id_mismatch"
[[ "${deployed[1]}" == "$EXPECTED_REPOSITORY" ]] || blocked "deployed_repository_name_mismatch"
[[ "${deployed[2]}" == "$SOURCE_SHA" ]] || blocked "deployed_main_sha_mismatch:${deployed[2]}:${SOURCE_SHA}"
[[ "${deployed[3]}" == "$DESKTOP_VERSION" ]] || blocked "deployed_desktop_version_mismatch:${deployed[3]}:${DESKTOP_VERSION}"

printf 'JAP_LOCAL_DEPLOY=PASS\n'
printf 'PINNED_MAIN=%s\n' "$SOURCE_SHA"
printf 'DESKTOP_HOST_VERSION=%s\n' "$DESKTOP_VERSION"
printf 'INSTALL_ROOT=%s\n' "$WINDOWS_LOCALAPPDATA\\JAP-Control-Center"
