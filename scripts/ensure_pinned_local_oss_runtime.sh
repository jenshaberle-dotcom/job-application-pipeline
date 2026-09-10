#!/usr/bin/env bash
set -euo pipefail

RUNTIME_PYTHON="${1:-${RUNTIME_PYTHON:-python3}}"
REQUIREMENTS_FILE="${2:-requirements.txt}"
SITE_ROOT="${3:-.runtime/local-oss-sites}"

if [ ! -x "$RUNTIME_PYTHON" ]; then
  echo "LOCAL_OSS_RUNTIME_INTERPRETER_INVALID=$RUNTIME_PYTHON" >&2
  exit 1
fi
if [ ! -f "$REQUIREMENTS_FILE" ]; then
  echo "LOCAL_OSS_RUNTIME_REQUIREMENTS_MISSING=$REQUIREMENTS_FILE" >&2
  exit 1
fi

mapfile -t SPECS < <(
  "$RUNTIME_PYTHON" - "$REQUIREMENTS_FILE" <<'PY'
from __future__ import annotations

from pathlib import Path
import sys

path = Path(sys.argv[1])
required = ("extruct", "trafilatura")
found: dict[str, str] = {}
for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    for name in required:
        if line.lower().startswith(name + "=="):
            if name in found:
                raise SystemExit(f"duplicate pinned requirement for {name}")
            found[name] = line
missing = [name for name in required if name not in found]
if missing:
    raise SystemExit("missing exact pinned local OSS requirements: " + ",".join(missing))
for name in required:
    print(found[name])
PY
)

if [ "${#SPECS[@]}" -ne 2 ]; then
  echo "LOCAL_OSS_RUNTIME_PIN_SET_INVALID" >&2
  exit 1
fi

PIN_DIGEST="$(printf '%s\n' "${SPECS[@]}" | sha256sum | awk '{print $1}')"
SITE_DIR="$SITE_ROOT/$PIN_DIGEST"
mkdir -p "$SITE_ROOT"

verify_site() {
  local site="$1"
  PYTHONPATH="$site${PYTHONPATH:+:$PYTHONPATH}" "$RUNTIME_PYTHON" - <<'PY' >/dev/null
import extruct
import trafilatura
assert extruct is not None
assert trafilatura is not None
PY
}

if [ -d "$SITE_DIR" ] && verify_site "$SITE_DIR"; then
  printf '%s\n' "$SITE_DIR"
  exit 0
fi

TMP_DIR="$SITE_ROOT/.tmp-${PIN_DIGEST}-$$"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

"$RUNTIME_PYTHON" -m pip install \
  --disable-pip-version-check \
  --no-input \
  --target "$TMP_DIR" \
  "${SPECS[@]}" >&2

verify_site "$TMP_DIR"
rm -rf "$SITE_DIR"
mv "$TMP_DIR" "$SITE_DIR"
trap - EXIT

printf '%s\n' "$SITE_DIR"
