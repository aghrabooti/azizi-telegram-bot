"""Database migrations, backup/restore and the v1.3 "phone_skipped_at" case."""

from __future__ import annotations

import sqlite3

from bot.services.database import Database


def make_legacy_db(path) -> None:
    """Recreate the shape of an old v1.3 database (with the skip column)."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            phone_skipped_at TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            kind TEXT NOT NULL,
            key TEXT,
            created_at TEXT NOT NULL,
            day TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO users(user_id, phone, phone_skipped_at, created_at) "
        "VALUES (1, NULL, '2026-01-01 10:00:00', '2026-01-01 09:00:00')"
    )
    conn.execute(
        "INSERT INTO users(user_id, phone, created_at) "
        "VALUES (2, '+989121234567', '2026-01-02 09:00:00')"
    )
    conn.commit()
    conn.close()


def test_legacy_database_is_migrated(tmp_path):
    path = tmp_path / "legacy.db"
    make_legacy_db(path)

    db = Database(path)
    columns = db._columns("users")
    assert {"phone_at", "last_seen", "is_blocked"} <= columns

    # the user who once skipped must be asked again
    row = db.query_one("SELECT phone_skipped_at FROM users WHERE user_id = 1")
    assert row["phone_skipped_at"] is None
    assert db.has_phone(1) is False
    assert db.has_phone(2) is True
    db.close()


def test_new_tables_exist(tmp_path):
    db = Database(tmp_path / "fresh.db")
    tables = {
        row["name"]
        for row in db.query("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"users", "events", "anon_messages", "content_overrides", "meta"} <= tables
    db.close()


def test_backup_and_restore_roundtrip(tmp_path):
    db = Database(tmp_path / "live.db")
    db.upsert_user(1, "sara", "سارا", None)
    db.set_phone(1, "+989121234567")
    backup = db.backup_to(tmp_path / "backup.db")
    assert backup.exists() and backup.stat().st_size > 0

    db.execute("DELETE FROM users")
    assert db.user_counts()["total"] == 0

    db.restore_from(backup)
    assert db.user_counts()["total"] == 1
    assert db.get_user(1)["phone"] == "+989121234567"
    db.close()


def test_restore_rejects_a_non_bot_database(tmp_path):
    db = Database(tmp_path / "live.db")
    bogus = tmp_path / "bogus.db"
    conn = sqlite3.connect(bogus)
    conn.execute("CREATE TABLE something(id INTEGER)")
    conn.commit()
    conn.close()

    try:
        db.restore_from(bogus)
    except ValueError as exc:
        assert "معتبر نیست" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid backup was accepted")
    db.close()


def test_anon_messages_crud(tmp_path):
    db = Database(tmp_path / "anon.db")
    message_id = db.add_anon_message("A7F3", 42, "سلام")
    assert db.anon_unread_count() == 1
    db.mark_anon_read(message_id)
    assert db.anon_unread_count() == 0
    db.save_anon_reply(message_id, "پاسخ", 999)
    row = db.anon_message(message_id)
    assert row["reply_body"] == "پاسخ" and row["replied_by"] == 999
    assert db.anon_message_by_code("A7F3")["id"] == message_id
    db.close()
