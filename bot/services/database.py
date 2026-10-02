"""SQLite storage: thread-safe, self-migrating, backup-able.

Design notes
------------
* One connection, guarded by an ``RLock``.  python-telegram-bot runs handlers
  in one event loop but ``asyncio.to_thread`` and the keepalive/backup paths can
  touch the DB from other threads, so ``check_same_thread=False`` + a lock is
  the smallest correct thing.
* Migrations are plain ``ALTER TABLE`` statements executed when a column is
  missing, so an old production database is upgraded in place (v1.3 databases
  with the ``phone_skipped_at`` column are supported: those users are asked for
  their phone number again).
* Backups use SQLite's official online backup API — safe while the bot runs.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 3


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def today() -> str:
    return date.today().isoformat()


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        self.migrate()

    # ------------------------------------------------------------------
    # schema
    # ------------------------------------------------------------------
    def migrate(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id     INTEGER PRIMARY KEY,
                    username    TEXT,
                    first_name  TEXT,
                    last_name   TEXT,
                    phone       TEXT,
                    phone_at    TEXT,
                    created_at  TEXT NOT NULL,
                    last_seen   TEXT,
                    is_blocked  INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS events (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER,
                    kind       TEXT NOT NULL,
                    key        TEXT,
                    created_at TEXT NOT NULL,
                    day        TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_day ON events(day);
                CREATE INDEX IF NOT EXISTS idx_events_key ON events(key);

                CREATE TABLE IF NOT EXISTS anon_messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    code        TEXT NOT NULL UNIQUE,
                    user_id     INTEGER NOT NULL,
                    body        TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    is_read     INTEGER NOT NULL DEFAULT 0,
                    reply_body  TEXT,
                    replied_at  TEXT,
                    replied_by  INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_anon_created ON anon_messages(created_at);

                CREATE TABLE IF NOT EXISTS content_overrides (
                    key        TEXT PRIMARY KEY,
                    value      TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by INTEGER
                );

                CREATE TABLE IF NOT EXISTS meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )
            self._conn.commit()

            # --- column-level migrations for databases created by v1.x -------
            self._ensure_column("users", "phone_at", "TEXT")
            self._ensure_column("users", "last_seen", "TEXT")
            self._ensure_column("users", "is_blocked", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("anon_messages", "reply_body", "TEXT")
            self._ensure_column("anon_messages", "replied_at", "TEXT")
            self._ensure_column("anon_messages", "replied_by", "INTEGER")

            # v1.4.1: users who once pressed "later" must be asked again.
            if self._has_column("users", "phone_skipped_at"):
                cur.execute(
                    "UPDATE users SET phone_skipped_at = NULL "
                    "WHERE phone IS NULL OR phone = ''"
                )
                logger.info("migration: cleared phone_skipped_at for users without a phone")

            cur.execute(
                "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            self._conn.commit()

    def _columns(self, table: str) -> set[str]:
        cur = self._conn.execute(f"PRAGMA table_info({table})")
        return {row["name"] for row in cur.fetchall()}

    def _has_column(self, table: str, column: str) -> bool:
        return column in self._columns(table)

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        if column in self._columns(table):
            return
        try:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            self._conn.commit()
            logger.info("migration: added %s.%s", table, column)
        except sqlite3.OperationalError as exc:  # pragma: no cover
            logger.warning("migration failed for %s.%s: %s", table, column, exc)

    # ------------------------------------------------------------------
    # low level
    # ------------------------------------------------------------------
    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params).fetchall())

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    def upsert_user(
        self,
        user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> None:
        now = utcnow()
        self.execute(
            """
            INSERT INTO users(user_id, username, first_name, last_name, created_at, last_seen)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name,
                last_name  = excluded.last_name,
                last_seen  = excluded.last_seen
            """,
            (user_id, username, first_name, last_name, now, now),
        )

    def get_user(self, user_id: int) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM users WHERE user_id = ?", (user_id,))

    def set_phone(self, user_id: int, phone: str) -> None:
        self.execute(
            "UPDATE users SET phone = ?, phone_at = ? WHERE user_id = ?",
            (phone, utcnow(), user_id),
        )

    def has_phone(self, user_id: int) -> bool:
        row = self.query_one("SELECT phone FROM users WHERE user_id = ?", (user_id,))
        return bool(row and row["phone"])

    def users(self, limit: int = 50, offset: int = 0) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def all_users(self) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM users ORDER BY created_at DESC")

    def user_counts(self) -> dict[str, int]:
        total = self.query_one("SELECT COUNT(*) AS c FROM users")
        with_phone = self.query_one(
            "SELECT COUNT(*) AS c FROM users WHERE phone IS NOT NULL AND phone <> ''"
        )
        today_new = self.query_one(
            "SELECT COUNT(*) AS c FROM users WHERE substr(created_at,1,10) = ?", (today(),)
        )
        return {
            "total": total["c"] if total else 0,
            "with_phone": with_phone["c"] if with_phone else 0,
            "today": today_new["c"] if today_new else 0,
        }

    # ------------------------------------------------------------------
    # events / analytics
    # ------------------------------------------------------------------
    def log_event(self, user_id: int | None, kind: str, key: str | None = None) -> None:
        self.execute(
            "INSERT INTO events(user_id, kind, key, created_at, day) VALUES(?,?,?,?,?)",
            (user_id, kind, key, utcnow(), today()),
        )

    def event_counts(self) -> dict[str, int]:
        total = self.query_one("SELECT COUNT(*) AS c FROM events")
        today_count = self.query_one("SELECT COUNT(*) AS c FROM events WHERE day = ?", (today(),))
        active_today = self.query_one(
            "SELECT COUNT(DISTINCT user_id) AS c FROM events WHERE day = ?", (today(),)
        )
        return {
            "total": total["c"] if total else 0,
            "today": today_count["c"] if today_count else 0,
            "active_today": active_today["c"] if active_today else 0,
        }

    def top_keys(self, limit: int = 10, day: str | None = None) -> list[tuple[str, int]]:
        if day:
            rows = self.query(
                "SELECT key, COUNT(*) AS c FROM events WHERE key IS NOT NULL AND day = ? "
                "GROUP BY key ORDER BY c DESC LIMIT ?",
                (day, limit),
            )
        else:
            rows = self.query(
                "SELECT key, COUNT(*) AS c FROM events WHERE key IS NOT NULL "
                "GROUP BY key ORDER BY c DESC LIMIT ?",
                (limit,),
            )
        return [(row["key"], row["c"]) for row in rows]

    def clear_events(self) -> int:
        cur = self.execute("DELETE FROM events")
        return cur.rowcount or 0

    # ------------------------------------------------------------------
    # anonymous messages
    # ------------------------------------------------------------------
    def add_anon_message(self, code: str, user_id: int, body: str) -> int:
        cur = self.execute(
            "INSERT INTO anon_messages(code, user_id, body, created_at) VALUES(?,?,?,?)",
            (code, user_id, body, utcnow()),
        )
        return int(cur.lastrowid or 0)

    def anon_messages(self, limit: int = 5, offset: int = 0) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM anon_messages ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        )

    def anon_count(self) -> int:
        row = self.query_one("SELECT COUNT(*) AS c FROM anon_messages")
        return row["c"] if row else 0

    def anon_unread_count(self) -> int:
        row = self.query_one("SELECT COUNT(*) AS c FROM anon_messages WHERE is_read = 0")
        return row["c"] if row else 0

    def anon_message(self, message_id: int) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM anon_messages WHERE id = ?", (message_id,))

    def anon_message_by_code(self, code: str) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM anon_messages WHERE code = ?", (code,))

    def mark_anon_read(self, message_id: int) -> None:
        self.execute("UPDATE anon_messages SET is_read = 1 WHERE id = ?", (message_id,))

    def save_anon_reply(self, message_id: int, body: str, admin_id: int) -> None:
        self.execute(
            "UPDATE anon_messages SET reply_body = ?, replied_at = ?, replied_by = ?, "
            "is_read = 1 WHERE id = ?",
            (body, utcnow(), admin_id, message_id),
        )

    def last_anon_at(self, user_id: int) -> str | None:
        row = self.query_one(
            "SELECT created_at FROM anon_messages WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        return row["created_at"] if row else None

    # ------------------------------------------------------------------
    # content overrides
    # ------------------------------------------------------------------
    def get_override(self, key: str) -> str | None:
        row = self.query_one("SELECT value FROM content_overrides WHERE key = ?", (key,))
        return row["value"] if row else None

    def all_overrides(self) -> dict[str, str]:
        return {row["key"]: row["value"] for row in self.query("SELECT * FROM content_overrides")}

    def set_override(self, key: str, value: str, admin_id: int | None = None) -> None:
        self.execute(
            "INSERT INTO content_overrides(key, value, updated_at, updated_by) VALUES(?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
            "updated_at=excluded.updated_at, updated_by=excluded.updated_by",
            (key, value, utcnow(), admin_id),
        )

    def delete_override(self, key: str) -> None:
        self.execute("DELETE FROM content_overrides WHERE key = ?", (key,))

    # ------------------------------------------------------------------
    # maintenance
    # ------------------------------------------------------------------
    def backup_to(self, target: Path) -> Path:
        """Official SQLite online backup (safe while the bot is running)."""
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            dest = sqlite3.connect(str(target))
            try:
                self._conn.backup(dest)
            finally:
                dest.close()
        return target

    def restore_from(self, source: Path) -> None:
        """Replace current data with the content of *source* (validated first)."""
        source = Path(source)
        probe = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        try:
            tables = {
                row[0]
                for row in probe.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        finally:
            probe.close()
        missing = {"users", "events"} - tables
        if missing:
            raise ValueError(f"فایل پشتیبان معتبر نیست (جدول‌های گمشده: {', '.join(missing)})")

        with self._lock:
            src = sqlite3.connect(str(source))
            try:
                src.backup(self._conn)
            finally:
                src.close()
            self._conn.commit()
        self.migrate()

    def stats_snapshot(self) -> dict[str, Any]:
        return {
            "users": self.user_counts(),
            "events": self.event_counts(),
            "top_all": self.top_keys(8),
            "top_today": self.top_keys(8, day=today()),
            "anon_total": self.anon_count(),
            "anon_unread": self.anon_unread_count(),
            "db_size": self.path.stat().st_size if self.path.exists() else 0,
        }


# ---------------------------------------------------------------------------
# module-level singleton
# ---------------------------------------------------------------------------
_db: Database | None = None
_db_lock = threading.Lock()


def get_db(path: Path | str | None = None) -> Database:
    global _db
    with _db_lock:
        if _db is None:
            if path is None:
                from bot.config.settings import settings

                path = settings.db_path
            _db = Database(path)
        return _db


def set_db(db: Database | None) -> None:
    """Used by tests to inject a temporary database."""
    global _db
    with _db_lock:
        _db = db


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]
