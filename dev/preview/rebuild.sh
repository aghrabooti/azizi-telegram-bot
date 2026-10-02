#!/usr/bin/env bash
# Rebuild the preview data + zip and (re)start the preview server on :8080.
#   bash dev/preview/rebuild.sh
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi

echo "▶ building preview data from the real source…"
"$PY" dev/preview/build.py

echo "▶ building downloadable zip…"
"$PY" scripts/make_zip.py

PATTERN='[p]ython.*dev/preview/server.py'
if pgrep -f "$PATTERN" >/dev/null 2>&1; then
  echo "▶ stopping the old preview server…"
  pgrep -f "$PATTERN" | xargs kill
  sleep 1
fi

echo "▶ starting preview server on :8080"
nohup "$PY" dev/preview/server.py >> data/preview.log 2>&1 &
sleep 2
curl -fsS http://127.0.0.1:8080/healthz && echo " ← preview is up"
