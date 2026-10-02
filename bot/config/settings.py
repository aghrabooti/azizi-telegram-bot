"""Environment-driven settings (no texts here — those live in content.py).

Rules learned the hard way:
  * ``.env`` must contain only ``KEY=value`` lines. We therefore parse it
    defensively and *report* bad lines instead of crashing silently.
  * Real cPanel/Passenger environment variables must win over the .env file,
    because that is where the host injects them.
  * Nothing here ever logs the token.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

#: repository root (…/azizi-telegram-bot)
ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"

#: lines of .env that are not KEY=value — surfaced by scripts/diagnose.py
ENV_FILE_PROBLEMS: list[str] = []


def _sanity_check_env_file(path: Path) -> list[str]:
    problems: list[str] = []
    if not path.exists():
        return problems
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:  # pragma: no cover - unreadable file
        return [f"cannot read {path.name}: {exc}"]
    for lineno, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].strip()
        key, sep, _ = stripped.partition("=")
        if not sep or not key.strip() or any(ch in key for ch in " \t"):
            problems.append(f"line {lineno}: not a KEY=value line -> {stripped[:40]!r}")
    return problems


ENV_FILE_PROBLEMS = _sanity_check_env_file(ENV_FILE)
# override=False → variables already exported by cPanel/systemd win.
load_dotenv(ENV_FILE, override=False)


def _str(key: str, default: str = "") -> str:
    value = os.getenv(key)
    return default if value is None else value.strip()


def _int(key: str, default: int) -> int:
    raw = _str(key)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _bool(key: str, default: bool) -> bool:
    raw = _str(key).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _ids(key: str) -> tuple[int, ...]:
    out: list[int] = []
    for chunk in _str(key).replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.append(int(chunk))
        except ValueError:
            continue
    return tuple(out)


@dataclass
class Settings:
    # --- telegram ---
    bot_token: str = field(default_factory=lambda: _str("BOT_TOKEN"))
    api_root: str = field(
        default_factory=lambda: _str("TELEGRAM_API_ROOT", "https://api.telegram.org").rstrip("/")
    )
    admin_ids: tuple[int, ...] = field(default_factory=lambda: _ids("ADMIN_IDS"))

    # --- storage / logging ---
    data_dir: Path = field(default_factory=lambda: (ROOT_DIR / _str("DATA_DIR", "data")))
    log_level: str = field(default_factory=lambda: _str("LOG_LEVEL", "INFO").upper())

    # --- webhook ---
    webhook_secret: str = field(default_factory=lambda: _str("WEBHOOK_SECRET"))
    webhook_url: str = field(default_factory=lambda: _str("WEBHOOK_URL"))
    webhook_path: str = field(default_factory=lambda: _str("WEBHOOK_PATH", "/telegram/webhook"))
    boot_timeout: int = field(default_factory=lambda: _int("BOOT_TIMEOUT", 60))

    # --- website / catalog ---
    site_base_url: str = field(
        default_factory=lambda: _str("SITE_BASE_URL", "https://www.mahdiazizi.com").rstrip("/")
    )
    supabase_url: str = field(default_factory=lambda: _str("SUPABASE_URL").rstrip("/"))
    supabase_anon_key: str = field(default_factory=lambda: _str("SUPABASE_ANON_KEY"))
    table_courses: str = field(default_factory=lambda: _str("SUPABASE_TABLE_COURSES", "courses"))
    table_books: str = field(default_factory=lambda: _str("SUPABASE_TABLE_BOOKS", "books"))
    table_notes: str = field(default_factory=lambda: _str("SUPABASE_TABLE_NOTES", "notes"))
    single_table: str = field(default_factory=lambda: _str("SUPABASE_SINGLE_TABLE"))
    type_column: str = field(default_factory=lambda: _str("SUPABASE_TYPE_COLUMN", "type"))
    catalog_ttl: int = field(default_factory=lambda: _int("CATALOG_TTL", 600))
    catalog_page_size: int = field(default_factory=lambda: _int("CATALOG_PAGE_SIZE", 6))

    # --- anonymous inbox ---
    anon_notify: bool = field(default_factory=lambda: _bool("ANON_NOTIFY", True))
    anon_inbox_chat_id: str = field(default_factory=lambda: _str("ANON_INBOX_CHAT_ID"))

    # --- ui ---
    button_style_mode: str = field(
        default_factory=lambda: _str("BUTTON_STYLE_MODE", "auto").lower() or "auto"
    )

    # ------------------------------------------------------------------
    @property
    def db_path(self) -> Path:
        return self.data_dir / "bot.db"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "bot.log"

    @property
    def catalog_cache_path(self) -> Path:
        return self.data_dir / "catalog_cache.json"

    @property
    def base_url(self) -> str:
        """Telegram Bot API base, honouring TELEGRAM_API_ROOT (relay/mirror)."""
        return f"{self.api_root}/bot"

    @property
    def base_file_url(self) -> str:
        return f"{self.api_root}/file/bot"

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)

    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admin_ids

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        """Return a list of human-readable configuration problems (fa)."""
        problems: list[str] = []
        if not self.bot_token:
            problems.append("BOT_TOKEN تنظیم نشده است.")
        elif ":" not in self.bot_token:
            problems.append("BOT_TOKEN فرمت درستی ندارد (باید شامل ':' باشد).")
        if not self.admin_ids:
            problems.append("ADMIN_IDS خالی است — پنل ادمین در دسترس نخواهد بود.")
        if self.button_style_mode not in {"auto", "native", "off"}:
            problems.append("BUTTON_STYLE_MODE باید auto یا native یا off باشد.")
        for problem in ENV_FILE_PROBLEMS:
            problems.append(f".env خراب است → {problem}")
        return problems


settings = Settings()
