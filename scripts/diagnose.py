#!/usr/bin/env python3
"""Troubleshooting in the right order — run this before asking anyone for help.

    python scripts/diagnose.py              # everything
    python scripts/diagnose.py --getme      # only the token check
    python scripts/diagnose.py --post URL   # manual POST to your own webhook

Order (same as the README):
    1. can this host reach api.telegram.org at all?
    2. getMe with the token
    3. getWebhookInfo
    4. manual POST with the secret header
    5. tail of data/bot.log

Nothing printed here contains the token — output is safe to share.
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config.settings import ENV_FILE_PROBLEMS, settings  # noqa: E402
from bot.utils.logging import redact  # noqa: E402

OK = "✅"
BAD = "❌"
WARN = "⚠️"


def section(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 56 - len(title)))


def check_env() -> None:
    section("۱) بررسی .env و تنظیمات")
    for problem in ENV_FILE_PROBLEMS:
        print(f"{BAD} .env: {problem}")
    if not ENV_FILE_PROBLEMS:
        print(f"{OK} .env فقط شامل خطوط KEY=value است")
    print(f"{OK if settings.bot_token else BAD} BOT_TOKEN "
          f"{'تنظیم شده' if settings.bot_token else 'تنظیم نشده'}")
    print(f"{OK if settings.admin_ids else WARN} ADMIN_IDS = {list(settings.admin_ids) or '—'}")
    print(f"{OK} API root = {settings.api_root}")
    print(f"{OK} data dir = {settings.data_dir}")
    print(f"{OK if settings.supabase_configured else WARN} Supabase "
          f"{'تنظیم شده' if settings.supabase_configured else 'تنظیم نشده (کاتالوگ آفلاین)'}")


def check_connectivity() -> None:
    section("۲) دسترسی شبکه به API تلگرام")
    host = urllib.parse.urlparse(settings.api_root).hostname or "api.telegram.org"
    try:
        start = time.time()
        addresses = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        print(f"{OK} DNS {host} → {addresses[0][4][0]} ({(time.time() - start) * 1000:.0f}ms)")
    except OSError as exc:
        print(f"{BAD} DNS برای {host} شکست خورد: {exc}")
        return
    try:
        start = time.time()
        with socket.create_connection((host, 443), timeout=10) as raw:
            context = ssl.create_default_context()
            with context.wrap_socket(raw, server_hostname=host):
                print(f"{OK} TLS به {host}:443 برقرار شد ({(time.time() - start) * 1000:.0f}ms)")
    except OSError as exc:
        print(f"{BAD} اتصال به {host}:443 ممکن نشد: {exc}")
        print("   اگر سرور داخل ایران است این طبیعی است — "
              "یا VPS خارج بگیرید یا TELEGRAM_API_ROOT را روی یک رله تنظیم کنید.")


def api_call(method: str, payload: dict | None = None, timeout: int = 20) -> dict:
    url = f"{settings.base_url}{settings.bot_token}/{method}"
    data = json.dumps(payload).encode() if payload else None
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode())
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": f"HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": redact(str(exc))}


def check_getme() -> None:
    section("۳) getMe (اعتبار توکن)")
    if not settings.bot_token:
        print(f"{BAD} توکن تنظیم نشده")
        return
    result = api_call("getMe")
    if result.get("ok"):
        me = result["result"]
        print(f"{OK} @{me.get('username')} (id={me.get('id')})")
    else:
        print(f"{BAD} {json.dumps(result, ensure_ascii=False)}")
        print("   اگر 401 است یعنی توکن اشتباه/باطل شده — در @BotFather دوباره بسازید.")


def check_webhook() -> None:
    section("۴) getWebhookInfo")
    result = api_call("getWebhookInfo")
    if not result.get("ok"):
        print(f"{BAD} {json.dumps(result, ensure_ascii=False)}")
        return
    info = result["result"]
    url = info.get("url") or "(خالی — حالت polling)"
    print(f"{OK} url = {url}")
    print(f"   pending_update_count = {info.get('pending_update_count')}")
    print(f"   allowed_updates = {info.get('allowed_updates', 'پیش‌فرض')}")
    if info.get("last_error_message"):
        print(f"{BAD} last_error = {info.get('last_error_message')} "
              f"({info.get('last_error_date')})")
    allowed = info.get("allowed_updates")
    if url and allowed and "callback_query" not in allowed:
        print(f"{BAD} callback_query در allowed_updates نیست → دکمه‌ها هرگز کار نمی‌کنند!")


def check_post(url: str) -> None:
    section("۵) POST دستی به وب‌هوک خودمان")
    payload = {"update_id": 1}
    headers = {"Content-Type": "application/json"}
    if settings.webhook_secret:
        headers["X-Telegram-Bot-Api-Secret-Token"] = settings.webhook_secret
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers
    )
    start = time.time()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode()[:400]
            print(f"{OK} HTTP {response.status} در {time.time() - start:.1f}s → {body}")
    except urllib.error.HTTPError as exc:
        print(f"{WARN} HTTP {exc.code} در {time.time() - start:.1f}s → "
              f"{exc.read().decode()[:400]}")
    except Exception as exc:  # noqa: BLE001
        print(f"{BAD} {redact(str(exc))}")


def check_health(url: str) -> None:
    section("۶) /healthz")
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            print(f"{OK} {response.read().decode()[:400]}")
    except Exception as exc:  # noqa: BLE001
        print(f"{BAD} {redact(str(exc))}")


def check_runtime() -> None:
    section("۷) دیتابیس، کاتالوگ و لاگ")
    try:
        from bot.services.database import Database

        db = Database(settings.db_path)
        counts = db.user_counts()
        print(f"{OK} دیتابیس {settings.db_path} — کاربران: {counts['total']}، "
              f"دارای شماره: {counts['with_phone']}")
    except Exception as exc:  # noqa: BLE001
        print(f"{BAD} دیتابیس: {exc}")
    try:
        from bot.services.catalog import get_catalog

        snapshot = get_catalog().get()
        print(f"{OK} کاتالوگ: منبع={snapshot.source} تعداد={len(snapshot.items)} "
              f"{snapshot.counts()}")
        if snapshot.error:
            print(f"{WARN} آخرین خطای کاتالوگ: {snapshot.error}")
    except Exception as exc:  # noqa: BLE001
        print(f"{BAD} کاتالوگ: {exc}")

    log_path = settings.log_path
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]
        print(f"{OK} ۱۵ خط آخر {log_path}:")
        for line in lines:
            print("   " + redact(line))
    else:
        print(f"{WARN} فایل لاگ هنوز ساخته نشده: {log_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="بررسی سلامت ربات")
    parser.add_argument("--getme", action="store_true", help="فقط getMe")
    parser.add_argument("--post", metavar="URL", help="POST دستی به وب‌هوک")
    parser.add_argument("--health", metavar="URL", help="بررسی /healthz")
    args = parser.parse_args()

    print("🔎 azizi-telegram-bot — عیب‌یابی (خروجی بدون توکن، قابل اشتراک‌گذاری)")
    if args.getme:
        check_getme()
        return 0
    check_env()
    check_connectivity()
    check_getme()
    check_webhook()
    if args.post:
        check_post(args.post)
    if args.health:
        check_health(args.health)
    check_runtime()
    print("\nتمام شد. اگر مشکل پابرجاست، همین خروجی را برای من بفرستید.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
