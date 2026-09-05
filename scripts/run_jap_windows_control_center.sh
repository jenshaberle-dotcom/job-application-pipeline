#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-}"
MANAGED_WORKTREE="${2:-}"
PINNED_SHA="${3:-}"
STATE_ROOT="${4:-}"
ACTION="${5:-start}"
EXPECTED_ORIGIN='jenshaberle-dotcom/job-application-pipeline'
READ_ONLY_FETCH_URL='https://github.com/jenshaberle-dotcom/job-application-pipeline.git'
PID_FILE="${STATE_ROOT}/runtime.pid"

fail() {
  printf 'JAP_WINDOWS_APP_BLOCKED=%s\n' "$1" >&2
  exit 2
}

require_nonempty() {
  local name="$1"
  local value="$2"
  [[ -n "$value" ]] || fail "missing_${name}"
}

require_nonempty project_root "$PROJECT_ROOT"
require_nonempty managed_worktree "$MANAGED_WORKTREE"
require_nonempty pinned_sha "$PINNED_SHA"
require_nonempty state_root "$STATE_ROOT"
[[ "$PINNED_SHA" =~ ^[0-9a-f]{40}$ ]] || fail invalid_pinned_sha

mkdir -p "$STATE_ROOT"

managed_pid() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid cmdline cwd expected_cwd
  pid="$(tr -dc '0-9' < "$PID_FILE")"
  [[ -n "$pid" && -r "/proc/$pid/cmdline" ]] || return 1
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
  [[ "$cmdline" == *"scripts/run_product_v1_live_demo.py"* ]] || return 1
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  expected_cwd="$(readlink -f "$MANAGED_WORKTREE" 2>/dev/null || true)"
  [[ -n "$expected_cwd" && "$cwd" == "$expected_cwd" ]] || return 1
  printf '%s' "$pid"
}

stop_managed() {
  local pid
  if ! pid="$(managed_pid)"; then
    rm -f "$PID_FILE"
    printf 'JAP_WINDOWS_APP_STOP=NO_MANAGED_RUNTIME\n'
    return 0
  fi
  kill "$pid"
  for _ in $(seq 1 40); do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$PID_FILE"
      printf 'JAP_WINDOWS_APP_STOP=PASS\n'
      return 0
    fi
    sleep 0.25
  done
  fail managed_runtime_did_not_stop
}

if [[ "$ACTION" == "--stop" ]]; then
  stop_managed
  exit 0
fi
[[ "$ACTION" == "start" ]] || fail invalid_action

[[ -d "$PROJECT_ROOT/.git" ]] || fail canonical_checkout_missing
[[ -x "$PROJECT_ROOT/.venv/bin/python" ]] || fail canonical_venv_missing
[[ -f "$PROJECT_ROOT/.env" ]] || fail canonical_env_missing

origin="$(git -C "$PROJECT_ROOT" remote get-url origin 2>/dev/null || true)"
case "$origin" in
  *"$EXPECTED_ORIGIN"|*"$EXPECTED_ORIGIN.git") ;;
  *) fail repository_origin_mismatch ;;
esac

# A pinned main commit normally already exists locally from install/update. If it does
# not, recover it over HTTPS; the managed app must not depend on GitHub SSH port 22.
if ! git -C "$PROJECT_ROOT" cat-file -e "${PINNED_SHA}^{commit}" 2>/dev/null; then
  git -C "$PROJECT_ROOT" fetch --no-tags "$READ_ONLY_FETCH_URL" main || fail github_https_fetch_failed
fi
git -C "$PROJECT_ROOT" cat-file -e "${PINNED_SHA}^{commit}" 2>/dev/null || fail pinned_sha_unavailable

if [[ -e "$MANAGED_WORKTREE/.git" ]]; then
  [[ -z "$(git -C "$MANAGED_WORKTREE" status --porcelain)" ]] || fail managed_worktree_dirty
  current_sha="$(git -C "$MANAGED_WORKTREE" rev-parse HEAD)"
  if [[ "$current_sha" != "$PINNED_SHA" ]]; then
    git -C "$MANAGED_WORKTREE" checkout --detach "$PINNED_SHA"
  fi
else
  mkdir -p "$(dirname "$MANAGED_WORKTREE")"
  git -C "$PROJECT_ROOT" worktree prune
  git -C "$PROJECT_ROOT" worktree add --detach "$MANAGED_WORKTREE" "$PINNED_SHA"
fi

[[ "$(git -C "$MANAGED_WORKTREE" rev-parse HEAD)" == "$PINNED_SHA" ]] || fail managed_worktree_sha_mismatch
[[ -f "$MANAGED_WORKTREE/scripts/run_product_v1_live_demo.py" ]] || fail demo_launcher_missing

if pid="$(managed_pid 2>/dev/null)"; then
  fail "managed_runtime_already_running_pid_${pid}"
fi
rm -f "$PID_FILE"

# Reuse the canonical private runtime environment. Secrets and private documents are
# never copied into the Windows installation or the managed code worktree.
# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate"
set -a
set +u
# shellcheck disable=SC1090
source "$PROJECT_ROOT/.env"
set -u
set +a

for key in POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD; do
  [[ -n "${!key:-}" ]] || fail "missing_${key}"
done

export PRODUCT_V1_PRIVATE_DOCUMENT_ROOT="$PROJECT_ROOT/private_application_sources"
export PRODUCT_V1_UI_HOST="127.0.0.1"
export PRODUCT_V1_UI_PORT="8780"

cd "$MANAGED_WORKTREE"
launcher=(python scripts/run_product_v1_live_demo.py)
if [[ -f frontend/control-center/dist/index.html ]]; then
  launcher+=(--reuse-frontend)
fi

printf 'JAP_WINDOWS_APP_HEAD=%s\n' "$(git rev-parse HEAD)"
printf 'JAP_WINDOWS_APP_DOCUMENT_ROOT=%s\n' "$PRODUCT_V1_PRIVATE_DOCUMENT_ROOT"
printf 'JAP_WINDOWS_APP_FETCH_TRANSPORT=https\n'
printf 'JAP_WINDOWS_APP_URI=http://127.0.0.1:8780/\n'

"${launcher[@]}" &
child=$!
printf '%s\n' "$child" > "$PID_FILE"
cleanup() {
  rm -f "$PID_FILE"
}
trap cleanup EXIT
wait "$child"
status=$?
exit "$status"
