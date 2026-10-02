#!/usr/bin/env bash
# Start the bot detached (shared cPanel hosting style).
#   bash scripts/start_polling.sh
set -eu

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

if [ -x "$APP_DIR/.venv/bin/python" ]; then
  PY="$APP_DIR/.venv/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi

mkdir -p data
PATTERN='[p]ython.* -m bot'
if pgrep -f "$PATTERN" > /dev/null 2>&1; then
  echo "ℹ️ ربات از قبل در حال اجراست (pid $(pgrep -f "$PATTERN" | head -1))"
  exit 0
fi

nohup "$PY" -m bot >> data/polling.log 2>&1 &
sleep 3
if pgrep -f "$PATTERN" > /dev/null 2>&1; then
  echo "✅ اجرا شد (pid $(pgrep -f "$PATTERN" | head -1)) — لاگ: data/polling.log"
else
  echo "❌ اجرا نشد. آخرین خطوط لاگ:"
  tail -n 20 data/polling.log
  exit 1
fi
