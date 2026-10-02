"""Handler registration.

Group ordering is part of the security model:

* group **-1**: contact + phone gate.  Runs before everything else so a user
  without a phone number cannot reach any page, not even with an old button.
* group  **0**: commands and inline navigation.
* group  **1**: free text / documents (anonymous messages, admin flows).
"""

from __future__ import annotations

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot import constants as C
from bot.handlers import admin, navigation, phone_gate, router, start
from bot.handlers.anonymous import on_anon_entry
from bot.handlers.errors import on_error


def register_handlers(application: Application) -> None:
    # ---- group -1: the phone gate -------------------------------------
    application.add_handler(
        MessageHandler(filters.CONTACT, phone_gate.handle_contact), group=-1
    )
    application.add_handler(
        MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, phone_gate.gate_message),
        group=-1,
    )
    application.add_handler(CallbackQueryHandler(phone_gate.gate_callback), group=-1)

    # ---- group 0: commands & navigation --------------------------------
    application.add_handler(CommandHandler("start", start.cmd_start))
    application.add_handler(CommandHandler("menu", start.cmd_menu))
    application.add_handler(CommandHandler("help", start.cmd_help))
    application.add_handler(CommandHandler("id", start.cmd_id))
    application.add_handler(CommandHandler("admin", admin.cmd_admin))
    application.add_handler(CommandHandler("cancel", admin.cmd_cancel))

    application.add_handler(CallbackQueryHandler(navigation.on_nav, pattern=C.PATTERN_NAV))
    application.add_handler(CallbackQueryHandler(navigation.on_catalog, pattern=C.PATTERN_CAT))
    application.add_handler(CallbackQueryHandler(on_anon_entry, pattern=C.PATTERN_ANON))
    application.add_handler(CallbackQueryHandler(admin.on_admin_callback, pattern=C.PATTERN_ADM))
    application.add_handler(CallbackQueryHandler(navigation.on_noop, pattern=C.PATTERN_NOOP))
    # anything else = a button from an older build
    application.add_handler(CallbackQueryHandler(navigation.on_unknown_callback))

    # ---- group 1: free text --------------------------------------------
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, router.on_text), group=1
    )
    application.add_handler(MessageHandler(filters.Document.ALL, router.on_document), group=1)
    application.add_handler(
        MessageHandler(
            ~filters.TEXT & ~filters.COMMAND & ~filters.Document.ALL & ~filters.StatusUpdate.ALL,
            router.on_other,
        ),
        group=1,
    )

    application.add_error_handler(on_error)


__all__ = ["register_handlers"]
