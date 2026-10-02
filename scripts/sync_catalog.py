#!/usr/bin/env python3
"""Refresh the local catalog snapshot.

    python scripts/sync_catalog.py                 # from Supabase (live)
    python scripts/sync_catalog.py --from-site     # from the website JSON-LD
    python scripts/sync_catalog.py --write-seed    # also update the bundled seed

The bot normally reads Supabase directly; this script only refreshes the
offline fallback (``data/catalog_cache.json`` / ``bot/config/catalog_seed.json``)
so the shop is never empty when the host loses connectivity.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config.settings import settings  # noqa: E402
from bot.services.catalog import (  # noqa: E402
    SEED_PATH,
    CatalogService,
    Product,
    parse_field,
    parse_grade,
)

JSONLD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I
)


def from_site() -> list[Product]:
    """Scrape the public JSON-LD of /courses (no API key required).

    Note: JSON-LD does not expose the product *type*, so it is inferred from
    the title (کتاب… → book, جزوه… → note).  Use Supabase for authoritative data.
    """
    url = f"{settings.site_base_url}/courses"
    request = urllib.request.Request(url, headers={"User-Agent": "azizi-telegram-bot/sync"})
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    products: list[Product] = []
    for block in JSONLD_RE.findall(html):
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue
        graph = payload.get("@graph") if isinstance(payload, dict) else None
        if not graph:
            continue
        for node in graph:
            if node.get("@type") != "Course":
                continue
            title = node.get("name", "")
            offers = node.get("offers") or {}
            identifier = ""
            link = node.get("url") or offers.get("url") or ""
            if "id=" in link:
                identifier = link.split("id=", 1)[1]
            kind = "course"
            if title.startswith("کتاب"):
                kind = "book"
            elif title.startswith("جزوه"):
                kind = "note"
            products.append(
                Product(
                    id=identifier or title,
                    type=kind,
                    title=title,
                    description=node.get("description", ""),
                    price=int(offers.get("price") or 0) or None,
                    grade=parse_grade(node.get("educationalLevel")),
                    field=parse_field(node.get("about")),
                    url=link,
                    image=node.get("image", "") or "",
                )
            )
    return products


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-site", action="store_true", help="scrape the website JSON-LD")
    parser.add_argument("--write-seed", action="store_true", help="update the bundled seed file")
    args = parser.parse_args()

    if args.from_site:
        items = from_site()
        source = "site-jsonld"
    else:
        if not settings.supabase_configured:
            print("❌ SUPABASE_URL/SUPABASE_ANON_KEY تنظیم نشده — "
                  "یا کلید را در .env بگذارید یا با --from-site اجرا کنید.")
            return 2
        service = CatalogService(settings)
        snapshot = service.get(force=True)
        items = snapshot.items
        source = snapshot.source
        if snapshot.source != "live":
            print(f"⚠️ دریافت زنده ناموفق بود ({snapshot.error}) — منبع: {snapshot.source}")

    if not items:
        print("❌ هیچ آیتمی دریافت نشد.")
        return 1

    counts: dict[str, int] = {}
    for item in items:
        counts[item.type] = counts.get(item.type, 0) + 1
    print(f"✅ {len(items)} آیتم از منبع «{source}» — {counts}")

    settings.ensure_dirs()
    payload = {
        "generated_at": dt.date.today().isoformat(),
        "source": source,
        "items": [item.to_dict() for item in items],
    }
    cache_path = settings.catalog_cache_path
    cache_path.write_text(json.dumps({"fetched_at": 0, **payload}, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    print(f"📝 {cache_path}")

    if args.write_seed:
        SEED_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"📝 {SEED_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
