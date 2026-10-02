#!/usr/bin/env python3
"""Build the data file for the live preview site **from the real source**.

This script imports the actual bot modules and renders every page with the
real renderers — there is no hand-written copy of the menus anywhere.  It then
asserts that *every* callback produced by *any* page resolves to a page or to a
known action; a dead button fails the build instead of reaching production.

    python dev/preview/build.py          # writes dev/preview/static/app-data.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bot import __version__  # noqa: E402
from bot import constants as C  # noqa: E402
from bot.config import content  # noqa: E402
from bot.keyboards.builder import SUPPORTS_BUTTON_STYLES  # noqa: E402
from bot.services import admin_view  # noqa: E402
from bot.services.catalog import get_catalog  # noqa: E402
from bot.services.navigation import Page, iter_all_pages, render_static  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"
OUT_FILE = STATIC_DIR / "app-data.json"

SOURCE_GLOBS = ("bot/**/*.py", "bot/config/*.json", "scripts/*", "dev/preview/*",
                "dev/preview/static/*", "tests/*.py", "deploy/*", "*.py", "*.txt",
                "*.toml", "*.md", "*.example", ".gitignore")
SOURCE_EXCLUDE_PARTS = {".git", ".venv", "__pycache__", "data", "dist", ".pytest_cache",
                        ".ruff_cache"}

# ---------------------------------------------------------------------------
# sample data for the admin panel preview
# ---------------------------------------------------------------------------
SAMPLE_STATS = {
    "users": {"total": 128, "with_phone": 121, "today": 7},
    "events": {"total": 2310, "today": 143, "active_today": 22},
    "top_all": [("nav:main", 410), ("cat:c", 265), ("cat:c:12:t:1", 180), ("nav:social", 96)],
    "top_today": [("nav:main", 41), ("cat:n", 18), ("anon:new", 9)],
    "anon_total": 12,
    "anon_unread": 3,
    "db_size": 81920,
}

SAMPLE_USERS = [
    {"user_id": 1105550101, "username": "sara_m", "first_name": "سارا", "last_name": "محمدی",
     "phone": "+989121234567", "created_at": "2026-09-28 10:11:00"},
    {"user_id": 1105550102, "username": None, "first_name": "آرمان", "last_name": "",
     "phone": "+989351112233", "created_at": "2026-09-29 18:02:00"},
    {"user_id": 1105550103, "username": "parsa", "first_name": "پارسا", "last_name": "رضایی",
     "phone": "+4915112345678", "created_at": "2026-10-01 08:45:00"},
]

SAMPLE_ANON = [
    {"id": 12, "code": "A7F3", "body": "سلام، پکیج حسابان ۲ شامل جزوه چاپی هم میشه؟",
     "created_at": "2026-10-02 09:12:00", "is_read": 0, "reply_body": None},
    {"id": 11, "code": "K9QD", "body": "برای پایه نهم تخفیف دانش‌آموزی دارید؟",
     "created_at": "2026-10-01 20:40:00", "is_read": 1,
     "reply_body": "بله، با پشتیبانی تماس بگیرید.", "replied_at": "2026-10-01 21:05:00"},
]

SAMPLE_LOG = [
    "2026-10-02 09:00:01 | INFO     | bot.main | starting azizi-telegram-bot v1.0.0 (pid=20714)",
    "2026-10-02 09:00:02 | INFO     | bot.app  | database ready at data/bot.db",
    "2026-10-02 09:00:04 | INFO     | bot.app  | bot @azizi_math_bot (id=800123) is up — v1.0.0",
    "2026-10-02 09:12:33 | INFO     | bot.handlers.phone_gate | phone stored for user"
    " 110555 (+9891*****567)",
]


def admin_pages(snapshot) -> dict[str, Page]:
    pages = {
        C.admin(C.ADM_HOME): admin_view.home(SAMPLE_STATS),
        C.admin(C.ADM_STATS): admin_view.stats(SAMPLE_STATS),
        C.admin(C.ADM_STATS, "reset"): admin_view.stats_reset_confirm(),
        C.admin(C.ADM_USERS): admin_view.users(
            SAMPLE_USERS, SAMPLE_STATS["users"], 1, 1
        ),
        C.admin(C.ADM_LOGS): admin_view.logs(SAMPLE_LOG, "data/bot.log", 48127),
        C.admin(C.ADM_DB): admin_view.database(
            {"path": "data/bot.db", "size": 81920, "users": 128, "events": 2310}
        ),
        C.admin(C.ADM_CONTENT): admin_view.content_list({"main.text": "..."}),
        C.admin(C.ADM_ANON): admin_view.anon_list(SAMPLE_ANON, 1, 1, 12, 3),
        C.admin(C.ADM_CATALOG): admin_view.catalog_status(
            {
                "source": snapshot.source,
                "fetched_at_label": "—",
                "counts": snapshot.counts(),
                "configured": False,
                "error": snapshot.error,
            }
        ),
    }
    for index, (key, label) in enumerate(content.EDITABLE_KEYS):
        pages[C.admin(C.ADM_CONTENT, "edit", index)] = admin_view.content_edit(
            index, key, label, content.default_text(key), index == 0
        )
    for row in SAMPLE_ANON:
        pages[C.admin(C.ADM_ANON, "view", row["id"])] = admin_view.anon_detail(row)
    return pages


def actions() -> dict[str, dict[str, str]]:
    """Callbacks that do something instead of showing a page."""
    out = {
        "noop": {"toast": "—"},
        C.admin(C.ADM_USERS, "csv"): {
            "toast": "📥 فایل users-20261002-0930.csv (CSV با BOM) ارسال شد",
            "goto": C.admin(C.ADM_USERS),
        },
        C.admin(C.ADM_LOGS, "file"): {
            "toast": "⬇️ فایل bot.log (48 KB) ارسال شد", "goto": C.admin(C.ADM_LOGS)
        },
        C.admin(C.ADM_DB, "backup"): {
            "toast": "💾 پشتیبان bot-20261002-093012.db ارسال شد", "goto": C.admin(C.ADM_DB)
        },
        C.admin(C.ADM_DB, "restore"): {
            "toast": "♻️ منتظر دریافت فایل .db …", "goto": C.admin(C.ADM_DB)
        },
        C.admin(C.ADM_STATS, "reset", "yes"): {
            "toast": "🗑 ۲۳۱۰ رویداد پاک شد", "goto": C.admin(C.ADM_STATS)
        },
        C.admin(C.ADM_CATALOG, "refresh"): {
            "toast": "🔄 کاتالوگ دوباره دریافت شد", "goto": C.admin(C.ADM_CATALOG)
        },
    }
    for index in range(len(content.EDITABLE_KEYS)):
        out[C.admin(C.ADM_CONTENT, "reset", index)] = {
            "toast": "↩️ متن به پیش‌فرض برگشت", "goto": C.admin(C.ADM_CONTENT)
        }
    for row in SAMPLE_ANON:
        out[C.admin(C.ADM_ANON, "reply", row["id"])] = {
            "toast": f"✍️ حالت پاسخ به #{row['code']} فعال شد (متن را بنویسید)",
            "goto": C.admin(C.ADM_ANON, "view", row["id"]),
        }
    return out


def collect_sources() -> list[dict[str, object]]:
    seen: dict[str, dict[str, object]] = {}
    for pattern in SOURCE_GLOBS:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if set(relative.parts) & SOURCE_EXCLUDE_PARTS:
                continue
            if path.name == ".env" or path.suffix in {".pyc", ".zip", ".db", ".log"}:
                continue
            if path.name == "app-data.json":
                continue
            seen[str(relative)] = {"path": str(relative), "size": path.stat().st_size}
    return sorted(seen.values(), key=lambda item: item["path"])


def main() -> int:
    snapshot = get_catalog().get()
    pages: dict[str, Page] = {page.id: page for page in iter_all_pages(snapshot)}
    pages.setdefault(C.nav(C.PAGE_MAIN), render_static(C.PAGE_MAIN))
    admin = admin_pages(snapshot)
    known_actions = actions()

    # ---- assertion: no button may point at a missing page -----------------
    known = set(pages) | set(admin) | set(known_actions)
    missing: list[tuple[str, str]] = []
    for page in list(pages.values()) + list(admin.values()):
        for callback in page.callbacks():
            if callback not in known:
                missing.append((page.id, callback))
    if missing:
        for page_id, callback in missing:
            print(f"❌ dead button: {page_id} → {callback}", file=sys.stderr)
        raise SystemExit(f"preview build failed: {len(missing)} callback(s) without a page")

    payload = {
        "version": __version__,
        "build_id": datetime.now().strftime("%Y%m%d-%H%M%S"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "supports_button_styles": SUPPORTS_BUTTON_STYLES,
        "catalog": {
            "source": snapshot.source,
            "counts": snapshot.counts(),
            "total": len(snapshot.items),
            "error": snapshot.error,
        },
        "start": C.nav(C.PAGE_MAIN),
        "admin_start": C.admin(C.ADM_HOME),
        "pages": {page_id: page.to_dict() for page_id, page in pages.items()},
        "admin_pages": {page_id: page.to_dict() for page_id, page in admin.items()},
        "actions": known_actions,
        "phone": {
            "request": content.text("phone.request", name="دانش‌آموز"),
            "button": content.text("phone.button"),
            "invalid": content.text("phone.invalid"),
            "not_text": content.text("phone.not_text"),
            "saved": content.text("phone.saved", phone="+989121234567"),
            "gate_callback": content.text("phone.gate_callback"),
        },
        "anon": {
            "intro": content.text("anon.intro"),
            "sent": content.text("anon.sent", code="#A7F3"),
            "too_short": content.text("anon.too_short"),
        },
        "texts": {
            "expired": content.text("error.expired"),
        },
        "sources": collect_sources(),
    }

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"✅ {OUT_FILE.relative_to(ROOT)} — {len(pages)} user pages, "
        f"{len(admin)} admin pages, {len(known_actions)} actions, "
        f"{len(payload['sources'])} source files, catalog={snapshot.source}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
