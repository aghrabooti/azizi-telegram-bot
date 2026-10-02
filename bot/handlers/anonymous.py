"""Anonymous messages.

Privacy model chosen by the owner: **strictly anonymous**.  Admins only ever
see a random code such as ``#A7F3`` — no name, no username, no phone number,
not even an "unmask" button.  The mapping code -> user id exists only in the
database so that a reply can be delivered.

Admins can answer in two ways:
  * press ✍️ پاسخ in the admin panel (پنل ادمین → پیام‌های ناشناس), or
  * simply *reply* (Reply) to the notification message in their private chat.
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot import constants as C
from bot.config import content
from bot.config.settings import settings
from bot.handlers.common import (
    answer,
    get_awaiting,
    remember_user,
    set_awaiting,
    show_page,
)
from bot.keyboards.menus import buttons_markup
from bot.services.analytics import KIND_ANON, track
from bot.services.database import get_db
from bot.services.navigation import Button, render_anon_intro, render_static

logger = logging.getLogger(__name__)

AWAIT_ANON = "anon"
AWAIT_ADMIN_REPLY = "anon_reply"  # value: ("anon_reply", message_id)

MIN_LENGTH = 5
MAX_LENGTH = 4000
RATE_LIMIT_SECONDS = 30
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_IN_TEXT = re.compile(r"#([A-Z0-9]{4})")


def new_code() -> str:
    db = get_db()
    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
        if db.anon_message_by_code(code) is None:
            return code
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))  # pragma: no cover


def _rate_limited(user_id: int) -> bool:
    raw = get_db().last_anon_at(user_id)
    if not raw:
        return False
    try:
        last = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:  # pragma: no cover
        return False
    return datetime.now(timezone.utc) - last < timedelta(seconds=RATE_LIMIT_SECONDS)


# ---------------------------------------------------------------------------
# user side
# ---------------------------------------------------------------------------
async def on_anon_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    remember_user(update)
    await answer(update)
    set_awaiting(context, AWAIT_ANON)
    track(update.effective_user.id if update.effective_user else None, KIND_ANON, "open")
    await show_page(update, context, render_anon_intro())


async def on_anon_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle a message while the user is composing an anonymous message.

    Returns ``True`` when the message was consumed.
    """
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return False
    if get_awaiting(context) != AWAIT_ANON:
        return False

    if message.text is None:
        await message.reply_text(content.text("anon.only_text"))
        return True

    body = message.text.strip()
    if len(body) < MIN_LENGTH:
        await message.reply_text(content.text("anon.too_short"))
        return True
    if len(body) > MAX_LENGTH:
        await message.reply_text(content.text("anon.too_long"))
        return True
    if _rate_limited(user.id):
        await message.reply_text(content.text("anon.rate_limited"))
        return True

    code = new_code()
    message_id = get_db().add_anon_message(code, user.id, body)
    set_awaiting(context, None)
    track(user.id, KIND_ANON, "sent")

    await message.reply_text(
        content.text("anon.sent", code=f"#{code}"),
        parse_mode=ParseMode.HTML,
    )
    await show_page(update, context, render_static(C.PAGE_MAIN), force_new=True)
    await notify_admins(context, message_id, code, body)
    return True


# ---------------------------------------------------------------------------
# admin side
# ---------------------------------------------------------------------------
def notification_text(code: str, body: str, when: str | None = None) -> str:
    from bot.utils.text import esc

    head = f"🕵️ <b>پیام ناشناس جدید</b>  <code>#{code}</code>"
    if when:
        head += f"\n🕐 {when}"
    rule = "➖➖➖➖➖➖➖➖➖➖"
    footer = "برای پاسخ، روی همین پیام Reply کنید."
    return f"{head}\n{rule}\n{esc(body)}\n{rule}\n{footer}"


async def notify_admins(
    context: ContextTypes.DEFAULT_TYPE, message_id: int, code: str, body: str
) -> None:
    if not settings.anon_notify:
        return
    markup = buttons_markup(
        [
            [Button("✍️ پاسخ", callback=C.admin(C.ADM_ANON, "reply", message_id))],
            [Button("📨 همه‌ی پیام‌های ناشناس", callback=C.admin(C.ADM_ANON))],
        ]
    )
    targets: list[int | str] = list(settings.admin_ids)
    if settings.anon_inbox_chat_id:
        targets.append(settings.anon_inbox_chat_id)

    for target in targets:
        try:
            await context.bot.send_message(
                chat_id=target,
                text=notification_text(code, body),
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
                disable_web_page_preview=True,
            )
        except TelegramError as exc:
            logger.warning("cannot notify %s about anon message: %s", target, exc)


async def deliver_reply(
    context: ContextTypes.DEFAULT_TYPE, message_id: int, body: str, admin_id: int
) -> bool:
    row = get_db().anon_message(message_id)
    if row is None:
        return False
    try:
        await context.bot.send_message(
            chat_id=row["user_id"],
            text=content.text("anon.reply_to_user", code=f"#{row['code']}", text=body),
            parse_mode=ParseMode.HTML,
        )
    except TelegramError as exc:
        logger.warning("cannot deliver reply for #%s: %s", row["code"], exc)
        return False
    get_db().save_anon_reply(message_id, body, admin_id)
    track(admin_id, KIND_ANON, "reply")
    return True


async def on_admin_reply_shortcut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Admin pressed Reply on a notification: route the answer by its code."""
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None or not settings.is_admin(user.id):
        return False
    source = message.reply_to_message
    if source is None or not message.text:
        return False
    haystack = source.text or source.caption or ""
    found = _CODE_IN_TEXT.search(haystack)
    if not found:
        return False
    row = get_db().anon_message_by_code(found.group(1))
    if row is None:
        return False
    ok = await deliver_reply(context, int(row["id"]), message.text.strip(), user.id)
    await message.reply_text(
        "✅ پاسخ برای فرستنده ارسال شد."
        if ok
        else "❌ ارسال پاسخ ممکن نشد (کاربر ربات را بسته است؟)"
    )
    return True
