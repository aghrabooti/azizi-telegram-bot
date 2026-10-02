"""Passenger entry point (cPanel → Setup Python App → Application startup file).

Keep this file dumb: path bootstrap, .env loading, then delegate to
``bot.webhook.app``.  cPanel environment variables always win over ``.env``.

Health check:  https://your-domain/healthz
Webhook path:  value of WEBHOOK_PATH (default /telegram/webhook)
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    # override=False → real cPanel env vars take precedence over the file
    load_dotenv(ROOT / ".env", override=False)
except Exception as exc:  # pragma: no cover - dotenv missing on the host
    sys.stderr.write(f"passenger_wsgi: cannot load .env: {exc}\n")

os.environ.setdefault("PYTHONUNBUFFERED", "1")

from bot.webhook.app import application  # noqa: E402  (after the path bootstrap)

__all__ = ["application"]
