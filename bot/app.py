"""Application factory shared by polling (bot/main.py) and webhook (WSGI)."""

from __future__ import annotations

import logging

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, Defaults

from bot import __version__
from bot.config.settings import Settings
from bot.config.settings import settings as default_settings
from bot.handlers import register_handlers
from bot.services.content_store import get_store
from bot.services.database import get_db
from bot.utils.logging import setup_logging

logger = logging.getLogger(__name__)

#: callback_query MUST be in this list, otherwise buttons are silently dead.
ALLOWED_UPDATES: list[str] = [
    Update.MESSAGE,
    Update.EDITED_MESSAGE,
    Update.CALLBACK_QUERY,
    Update.MY_CHAT_MEMBER,
]

COMMANDS = [
    BotCommand("start", "شروع و منوی اصلی"),
    BotCommand("menu", "نمایش منوی اصلی"),
    BotCommand("help", "راهنما"),
    BotCommand("id", "نمایش آیدی عددی من"),
]


async def _post_init(application: Application) -> None:
    try:
        await application.bot.set_my_commands(COMMANDS)
    except Exception as exc:  # noqa: BLE001 - never block startup on cosmetics
        logger.warning("set_my_commands failed: %s", exc)
    me = await application.bot.get_me()
    logger.info("bot @%s (id=%s) is up — v%s", me.username, me.id, __version__)


def build_application(cfg: Settings | None = None) -> Application:
    cfg = cfg or default_settings
    cfg.ensure_dirs()
    setup_logging(cfg.log_level, cfg.log_path)

    problems = cfg.validate()
    for problem in problems:
        logger.error("config: %s", problem)
    if not cfg.bot_token:
        raise RuntimeError("BOT_TOKEN تنظیم نشده است — فایل .env را بررسی کنید.")

    # database + live content overrides
    db = get_db(cfg.db_path)
    get_store(db)
    logger.info("database ready at %s", db.path)
    if cfg.api_root != "https://api.telegram.org":
        logger.info("using custom Telegram API root: %s", cfg.api_root)

    builder: ApplicationBuilder = (
        Application.builder()
        .token(cfg.bot_token)
        .base_url(cfg.base_url)
        .base_file_url(cfg.base_file_url)
        .defaults(Defaults(parse_mode=ParseMode.HTML, block=False))
        .concurrent_updates(True)
        .post_init(_post_init)
    )
    # Optional extra: pip install "python-telegram-bot[rate-limiter]".
    # Without it the bot works fine, it just has no automatic flood control.
    try:
        from telegram.ext import AIORateLimiter

        builder = builder.rate_limiter(AIORateLimiter())
    except (ImportError, RuntimeError) as exc:
        logger.info("rate limiter not enabled (%s)", exc)
    application = builder.build()
    register_handlers(application)
    return application
