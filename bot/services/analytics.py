"""Usage analytics — intentionally tiny: counts per page, per day.

Every page view and command is one row in ``events``; the admin panel turns
that into "total / today / most visited".  No third-party analytics, no PII
beyond the Telegram user id that we already store.
"""

from __future__ import annotations

import logging

from bot.services.database import Database, get_db

logger = logging.getLogger(__name__)

KIND_COMMAND = "command"
KIND_PAGE = "page"
KIND_CONTACT = "contact"
KIND_ANON = "anon"
KIND_ADMIN = "admin"
KIND_ERROR = "error"


def track(user_id: int | None, kind: str, key: str | None = None, db: Database | None = None):
    """Record one event; analytics must never break a user flow."""
    try:
        (db or get_db()).log_event(user_id, kind, key)
    except Exception as exc:  # noqa: BLE001 - best effort by design
        logger.warning("analytics: could not record %s/%s: %s", kind, key, exc)


def snapshot(db: Database | None = None) -> dict:
    return (db or get_db()).stats_snapshot()
