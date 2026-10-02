"""Polling entry point.

    python -m bot          (recommended, works everywhere)
    python bot/main.py     (works on Windows too — see the sys.path bootstrap)

On a shared cPanel host run it detached and let cron keep it alive::

    nohup python -m bot >> data/polling.log 2>&1 &
    */5 * * * * bash /home/USER/azizi-telegram-bot/scripts/keepalive.sh
"""

from __future__ import annotations

# --- sys.path bootstrap: allows `python bot/main.py` from any cwd/OS --------
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:  # pragma: no cover - import side effect
    sys.path.insert(0, str(_ROOT))
# ---------------------------------------------------------------------------

import logging  # noqa: E402

from telegram.error import InvalidToken, NetworkError  # noqa: E402

from bot import __version__  # noqa: E402
from bot.app import ALLOWED_UPDATES, build_application  # noqa: E402
from bot.config.settings import settings  # noqa: E402
from bot.utils.logging import setup_logging  # noqa: E402

logger = logging.getLogger("bot.main")


def main() -> int:
    setup_logging(settings.log_level, settings.log_path)
    logger.info("starting azizi-telegram-bot v%s (pid=%s)", __version__, os.getpid())

    for problem in settings.validate():
        logger.warning("config: %s", problem)

    try:
        application = build_application(settings)
    except RuntimeError as exc:
        logger.critical("%s", exc)
        return 2

    logger.info("mode=polling | api_root=%s", settings.api_root)
    try:
        application.run_polling(
            allowed_updates=ALLOWED_UPDATES,
            drop_pending_updates=False,
            stop_signals=None if os.name == "nt" else None,
        )
    except InvalidToken:
        logger.critical(
            "توکن نامعتبر است. با getMe تست کنید: python scripts/diagnose.py --getme"
        )
        return 3
    except NetworkError as exc:
        logger.critical(
            "دسترسی شبکه به تلگرام برقرار نشد (%s). "
            "اگر سرور داخل ایران است، TELEGRAM_API_ROOT را تنظیم کنید.",
            exc,
        )
        return 4
    except KeyboardInterrupt:  # pragma: no cover
        logger.info("stopped by user")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
