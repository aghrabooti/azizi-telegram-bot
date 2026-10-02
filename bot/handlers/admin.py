"""Admin panel (/admin) — stats, users+CSV, logs, DB backup/restore, content,
anonymous inbox and catalog diagnostics."""

from __future__ import annotations

import csv
import io
import logging
import math
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot import constants as C
from bot.config import content
from bot.config.settings import settings
from bot.handlers.common import (
    answer,
    get_awaiting,
    is_admin,
    remember_user,
    set_awaiting,
    show_page,
)
from bot.services import admin_view
from bot.services.analytics import KIND_ADMIN, track
from bot.services.catalog import get_catalog
from bot.services.content_store import get_store
from bot.services.database import get_db
from bot.services.navigation import render_static

logger = logging.getLogger(__name__)

USERS_PAGE_SIZE = 8
ANON_PAGE_SIZE = 5
LOG_TAIL_LINES = 25

AWAIT_CONTENT = "admin_content"  # ("admin_content", index)
AWAIT_ANON_REPLY = "admin_anon_reply"  # ("admin_anon_reply", message_id)
AWAIT_RESTORE = "admin_restore"


# ---------------------------------------------------------------------------
# entry points
# ---------------------------------------------------------------------------
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    remember_user(update)
    message = update.effective_message
    if not is_admin(update):
        if message:
            await message.reply_text(content.text("error.admin_only"))
        return
    track(update.effective_user.id, KIND_ADMIN, "/admin")
    await show_page(update, context, admin_view.home(get_db().stats_snapshot()), force_new=True)


async def on_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    if not is_admin(update):
        await answer(update, content.text("error.admin_only"), alert=True)
        return

    parts = query.data.split(":")
    section = parts[1] if len(parts) > 1 else C.ADM_HOME
    action = parts[2] if len(parts) > 2 else None
    key = parts[3] if len(parts) > 3 else None
    track(update.effective_user.id, KIND_ADMIN, ":".join(parts[:3]))
    await answer(update)

    handlers = {
        C.ADM_HOME: _home,
        C.ADM_STATS: _stats,
        C.ADM_USERS: _users,
        C.ADM_LOGS: _logs,
        C.ADM_DB: _database,
        C.ADM_CONTENT: _content,
        C.ADM_ANON: _anon,
        C.ADM_CATALOG: _catalog,
    }
    handler = handlers.get(section)
    if handler is None:
        await answer(update, content.text("error.expired"), alert=True)
        return
    await handler(update, context, action, key)


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------
async def _home(update, context, action=None, key=None) -> None:
    set_awaiting(context, None)
    await show_page(update, context, admin_view.home(get_db().stats_snapshot()))


async def _stats(update, context, action=None, key=None) -> None:
    db = get_db()
    if action == "reset" and key == "yes":
        removed = db.clear_events()
        logger.info("admin %s cleared %s events", update.effective_user.id, removed)
        await answer(update, f"{removed} رویداد پاک شد", alert=True)
        await show_page(update, context, admin_view.stats(db.stats_snapshot()))
        return
    if action == "reset":
        await show_page(update, context, admin_view.stats_reset_confirm())
        return
    await show_page(update, context, admin_view.stats(db.stats_snapshot()))


async def _users(update, context, action=None, key=None) -> None:
    db = get_db()
    if action == "csv":
        await _send_users_csv(update, context)
        return
    page = int(key) if action == "page" and key and key.isdigit() else 1
    counts = db.user_counts()
    pages = max(1, math.ceil(counts["total"] / USERS_PAGE_SIZE))
    page = min(max(1, page), pages)
    rows = db.users(limit=USERS_PAGE_SIZE, offset=(page - 1) * USERS_PAGE_SIZE)
    await show_page(
        update, context, admin_view.users([dict(r) for r in rows], counts, page, pages)
    )


async def _send_users_csv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = get_db().all_users()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["user_id", "username", "first_name", "last_name", "phone",
                     "phone_at", "created_at", "last_seen"])
    for row in rows:
        writer.writerow([
            row["user_id"], row["username"] or "", row["first_name"] or "",
            row["last_name"] or "", row["phone"] or "", row["phone_at"] or "",
            row["created_at"] or "", row["last_seen"] or "",
        ])
    # UTF-8 BOM so Excel opens Persian text correctly
    payload = ("\ufeff" + buffer.getvalue()).encode("utf-8")
    filename = f"users-{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(payload),
        filename=filename,
        caption=f"📥 {len(rows)} کاربر — CSV با BOM (مناسب اکسل فارسی)",
    )


async def _logs(update, context, action=None, key=None) -> None:
    path = settings.log_path
    if action == "file":
        if not path.exists():
            await answer(update, "فایل لاگ هنوز ساخته نشده است.", alert=True)
            return
        with path.open("rb") as handle:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=handle,
                filename=path.name,
                caption="📋 فایل کامل لاگ (توکن در لاگ ذخیره نمی‌شود)",
            )
        return
    lines: list[str] = []
    size = 0
    if path.exists():
        size = path.stat().st_size
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()[-LOG_TAIL_LINES:]
    await show_page(
        update, context, admin_view.logs([line.rstrip() for line in lines], str(path), size)
    )


async def _database(update, context, action=None, key=None) -> None:
    db = get_db()
    if action == "backup":
        target = settings.data_dir / "backups" / f"bot-{datetime.now():%Y%m%d-%H%M%S}.db"
        db.backup_to(target)
        with target.open("rb") as handle:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=handle,
                filename=target.name,
                caption="💾 پشتیبان آنلاین SQLite",
            )
        return
    if action == "restore":
        set_awaiting(context, AWAIT_RESTORE)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "♻️ فایل پشتیبان (<code>.db</code>) را همین‌جا بفرستید.\n"
                "⚠️ داده‌های فعلی جایگزین می‌شوند. برای انصراف /cancel را بزنید."
            ),
            parse_mode=ParseMode.HTML,
        )
        return
    info = {
        "path": str(db.path),
        "size": db.path.stat().st_size if db.path.exists() else 0,
        "users": db.user_counts()["total"],
        "events": db.event_counts()["total"],
    }
    await show_page(update, context, admin_view.database(info))


async def _content(update, context, action=None, key=None) -> None:
    store = get_store()
    if action == "edit" and key is not None and key.isdigit():
        index = int(key)
        if index >= len(content.EDITABLE_KEYS):
            await answer(update, content.text("error.expired"), alert=True)
            return
        content_key, label = content.EDITABLE_KEYS[index]
        current = store.get(content_key) or content.default_text(content_key)
        set_awaiting(context, (AWAIT_CONTENT, index))
        await show_page(
            update,
            context,
            admin_view.content_edit(
                index, content_key, label, current, store.get(content_key) is not None
            ),
        )
        return
    if action == "reset" and key is not None and key.isdigit():
        content_key, _ = content.EDITABLE_KEYS[int(key)]
        store.reset(content_key)
        await answer(update, "به متن پیش‌فرض برگشت.", alert=True)
    set_awaiting(context, None)
    await show_page(update, context, admin_view.content_list(store.all()))


async def _anon(update, context, action=None, key=None) -> None:
    db = get_db()
    if action == "view" and key and key.isdigit():
        row = db.anon_message(int(key))
        if row is None:
            await answer(update, content.text("error.expired"), alert=True)
            return
        db.mark_anon_read(int(key))
        await show_page(update, context, admin_view.anon_detail(dict(row)))
        return
    if action == "reply" and key and key.isdigit():
        row = db.anon_message(int(key))
        if row is None:
            await answer(update, content.text("error.expired"), alert=True)
            return
        set_awaiting(context, (AWAIT_ANON_REPLY, int(key)))
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"✍️ پاسخ خود به پیام <code>#{row['code']}</code> را بنویسید.\n"
                "برای انصراف /cancel را بزنید."
            ),
            parse_mode=ParseMode.HTML,
        )
        return

    page = int(key) if action == "page" and key and key.isdigit() else 1
    total = db.anon_count()
    pages = max(1, math.ceil(total / ANON_PAGE_SIZE))
    page = min(max(1, page), pages)
    rows = db.anon_messages(limit=ANON_PAGE_SIZE, offset=(page - 1) * ANON_PAGE_SIZE)
    await show_page(
        update,
        context,
        admin_view.anon_list(
            [dict(r) for r in rows], page, pages, total, db.anon_unread_count()
        ),
    )


async def _catalog(update, context, action=None, key=None) -> None:
    service = get_catalog()
    snapshot = await service.get_async(force=action == "refresh")
    fetched = (
        datetime.fromtimestamp(snapshot.fetched_at).strftime("%Y-%m-%d %H:%M")
        if snapshot.fetched_at
        else "—"
    )
    info = {
        "source": snapshot.source,
        "fetched_at_label": fetched,
        "counts": snapshot.counts(),
        "configured": settings.supabase_configured,
        "error": snapshot.error or service.last_error,
    }
    await show_page(update, context, admin_view.catalog_status(info))


# ---------------------------------------------------------------------------
# message-driven admin flows (content edit / reply / restore)
# ---------------------------------------------------------------------------
async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Consume a text message that belongs to an admin flow. Returns True if used."""
    if not is_admin(update):
        return False
    awaiting = get_awaiting(context)
    message = update.effective_message
    if message is None or message.text is None or not isinstance(awaiting, tuple):
        return False

    kind = awaiting[0]
    if kind == AWAIT_CONTENT:
        index = int(awaiting[1])
        content_key, label = content.EDITABLE_KEYS[index]
        get_store().set(content_key, message.text, update.effective_user.id)
        set_awaiting(context, None)
        await message.reply_text(f"✅ «{label}» به‌روزرسانی شد.")
        await show_page(update, context, admin_view.content_list(get_store().all()),
                        force_new=True)
        return True

    if kind == AWAIT_ANON_REPLY:
        from bot.handlers.anonymous import deliver_reply

        ok = await deliver_reply(context, int(awaiting[1]), message.text.strip(),
                                 update.effective_user.id)
        set_awaiting(context, None)
        await message.reply_text(
            "✅ پاسخ ارسال شد." if ok else "❌ ارسال پاسخ ممکن نشد (کاربر ربات را بسته است؟)"
        )
        return True

    return False


async def handle_admin_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """DB restore: an admin uploads a .db file while in restore mode."""
    message = update.effective_message
    if message is None or message.document is None:
        return
    if not is_admin(update) or get_awaiting(context) != AWAIT_RESTORE:
        return

    document = message.document
    if not (document.file_name or "").endswith(".db"):
        await message.reply_text("فقط فایل با پسوند .db پذیرفته می‌شود.")
        return

    settings.ensure_dirs()
    target = settings.data_dir / "restore" / f"upload-{datetime.now():%Y%m%d-%H%M%S}.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    telegram_file = await document.get_file()
    await telegram_file.download_to_drive(custom_path=str(target))

    try:
        get_db().restore_from(Path(target))
    except Exception as exc:  # noqa: BLE001 - the admin needs the real reason
        logger.error("restore failed: %s", exc)
        await message.reply_text(f"❌ بازیابی ناموفق بود:\n{exc}")
        return
    finally:
        set_awaiting(context, None)

    logger.warning("database restored by admin %s from %s", update.effective_user.id, target.name)
    await message.reply_text("✅ دیتابیس بازیابی شد.")
    await show_page(update, context, admin_view.home(get_db().stats_snapshot()), force_new=True)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    set_awaiting(context, None)
    message = update.effective_message
    if message:
        await message.reply_text("لغو شد.")
    await show_page(update, context, render_static(C.PAGE_MAIN), force_new=True)
