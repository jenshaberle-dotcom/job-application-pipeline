#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-}"
RUNTIME_ROOT="${2:-}"
PINNED_SHA="${3:-}"
STATE_ROOT="${4:-}"
ACTION="${5:-start}"
DETACHED_STDOUT="${6:-}"
DETACHED_STDERR="${7:-}"
EXPECTED_REPOSITORY_ID='1230805345'
PID_FILE="${STATE_ROOT}/runtime.pid"
RUNTIME_INFO="${RUNTIME_ROOT}/runtime-info.json"
FRONTEND_DIST="${RUNTIME_ROOT}/frontend/control-center/dist"
FRONTEND_BUILD_SHA_FILE="${FRONTEND_DIST}/.jap-source-sha"
CODEX_BINARY="${RUNTIME_ROOT}/vendor/codex/codex"
CODEX_INFO="${RUNTIME_ROOT}/vendor/codex/codex-info.json"

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
require_nonempty runtime_root "$RUNTIME_ROOT"
require_nonempty pinned_sha "$PINNED_SHA"
require_nonempty state_root "$STATE_ROOT"
[[ "$PROJECT_ROOT" == /* ]] || fail project_root_not_absolute
[[ "$RUNTIME_ROOT" == /* ]] || fail runtime_root_not_absolute
[[ "$STATE_ROOT" == /* ]] || fail state_root_not_absolute
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
  expected_cwd="$(readlink -f "$RUNTIME_ROOT" 2>/dev/null || true)"
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
[[ "$ACTION" == "start" || "$ACTION" == "launch" ]] || fail invalid_action

if [[ "$ACTION" == "launch" ]]; then
  require_nonempty detached_stdout "$DETACHED_STDOUT"
  require_nonempty detached_stderr "$DETACHED_STDERR"
  [[ "$DETACHED_STDOUT" == /* ]] || fail detached_stdout_not_absolute
  [[ "$DETACHED_STDERR" == /* ]] || fail detached_stderr_not_absolute
  command -v nohup >/dev/null 2>&1 || fail nohup_unavailable
  command -v setsid >/dev/null 2>&1 || fail setsid_unavailable
  mkdir -p "$(dirname "$DETACHED_STDOUT")" "$(dirname "$DETACHED_STDERR")"
  : > "$DETACHED_STDOUT"
  : > "$DETACHED_STDERR"
  nohup setsid bash "$0" \
    "$PROJECT_ROOT" \
    "$RUNTIME_ROOT" \
    "$PINNED_SHA" \
    "$STATE_ROOT" \
    start \
    >"$DETACHED_STDOUT" \
    2>"$DETACHED_STDERR" \
    </dev/null &
  detached_pid=$!
  sleep 0.25
  if ! kill -0 "$detached_pid" 2>/dev/null; then
    detached_status=0
    wait "$detached_pid" || detached_status=$?
    fail "detached_runtime_handoff_failed_${detached_status}"
  fi
  printf 'JAP_WINDOWS_APP_DETACHED_HANDOFF=PASS pid=%s\n' "$detached_pid"
  exit 0
fi

[[ -x "$PROJECT_ROOT/.venv/bin/python" ]] || fail canonical_venv_missing
[[ -f "$PROJECT_ROOT/.env" ]] || fail canonical_env_missing
[[ -f "$RUNTIME_INFO" ]] || fail runtime_info_missing
[[ -f "$RUNTIME_ROOT/scripts/run_product_v1_live_demo.py" ]] || fail demo_launcher_missing
[[ -f "$RUNTIME_ROOT/scripts/ensure_pinned_local_oss_runtime.sh" ]] || fail local_oss_provisioner_missing
[[ -f "$RUNTIME_ROOT/requirements.txt" ]] || fail pinned_requirements_missing
[[ -f "$CODEX_BINARY" ]] || fail bundled_codex_missing
[[ -f "$CODEX_INFO" ]] || fail bundled_codex_info_missing
[[ -f "$FRONTEND_DIST/index.html" ]] || fail frontend_bundle_missing
[[ -f "$FRONTEND_BUILD_SHA_FILE" ]] || fail frontend_source_marker_missing

runtime_identity="$(
  "$PROJECT_ROOT/.venv/bin/python" - "$RUNTIME_INFO" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8-sig") as handle:
    payload = json.load(handle)
print(
    f"{payload.get('repository_id', '')}|"
    f"{payload.get('source_sha', '')}|"
    f"{payload.get('schema', '')}"
)
PY
)" || fail runtime_info_invalid

IFS='|' read -r runtime_repository_id runtime_source_sha runtime_schema <<<"$runtime_identity"
[[ "$runtime_repository_id" == "$EXPECTED_REPOSITORY_ID" ]] || fail runtime_repository_identity_mismatch
[[ "$runtime_source_sha" == "$PINNED_SHA" ]] || fail runtime_source_identity_mismatch
[[ "$runtime_schema" == "job_application_pipeline.runtime_bundle.v1" ]] || fail runtime_schema_mismatch

frontend_build_sha="$(tr -d '\r\n[:space:]' < "$FRONTEND_BUILD_SHA_FILE")"
[[ "$frontend_build_sha" == "$PINNED_SHA" ]] || fail frontend_source_marker_mismatch

codex_identity="$(
  "$PROJECT_ROOT/.venv/bin/python" - "$CODEX_INFO" "$CODEX_BINARY" <<'PY'
import hashlib
import json
import sys

info_path, binary_path = sys.argv[1:]
with open(info_path, encoding="utf-8-sig") as handle:
    payload = json.load(handle)
if payload.get("schema") != "job_application_pipeline.codex_runtime.v1":
    raise SystemExit("codex runtime schema mismatch")
if payload.get("version") != "0.154.0":
    raise SystemExit("codex runtime version mismatch")
if payload.get("platform") != "x86_64-unknown-linux-musl":
    raise SystemExit("codex runtime platform mismatch")
with open(binary_path, "rb") as handle:
    digest = hashlib.sha256(handle.read()).hexdigest()
if digest != payload.get("binary_sha256"):
    raise SystemExit("codex binary checksum mismatch")
print(f"{payload['version']}|{digest}")
PY
)" || fail bundled_codex_identity_invalid

IFS='|' read -r codex_version codex_binary_sha <<<"$codex_identity"
[[ "$codex_version" == "0.154.0" ]] || fail bundled_codex_version_mismatch
chmod 0755 "$CODEX_BINARY" || fail bundled_codex_not_executable

if pid="$(managed_pid 2>/dev/null)"; then
  fail "managed_runtime_already_running_pid_${pid}"
fi
rm -f "$PID_FILE"

# Reuse only the private local environment from the canonical WSL project.
# Executable product code and the prebuilt frontend come exclusively from the
# immutable runtime bundle installed under the JAP product root.
# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate"
set -a
set +u
# shellcheck disable=SC1090
source "$PROJECT_ROOT/.env"
set -u
set +a

LOCAL_OSS_SITE="$(
  bash "$RUNTIME_ROOT/scripts/ensure_pinned_local_oss_runtime.sh" \
    "$PROJECT_ROOT/.venv/bin/python" \
    "$RUNTIME_ROOT/requirements.txt" \
    "$PROJECT_ROOT/.runtime/local-oss-sites"
)" || fail pinned_local_oss_runtime_unavailable
[[ -n "$LOCAL_OSS_SITE" && -d "$LOCAL_OSS_SITE" ]] || fail pinned_local_oss_runtime_invalid
export PYTHONPATH="$LOCAL_OSS_SITE${PYTHONPATH:+:$PYTHONPATH}"
if ! python -c 'import extruct, trafilatura, pymupdf'; then
  fail pinned_local_oss_runtime_import_failed
fi

for key in POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD; do
  [[ -n "${!key:-}" ]] || fail "missing_${key}"
done

export PRODUCT_V1_PRIVATE_DOCUMENT_ROOT="$PROJECT_ROOT/private_application_sources"
export PRODUCT_V1_UI_HOST="127.0.0.1"
export PRODUCT_V1_UI_PORT="8780"
export PYTHONUNBUFFERED=1
export JAP_CONTROL_CENTER_PINNED_SHA="$PINNED_SHA"
export JAP_CODEX_EXECUTABLE="$CODEX_BINARY"

cd "$RUNTIME_ROOT"
launcher=(python -u scripts/run_product_v1_live_demo.py --installed-runtime --reuse-frontend)

printf 'JAP_WINDOWS_APP_RUNTIME_BUNDLE=%s\n' "$RUNTIME_ROOT"
printf 'JAP_WINDOWS_APP_DOCUMENT_ROOT=%s\n' "$PRODUCT_V1_PRIVATE_DOCUMENT_ROOT"
printf 'JAP_WINDOWS_APP_LOCAL_OSS_SITE=%s\n' "$LOCAL_OSS_SITE"
printf 'JAP_WINDOWS_APP_PYTHON_UNBUFFERED=1\n'
printf 'JAP_WINDOWS_APP_PINNED_SHA=%s\n' "$JAP_CONTROL_CENTER_PINNED_SHA"
printf 'JAP_WINDOWS_APP_CODEX_VERSION=%s\n' "$codex_version"
printf 'JAP_WINDOWS_APP_CODEX_SHA256=%s\n' "$codex_binary_sha"
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
