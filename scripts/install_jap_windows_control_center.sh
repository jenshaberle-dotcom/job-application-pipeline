#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLER="$ROOT/install-jap-control-center.ps1"

blocked() {
  printf 'JAP_WINDOWS_APP_INSTALL=BLOCKED reason=%s\n' "$1" >&2
  exit 2
}

resolve_windows_pwsh() {
  if command -v pwsh.exe >/dev/null 2>&1; then
    command -v pwsh.exe
    return 0
  fi
  local candidate
  for candidate in \
    "/mnt/c/Program Files/PowerShell/7/pwsh.exe" \
    "/mnt/c/Program Files (x86)/PowerShell/7/pwsh.exe"; do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

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

[[ -f "$INSTALLER" ]] || blocked "installer_missing:$INSTALLER"
command -v wslpath >/dev/null 2>&1 || blocked "wslpath_unavailable"
WINDOWS_PWSH="$(resolve_windows_pwsh)" || blocked "pwsh7_unavailable"
PWSH_VERSION="$("$WINDOWS_PWSH" -NoProfile -Command '$PSVersionTable.PSVersion.ToString()' | tr -d '\r' | tail -n 1)"
[[ "$PWSH_VERSION" =~ ^7\. ]] || blocked "pwsh7_version_invalid:$PWSH_VERSION"
printf 'JAP_WINDOWS_APP_PWSH=PASS version=%s executable=%s\n' "$PWSH_VERSION" "$WINDOWS_PWSH"

WINDOWS_INSTALLER="$(wslpath -w "$INSTALLER")"
WINDOWS_LOCALAPPDATA="$("$WINDOWS_PWSH" -NoProfile -Command '[Environment]::GetFolderPath("LocalApplicationData")' | tr -d '\r' | tail -n 1)"
[[ -n "$WINDOWS_LOCALAPPDATA" ]] || blocked "localappdata_unavailable"

WSL_LOCALAPPDATA="$(wslpath -u "$WINDOWS_LOCALAPPDATA")"
[[ -n "$WSL_LOCALAPPDATA" ]] || blocked "localappdata_wsl_mapping_failed"
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

exec "$WINDOWS_PWSH" "${args[@]}"
