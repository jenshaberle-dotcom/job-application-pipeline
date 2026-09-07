#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLER="$ROOT/install-jap-control-center.ps1"

NO_START=0
NO_SHORTCUTS=0
while (($#)); do
  case "$1" in
    --no-start)
      NO_START=1
      ;;
    --no-shortcuts)
      NO_SHORTCUTS=1
      ;;
    *)
      printf 'JAP_WINDOWS_APP_INSTALL=BLOCKED unknown_argument=%s\n' "$1" >&2
      exit 2
      ;;
  esac
  shift
done

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

args=(
  -NoProfile
  -ExecutionPolicy Bypass
  -File "$WINDOWS_INSTALLER"
  -WslInstalledRunnerPath "$WSL_INSTALLED_RUNNER"
)
if ((NO_START)); then
  args+=(-NoStart)
fi
if ((NO_SHORTCUTS)); then
  args+=(-NoShortcuts)
fi

exec powershell.exe "${args[@]}"
