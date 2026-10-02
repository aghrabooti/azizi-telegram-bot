"""The phone gate — the part that must never regress (v1.4.1)."""

from __future__ import annotations

import pytest
from telegram.ext import ApplicationHandlerStop

from bot.handlers import phone_gate
from bot.utils.phone import mask_phone, normalize_phone
from tests.fakes import callback_update, contact_update, text_update


# --------------------------------------------------------------------- unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+989121234567", "+989121234567"),   # Telegram's Iranian format — as is
        ("+4915112345678", "+4915112345678"),  # German user abroad
        ("+971501234567", "+971501234567"),    # UAE
        ("09121234567", "+989121234567"),      # local mobile
        ("9121234567", "+989121234567"),
        ("989121234567", "+989121234567"),
        ("00989121234567", "+989121234567"),
        ("۰۹۱۲۱۲۳۴۵۶۷", "+989121234567"),       # Persian digits
        ("٠٩١٢١٢٣٤٥٦٧", "+989121234567"),       # Arabic digits
        ("0912 123 4567", "+989121234567"),
        ("(0912) 123-4567", "+989121234567"),
        ("+98 912 123 4567", "+989121234567"),
    ],
)
def test_valid_numbers(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", None, "02188776655", "88776655", "سلام", "12345", "+1234", "+" + "9" * 20],
)
def test_invalid_numbers(raw):
    assert normalize_phone(raw) is None


def test_mask_phone():
    assert mask_phone("+989121234567").startswith("+9891")
    assert mask_phone("+989121234567").endswith("567")
    assert "1234" not in mask_phone("+989121234567")


# ----------------------------------------------------------------- the gate
async def test_contact_is_accepted_and_opens_menu(isolated_env, context):
    update, message = contact_update("+989121234567", user_id=501)
    with pytest.raises(ApplicationHandlerStop):
        await phone_gate.handle_contact(update, context)

    assert isolated_env.has_phone(501)
    assert isolated_env.get_user(501)["phone"] == "+989121234567"
    assert any("ثبت شد" in reply["text"] for reply in message.replies)
    assert any("منوی اصلی" in text or "آکادمی" in text for text in context.bot.texts)


async def test_foreign_contact_is_rejected(isolated_env, context):
    update, message = contact_update("+989121234567", user_id=502, owner=777)
    with pytest.raises(ApplicationHandlerStop):
        await phone_gate.handle_contact(update, context)
    assert not isolated_env.has_phone(502)
    assert "متعلق به حساب شما نیست" in message.replies[0]["text"]


async def test_layer_a_invalid_text_shows_no_menu(isolated_env, context):
    update, _ = text_update("شماره‌ام رو نمیدم", user_id=503)
    with pytest.raises(ApplicationHandlerStop):
        await phone_gate.gate_message(update, context)

    assert not isolated_env.has_phone(503)
    assert len(context.bot.messages) == 1
    body = context.bot.texts[0]
    assert "شماره‌ی معتبری دریافت نشد" in body
    assert "از منوی زیر انتخاب کنید" not in body  # the menu must NOT appear


async def test_layer_b_old_button_cannot_bypass_the_gate(isolated_env, context):
    update, query = callback_update("cat:c:12:t:1", user_id=504)
    with pytest.raises(ApplicationHandlerStop):
        await phone_gate.gate_callback(update, context)

    assert query.answers and query.answers[0]["alert"] is True
    assert not query.edits  # no page was rendered
    assert context.bot.messages  # but the contact request was re-sent


async def test_layer_c_non_text_message_asks_again(isolated_env, context):
    update, _ = text_update("placeholder", user_id=505)
    update.effective_message.text = None  # e.g. a sticker
    with pytest.raises(ApplicationHandlerStop):
        await phone_gate.gate_message(update, context)
    assert "شماره‌ی موبایلتان ثبت شود" in context.bot.texts[0]


async def test_typed_international_number_is_accepted(isolated_env, context):
    update, _ = text_update("+4915112345678", user_id=506)
    with pytest.raises(ApplicationHandlerStop):
        await phone_gate.gate_message(update, context)
    assert isolated_env.get_user(506)["phone"] == "+4915112345678"


async def test_gate_lets_registered_users_through(isolated_env, context):
    isolated_env.upsert_user(507)
    isolated_env.set_phone(507, "+989121234567")
    update, _ = text_update("سلام", user_id=507)
    await phone_gate.gate_message(update, context)  # must NOT raise
