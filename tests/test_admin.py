"""Admin panel: access control, stats, CSV, content editing, anonymous inbox."""

from __future__ import annotations

from bot import constants as C
from bot.config import content
from bot.handlers import admin as admin_handlers
from bot.handlers import anonymous as anon_handlers
from bot.handlers.common import set_awaiting
from bot.services.content_store import ContentStore, set_store
from tests.fakes import callback_update, text_update

ADMIN_ID = 999
USER_ID = 500


def register(db, user_id: int) -> None:
    db.upsert_user(user_id)
    db.set_phone(user_id, "+989121234567")


async def test_admin_command_is_refused_for_normal_users(isolated_env, context):
    register(isolated_env, USER_ID)
    update, message = text_update("/admin", user_id=USER_ID)
    await admin_handlers.cmd_admin(update, context)
    assert message.replies[0]["text"] == content.text("error.admin_only")
    assert not context.bot.messages


async def test_admin_command_opens_the_panel(isolated_env, context):
    register(isolated_env, ADMIN_ID)
    update, _ = text_update("/admin", user_id=ADMIN_ID)
    await admin_handlers.cmd_admin(update, context)
    assert "پنل مدیریت" in context.bot.texts[0]


async def test_admin_callbacks_are_refused_for_normal_users(isolated_env, context):
    register(isolated_env, USER_ID)
    update, query = callback_update(C.admin(C.ADM_USERS), user_id=USER_ID)
    await admin_handlers.on_admin_callback(update, context)
    assert query.answers[0]["alert"] is True
    assert not query.edits


async def test_stats_page_and_reset_flow(isolated_env, context):
    register(isolated_env, ADMIN_ID)
    isolated_env.log_event(USER_ID, "page", "nav:main")

    update, query = callback_update(C.admin(C.ADM_STATS), user_id=ADMIN_ID)
    await admin_handlers.on_admin_callback(update, context)
    assert "آمار" in query.edits[0]["text"]

    update, query = callback_update(C.admin(C.ADM_STATS, "reset"), user_id=ADMIN_ID)
    await admin_handlers.on_admin_callback(update, context)
    assert "مطمئن هستید" in query.edits[0]["text"]

    update, query = callback_update(C.admin(C.ADM_STATS, "reset", "yes"), user_id=ADMIN_ID)
    await admin_handlers.on_admin_callback(update, context)
    # old events are gone (the page view recorded *after* the reset may remain)
    assert all(key != "nav:main" for key, _ in isolated_env.top_keys(50))


async def test_users_csv_has_bom_for_excel(isolated_env, context):
    register(isolated_env, ADMIN_ID)
    register(isolated_env, USER_ID)
    update, _ = callback_update(C.admin(C.ADM_USERS, "csv"), user_id=ADMIN_ID)
    await admin_handlers.on_admin_callback(update, context)

    document = context.bot.documents[0]
    assert document["filename"].endswith(".csv")
    assert document["bytes"].startswith("\ufeff".encode())
    assert "+989121234567" in document["bytes"].decode("utf-8")


async def test_content_edit_persists_across_restarts(isolated_env, context):
    register(isolated_env, ADMIN_ID)
    update, query = callback_update(C.admin(C.ADM_CONTENT, "edit", 0), user_id=ADMIN_ID)
    await admin_handlers.on_admin_callback(update, context)
    assert "متن فعلی" in query.edits[0]["text"]

    update, message = text_update("متن تازه‌ی منوی اصلی", user_id=ADMIN_ID)
    context.user_data["awaiting"] = (admin_handlers.AWAIT_CONTENT, 0)
    assert await admin_handlers.handle_admin_text(update, context)
    assert content.text("main.text") == "متن تازه‌ی منوی اصلی"

    # simulate a restart: brand new store reading the same database
    set_store(ContentStore(isolated_env))
    assert content.text("main.text") == "متن تازه‌ی منوی اصلی"
    assert message.replies


async def test_anonymous_inbox_list_view_and_reply(isolated_env, context):
    register(isolated_env, ADMIN_ID)
    register(isolated_env, USER_ID)

    # user sends an anonymous message
    update, message = text_update("سلام، تخفیف دارید؟", user_id=USER_ID)
    set_awaiting(context, anon_handlers.AWAIT_ANON)
    assert await anon_handlers.on_anon_message(update, context)
    row = isolated_env.anon_messages()[0]
    assert row["body"] == "سلام، تخفیف دارید؟"

    # the notification must not leak the sender's identity
    notification = next(m for m in context.bot.messages if "پیام ناشناس جدید" in m["text"])
    assert str(USER_ID) not in notification["text"]
    assert "+98" not in notification["text"]
    assert "sara" not in notification["text"]

    # admin opens the list, then the message
    update, query = callback_update(C.admin(C.ADM_ANON), user_id=ADMIN_ID)
    await admin_handlers.on_admin_callback(update, context)
    assert f"#{row['code']}" in query.edits[0]["text"]

    update, query = callback_update(
        C.admin(C.ADM_ANON, "view", row["id"]), user_id=ADMIN_ID
    )
    await admin_handlers.on_admin_callback(update, context)
    assert "تخفیف" in query.edits[0]["text"]
    assert isolated_env.anon_message(row["id"])["is_read"] == 1

    # admin replies from the panel
    context.user_data["awaiting"] = (admin_handlers.AWAIT_ANON_REPLY, int(row["id"]))
    update, _ = text_update("بله، با پشتیبانی تماس بگیرید.", user_id=ADMIN_ID)
    assert await admin_handlers.handle_admin_text(update, context)
    stored = isolated_env.anon_message(row["id"])
    assert stored["reply_body"] == "بله، با پشتیبانی تماس بگیرید."
    delivered = [m for m in context.bot.messages if m["chat_id"] == USER_ID]
    assert any("پاسخ مدیریت" in m["text"] for m in delivered)


async def test_admin_reply_by_replying_to_the_notification(isolated_env, context):
    register(isolated_env, ADMIN_ID)
    register(isolated_env, USER_ID)
    message_id = isolated_env.add_anon_message("A7F3", USER_ID, "سوال تستی")

    update, message = text_update("پاسخ من", user_id=ADMIN_ID)
    from tests.fakes import FakeMessage

    message.reply_to_message = FakeMessage(
        text=anon_handlers.notification_text("A7F3", "سوال تستی")
    )
    assert await anon_handlers.on_admin_reply_shortcut(update, context)
    assert isolated_env.anon_message(message_id)["reply_body"] == "پاسخ من"


async def test_logs_and_catalog_sections_render(isolated_env, context):
    register(isolated_env, ADMIN_ID)
    for callback in (C.admin(C.ADM_LOGS), C.admin(C.ADM_CATALOG), C.admin(C.ADM_DB),
                     C.admin(C.ADM_CONTENT), C.admin(C.ADM_HOME)):
        update, query = callback_update(callback, user_id=ADMIN_ID)
        await admin_handlers.on_admin_callback(update, context)
        assert query.edits, callback
