#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLER="$ROOT/install-jap-control-center.ps1"

[[ -f "$INSTALLER" ]] || {
  printf 'JAP_WINDOWS_APP_INSTALL=BLOCKED installer_missing=%s\n' "$INSTALLER" >&2
  exit 2
}
command -v powershell.exe >/dev/null 2>&1 || {
  printf 'JAP_WINDOWS_APP_INSTALL=BLOCKED powershell.exe_unavailable\n' >&2
  exit 2
}
command -v wslpath >/dev/null 2>&1 || {
  printf 'JAP_WINDOWS_APP_INSTALL=BLOCKED wslpath_unavailable\n' >&2
  exit 2
}

WINDOWS_INSTALLER="$(wslpath -w "$INSTALLER")"
WINDOWS_LOCALAPPDATA="$(powershell.exe -NoProfile -Command '[Environment]::GetFolderPath("LocalApplicationData")' | tr -d '\r' | tail -n 1)"
[[ -n "$WINDOWS_LOCALAPPDATA" ]] || {
  printf 'JAP_WINDOWS_APP_INSTALL=BLOCKED localappdata_unavailable\n' >&2
  exit 2
}

WSL_LOCALAPPDATA="$(wslpath -u "$WINDOWS_LOCALAPPDATA")"
[[ -n "$WSL_LOCALAPPDATA" ]] || {
  printf 'JAP_WINDOWS_APP_INSTALL=BLOCKED localappdata_wsl_mapping_failed\n' >&2
  exit 2
}
WSL_INSTALLED_RUNNER="$WSL_LOCALAPPDATA/JAP-Control-Center/run-jap-control-center-wsl.sh"

exec powershell.exe \
  -NoProfile \
  -ExecutionPolicy Bypass \
  -File "$WINDOWS_INSTALLER" \
  -WslInstalledRunnerPath "$WSL_INSTALLED_RUNNER"
