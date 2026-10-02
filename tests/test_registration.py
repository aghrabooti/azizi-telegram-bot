"""Handler registration: the group order IS the security model."""

from __future__ import annotations

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
)

from bot.handlers import register_handlers


def build() -> object:
    application = ApplicationBuilder().token("123456:TEST-TOKEN-FOR-UNIT-TESTS").build()
    register_handlers(application)
    return application


def test_phone_gate_runs_before_everything_else():
    application = build()
    groups = sorted(application.handlers)
    assert groups[0] == -1, "the phone gate must be registered in group -1"

    gate = application.handlers[-1]
    assert any(isinstance(handler, CallbackQueryHandler) for handler in gate)
    assert sum(isinstance(handler, MessageHandler) for handler in gate) >= 2


def test_commands_are_registered():
    application = build()
    commands = {
        tuple(handler.commands)[0]
        for handler in application.handlers[0]
        if isinstance(handler, CommandHandler)
    }
    assert {"start", "menu", "help", "admin", "id", "cancel"} <= commands


def test_every_callback_pattern_has_a_handler():
    application = build()
    handlers = [
        handler
        for handler in application.handlers[0]
        if isinstance(handler, CallbackQueryHandler)
    ]
    samples = [
        "nav:main",
        "nav:about",
        "cat:c",
        "cat:c:11",
        "cat:n:12:t:2",
        "anon:new",
        "adm:home",
        "adm:users:page:2",
        "adm:anon:view:12",
        "noop",
        "totally:unknown:button",  # must fall through to the catch-all handler
    ]
    for data in samples:
        matched = [
            handler
            for handler in handlers
            if handler.pattern is None or handler.pattern.match(data)
        ]
        assert matched, f"no handler matches {data}"


def test_error_handler_is_installed():
    application = build()
    assert application.error_handlers
