#!/usr/bin/env python3
"""Discover the real Supabase schema instead of guessing it.

    python scripts/probe_supabase.py            # list tables + columns
    python scripts/probe_supabase.py --table courses --rows 3

Needs ``SUPABASE_URL`` and ``SUPABASE_ANON_KEY`` in ``.env`` (the anon key is
the public key your website already ships inside its JavaScript bundle).

Output is a ready-to-paste report: table names, column names, and how the bot
would map them to (title / price / grade / field / type).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config.settings import settings  # noqa: E402
from bot.services.catalog import normalize_row  # noqa: E402


def request(path: str) -> tuple[int, object]:
    url = f"{settings.supabase_url}/rest/v1/{path}"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {settings.supabase_anon_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", help="inspect a single table")
    parser.add_argument("--rows", type=int, default=2, help="sample rows to print")
    args = parser.parse_args()

    if not settings.supabase_configured:
        print("❌ SUPABASE_URL یا SUPABASE_ANON_KEY در .env تنظیم نشده است.")
        print("   کلید anon همان کلید عمومی داخل جاوااسکریپت سایت است "
              "(DevTools → Network → هر درخواست به supabase.co → هدر apikey).")
        return 2

    if not args.table:
        status, spec = request("")
        if status != 200 or not isinstance(spec, dict):
            print(f"❌ دریافت OpenAPI ناموفق بود: HTTP {status}\n{spec}")
            return 1
        definitions = spec.get("definitions") or spec.get("components", {}).get("schemas", {})
        print(f"✅ {len(definitions)} جدول/ویو در دسترس کلید anon:\n")
        for name, schema in sorted(definitions.items()):
            columns = list((schema.get("properties") or {}).keys())
            print(f"• {name}: {', '.join(columns) if columns else '—'}")
        print("\nنام جدول‌های مربوط به دوره/کتاب/جزوه را در .env بگذارید:")
        print("SUPABASE_TABLE_COURSES=... / SUPABASE_TABLE_BOOKS=... / SUPABASE_TABLE_NOTES=...")
        return 0

    query = urllib.parse.urlencode({"select": "*", "limit": str(args.rows)})
    status, rows = request(f"{urllib.parse.quote(args.table)}?{query}")
    if status != 200 or not isinstance(rows, list):
        print(f"❌ HTTP {status}: {rows}")
        return 1
    print(f"✅ {args.table}: {len(rows)} ردیف نمونه\n")
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, indent=2)[:1500])
        product = normalize_row(row, "course", site_base=settings.site_base_url,
                                type_column=settings.type_column)
        print("→ نگاشت ربات:", json.dumps(product.to_dict() if product else None,
                                          ensure_ascii=False))
        print("-" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
