#!/usr/bin/env python3
"""Terminal walkthrough of every screen the bot can show (no network, no token).

    python scripts/demo.py             # all pages
    python scripts/demo.py --page cat:c:11:r:1
    python scripts/demo.py --admin     # include the admin panel with sample data
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.services import admin_view  # noqa: E402
from bot.services.catalog import get_catalog  # noqa: E402
from bot.services.navigation import Page, iter_all_pages, render  # noqa: E402

TAG_RE = re.compile(r"<[^>]+>")


def plain(text: str) -> str:
    return html.unescape(TAG_RE.sub("", text))


def show(page: Page) -> None:
    print("\n" + "=" * 72)
    print(f"[{page.id}]  ← parent: {page.parent or '—'}")
    print("-" * 72)
    print(plain(page.text))
    print("-" * 72)
    for row in page.rows:
        cells = []
        for button in row:
            mark = {"primary": "🔵", "success": "🟢", "danger": "🔴"}.get(button.style, "⚪️")
            target = button.url or button.callback
            cells.append(f"{mark} {button.text} → {target}")
        print("   " + " | ".join(cells))


SAMPLE_STATS = {
    "users": {"total": 128, "with_phone": 121, "today": 7},
    "events": {"total": 2310, "today": 143, "active_today": 22},
    "top_all": [("nav:main", 410), ("cat:c", 265), ("cat:c:12:t:1", 180)],
    "top_today": [("nav:main", 41), ("cat:n", 18)],
    "anon_total": 12,
    "anon_unread": 3,
    "db_size": 81920,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", help="render a single callback")
    parser.add_argument("--admin", action="store_true", help="include admin screens")
    args = parser.parse_args()

    snapshot = get_catalog().get()
    print(f"کاتالوگ: منبع={snapshot.source} | تعداد={len(snapshot.items)} | {snapshot.counts()}")

    if args.page:
        show(render(args.page, snapshot))
        return 0

    count = 0
    for page in iter_all_pages(snapshot):
        show(page)
        count += 1

    if args.admin:
        for page in (
            admin_view.home(SAMPLE_STATS),
            admin_view.stats(SAMPLE_STATS),
            admin_view.stats_reset_confirm(),
            admin_view.users([], {"total": 0, "with_phone": 0, "today": 0}, 1, 1),
            admin_view.logs(["2026-10-02 10:00:00 | INFO | bot | ready"], "data/bot.log", 1024),
            admin_view.database({"path": "data/bot.db", "size": 81920, "users": 128,
                                 "events": 2310}),
            admin_view.content_list({}),
            admin_view.anon_list([], 1, 1, 0, 0),
            admin_view.catalog_status({"source": snapshot.source, "counts": snapshot.counts(),
                                       "configured": False, "fetched_at_label": "—"}),
        ):
            show(page)
            count += 1

    print(f"\n✅ {count} صفحه رندر شد.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
