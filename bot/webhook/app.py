"""Webhook runtime for cPanel / Passenger (and any other WSGI host).

Every item here is a scar from a real deployment:

1. ``.env`` is loaded by :mod:`bot.config.settings` with ``override=False`` so
   real cPanel environment variables win.
2. The ``X-Telegram-Bot-Api-Secret-Token`` header is verified on **every**
   request (constant-time compare).
3. ``allowed_updates`` must contain ``callback_query`` — see
   ``scripts/set_webhook.py`` (without it the buttons are dead on arrival).
4. Self-starting runtime: the first HTTP request boots the Application in a
   background thread with its own event loop.  ``_owner_pid`` makes it
   fork-safe, because Passenger forks workers after import.
5. Updates are always built with ``Update.de_json(payload, app.bot)`` — never
   with ``None``, otherwise ``query.edit_message_text`` raises RuntimeError and
   the bot goes silent.
6. ``Application.start()`` is called after ``initialize()`` (both are required).
7. ``/healthz`` answers ``ready (vX.Y.Z)`` / ``starting (Ns)`` / ``init-failed``
   and logs the precise reason. ``SystemExit`` is caught as well — otherwise a
   dying worker leaves the bot "starting" forever.
8. ``initialize()`` has a 60s timeout with an explicit log line.
9. A Telegram POST waits up to ~20s for the boot instead of a instant 503.
10. ``TELEGRAM_API_ROOT`` lets you point the bot at a relay/mirror.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import threading
import time
import traceback
from typing import Any, Callable, Iterable

from bot import __version__
from bot.config.settings import Settings
from bot.config.settings import settings as default_settings
from bot.utils.logging import redact, setup_logging

logger = logging.getLogger("bot.webhook")

STATE_IDLE = "idle"
STATE_STARTING = "starting"
STATE_READY = "ready"
STATE_FAILED = "init-failed"

#: how long a Telegram POST may wait for the application to finish booting
POST_BOOT_WAIT = 20.0


class BotRuntime:
    """Boots the PTB Application in a background event loop, once per process."""

    def __init__(self, cfg: Settings | None = None) -> None:
        self.settings = cfg or default_settings
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._application: Any = None
        self._thread: threading.Thread | None = None
        self._state = STATE_IDLE
        self._error: str | None = None
        self._started_at: float = 0.0
        self._ready_event = threading.Event()
        self._owner_pid: int | None = None

    # ------------------------------------------------------------------
    @property
    def state(self) -> str:
        return self._state

    @property
    def application(self) -> Any:
        return self._application

    def status(self) -> dict[str, Any]:
        elapsed = time.time() - self._started_at if self._started_at else 0.0
        if self._state == STATE_READY:
            label = f"ready (v{__version__})"
        elif self._state == STATE_STARTING:
            label = f"starting ({elapsed:.0f}s)"
        elif self._state == STATE_FAILED:
            label = STATE_FAILED
        else:
            label = STATE_IDLE
        return {
            "status": label,
            "state": self._state,
            "version": __version__,
            "pid": os.getpid(),
            "owner_pid": self._owner_pid,
            "uptime_s": round(elapsed, 1),
            "error": self._error,
            "api_root": self.settings.api_root,
        }

    # ------------------------------------------------------------------
    def ensure_started(self) -> None:
        """Start (or restart after a fork) the background runtime."""
        with self._lock:
            if self._owner_pid is not None and self._owner_pid != os.getpid():
                # Passenger forked this worker: the inherited loop is useless.
                logger.warning(
                    "process forked (owner=%s, now=%s) — rebooting runtime",
                    self._owner_pid,
                    os.getpid(),
                )
                self._reset()
            if self._state in (STATE_STARTING, STATE_READY):
                return
            if self._state == STATE_FAILED and self._thread and self._thread.is_alive():
                return

            self._state = STATE_STARTING
            self._error = None
            self._started_at = time.time()
            self._ready_event.clear()
            self._owner_pid = os.getpid()
            self._thread = threading.Thread(
                target=self._run, name="bot-runtime", daemon=True
            )
            self._thread.start()
            logger.info("runtime thread started (pid=%s)", os.getpid())

    def _reset(self) -> None:
        self._loop = None
        self._application = None
        self._thread = None
        self._state = STATE_IDLE
        self._ready_event.clear()

    def _run(self) -> None:  # pragma: no cover - exercised in real deployments
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            from bot.app import build_application

            application = build_application(self.settings)
            loop.run_until_complete(
                asyncio.wait_for(application.initialize(), timeout=self.settings.boot_timeout)
            )
            loop.run_until_complete(application.start())  # required next to initialize()
            self._application = application
            self._state = STATE_READY
            self._ready_event.set()
            logger.info("runtime ready in %.1fs", time.time() - self._started_at)
            loop.run_forever()
        except asyncio.TimeoutError:
            self._fail(
                f"initialize() بیش از {self.settings.boot_timeout} ثانیه طول کشید "
                "(شبکه‌ی هاست به api.telegram.org نمی‌رسد؟)"
            )
        except SystemExit as exc:  # a dying worker must not look like "starting"
            self._fail(f"SystemExit: {exc}")
        except BaseException as exc:  # noqa: BLE001 - we must report everything
            self._fail(f"{type(exc).__name__}: {exc}")
        finally:
            self._ready_event.set()

    def _fail(self, reason: str) -> None:
        self._state = STATE_FAILED
        self._error = redact(reason)
        logger.critical("runtime init failed: %s", self._error)
        logger.critical("traceback:\n%s", redact(traceback.format_exc()))

    # ------------------------------------------------------------------
    def wait_ready(self, timeout: float) -> bool:
        self.ensure_started()
        self._ready_event.wait(timeout)
        return self._state == STATE_READY

    def submit(self, payload: dict[str, Any]) -> bool:
        """Queue one update on the runtime loop."""
        if self._state != STATE_READY or self._loop is None or self._application is None:
            return False
        from telegram import Update

        # Update.de_json(payload, bot) — never None, or button shortcuts break.
        update = Update.de_json(payload, self._application.bot)
        asyncio.run_coroutine_threadsafe(
            self._application.process_update(update), self._loop
        )
        return True


runtime = BotRuntime()


# ---------------------------------------------------------------------------
# WSGI
# ---------------------------------------------------------------------------
def _respond(
    start_response: Callable[..., Any],
    status: str,
    body: str | bytes,
    content_type: str = "application/json; charset=utf-8",
) -> Iterable[bytes]:
    payload = body.encode("utf-8") if isinstance(body, str) else body
    start_response(
        status,
        [
            ("Content-Type", content_type),
            ("Content-Length", str(len(payload))),
            ("Cache-Control", "no-store"),
        ],
    )
    return [payload]


def create_app(cfg: Settings | None = None) -> Callable[..., Iterable[bytes]]:
    cfg = cfg or default_settings
    cfg.ensure_dirs()
    setup_logging(cfg.log_level, cfg.log_path)
    runtime.settings = cfg

    webhook_path = cfg.webhook_path or "/telegram/webhook"

    def wsgi_app(environ: dict[str, Any], start_response: Callable[..., Any]):
        path = environ.get("PATH_INFO", "") or "/"
        method = environ.get("REQUEST_METHOD", "GET").upper()

        # ---- health check -------------------------------------------------
        if path.rstrip("/").endswith("/healthz") or path == "/healthz":
            runtime.ensure_started()
            return _respond(start_response, "200 OK",
                            json.dumps(runtime.status(), ensure_ascii=False))

        # ---- webhook ------------------------------------------------------
        if path.rstrip("/") == webhook_path.rstrip("/"):
            if method != "POST":
                return _respond(start_response, "405 Method Not Allowed",
                                '{"error":"method not allowed"}')

            provided = environ.get("HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN", "")
            if cfg.webhook_secret:
                if not provided or not hmac.compare_digest(provided, cfg.webhook_secret):
                    logger.warning("rejected webhook request: bad secret token")
                    return _respond(start_response, "403 Forbidden", '{"error":"forbidden"}')
            else:
                logger.warning("WEBHOOK_SECRET is empty — anyone can POST updates!")

            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
            except ValueError:
                length = 0
            raw = environ["wsgi.input"].read(length) if length else b""
            try:
                payload = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                logger.warning("invalid webhook payload: %s", exc)
                return _respond(start_response, "400 Bad Request", '{"error":"bad json"}')

            # give a cold Passenger worker time to boot instead of 503-ing
            if not runtime.wait_ready(POST_BOOT_WAIT):
                status = runtime.status()
                logger.error("update dropped, runtime not ready: %s", status)
                return _respond(start_response, "503 Service Unavailable",
                                json.dumps(status, ensure_ascii=False))

            if not runtime.submit(payload):
                return _respond(start_response, "503 Service Unavailable",
                                '{"error":"runtime not ready"}')
            return _respond(start_response, "200 OK", '{"ok":true}')

        # ---- anything else -------------------------------------------------
        return _respond(start_response, "404 Not Found", '{"error":"not found"}')

    return wsgi_app


application = create_app()
