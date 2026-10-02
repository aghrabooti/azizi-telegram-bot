#!/usr/bin/env bash
# Stop the detached polling process.
set -u
PATTERN='[p]ython.* -m bot'
PIDS="$(pgrep -f "$PATTERN" || true)"
if [ -z "$PIDS" ]; then
  echo "ℹ️ ربات در حال اجرا نیست."
  exit 0
fi
echo "$PIDS" | xargs kill
sleep 2
if pgrep -f "$PATTERN" > /dev/null 2>&1; then
  echo "$PIDS" | xargs kill -9
fi
echo "✅ متوقف شد."
