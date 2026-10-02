#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# keepalive: restart the polling process if it died.
#
# ⚠️ The pgrep pattern MUST live inside this file.
#    If you put it directly in the crontab line, cron's own command line
#    contains the pattern, pgrep matches *itself* (proven false positive) and
#    the bot is never restarted.
#
# Crontab line — exactly this, nothing more:
#    */5 * * * * bash /home/USER/azizi-telegram-bot/scripts/keepalive.sh
# ---------------------------------------------------------------------------
set -u

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR" || exit 1

# Python interpreter: virtualenv first, then the cPanel one, then system python
if [ -x "$APP_DIR/.venv/bin/python" ]; then
  PY="$APP_DIR/.venv/bin/python"
elif [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
  PY="$VIRTUAL_ENV/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi

LOG_DIR="$APP_DIR/data"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/polling.log"
KEEP_LOG="$LOG_DIR/keepalive.log"
LOCK_FILE="$LOG_DIR/keepalive.lock"

# the pattern that identifies a running bot process (kept out of the cron line)
PATTERN='[p]ython.* -m bot'

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') | $*" >> "$KEEP_LOG"; }

# never run two keepalives at the same time
exec 9>"$LOCK_FILE"
if command -v flock >/dev/null 2>&1; then
  flock -n 9 || exit 0
fi

if pgrep -f "$PATTERN" > /dev/null 2>&1; then
  exit 0
fi

log "bot is down → starting with $PY"
nohup "$PY" -m bot >> "$LOG_FILE" 2>&1 &
sleep 3

if pgrep -f "$PATTERN" > /dev/null 2>&1; then
  log "started successfully (pid $(pgrep -f "$PATTERN" | head -1))"
else
  log "ERROR: start failed — see $LOG_FILE"
  tail -n 5 "$LOG_FILE" >> "$KEEP_LOG" 2>/dev/null
fi
