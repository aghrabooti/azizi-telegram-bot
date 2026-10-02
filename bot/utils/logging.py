"""Logging: console + rotating file, with the bot token scrubbed everywhere."""

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_TOKEN_RE = re.compile(r"bot\d{5,}:[A-Za-z0-9_-]{20,}")
_BARE_TOKEN_RE = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{30,}\b")
REDACTED = "bot***:***REDACTED***"


class TokenRedactingFilter(logging.Filter):
    """Never let a token reach a log file that might be shared with others."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover
            return True
        redacted = _BARE_TOKEN_RE.sub("***REDACTED***", _TOKEN_RE.sub(REDACTED, message))
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


_CONFIGURED = False


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> logging.Logger:
    """Configure root logging once; safe to call from polling, WSGI and tests."""
    global _CONFIGURED
    root = logging.getLogger()
    if _CONFIGURED:
        return logging.getLogger("bot")

    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    redactor = TokenRedactingFilter()

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(redactor)
    root.addHandler(console)

    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            file_handler.addFilter(redactor)
            root.addHandler(file_handler)
        except OSError as exc:  # pragma: no cover - read-only disk
            root.warning("cannot open log file %s: %s", log_file, exc)

    # third-party noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    _CONFIGURED = True
    return logging.getLogger("bot")


def redact(text: str) -> str:
    return _BARE_TOKEN_RE.sub("***REDACTED***", _TOKEN_RE.sub(REDACTED, text))
