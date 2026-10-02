"""Live content overrides (admins edit texts from inside Telegram).

Overrides live in SQLite, so they survive a restart / redeploy.  A tiny
in-process cache keeps rendering cheap; it is invalidated on every write.
"""

from __future__ import annotations

import logging
import threading

from bot.config import content
from bot.services.database import Database

logger = logging.getLogger(__name__)


class ContentStore:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._lock = threading.RLock()
        self._cache: dict[str, str] | None = None

    def _ensure(self) -> dict[str, str]:
        with self._lock:
            if self._cache is None:
                self._cache = self.db.all_overrides()
            return self._cache

    def get(self, key: str) -> str | None:
        return self._ensure().get(key)

    def set(self, key: str, value: str, admin_id: int | None = None) -> None:
        self.db.set_override(key, value, admin_id)
        with self._lock:
            self._cache = None
        logger.info("content override updated: %s (by %s)", key, admin_id)

    def reset(self, key: str) -> None:
        self.db.delete_override(key)
        with self._lock:
            self._cache = None
        logger.info("content override removed: %s", key)

    def all(self) -> dict[str, str]:
        return dict(self._ensure())

    def install(self) -> None:
        """Make ``content.text()`` consult this store."""
        content.set_override_resolver(self.get)


_store: ContentStore | None = None


def get_store(db: Database | None = None) -> ContentStore:
    global _store
    if _store is None:
        if db is None:
            from bot.services.database import get_db

            db = get_db()
        _store = ContentStore(db)
        _store.install()
    return _store


def set_store(store: ContentStore | None) -> None:
    global _store
    _store = store
    content.set_override_resolver(store.get if store else None)
