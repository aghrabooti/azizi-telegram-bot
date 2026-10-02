#!/usr/bin/env python3
"""Switch between webhook and polling with a single command.

    python scripts/set_webhook.py --url https://example.com/telegram/webhook
    python scripts/set_webhook.py --delete        # back to polling
    python scripts/set_webhook.py --info          # getWebhookInfo

``allowed_updates`` always contains ``callback_query`` — without it every
inline button in the bot is silently dead.
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

from bot.app import ALLOWED_UPDATES  # noqa: E402
from bot.config.settings import settings  # noqa: E402


def call(method: str, payload: dict | None = None) -> dict:
    url = f"{settings.base_url}{settings.bot_token}/{method}"
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="setWebhook / deleteWebhook helper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="public HTTPS url of the webhook endpoint")
    group.add_argument("--delete", action="store_true", help="remove the webhook (polling)")
    group.add_argument("--info", action="store_true", help="print getWebhookInfo")
    parser.add_argument("--drop-pending", action="store_true", help="drop pending updates")
    args = parser.parse_args()

    if not settings.bot_token:
        print("❌ BOT_TOKEN تنظیم نشده است (.env)")
        return 2

    if args.info:
        print(json.dumps(call("getWebhookInfo"), ensure_ascii=False, indent=2))
        return 0

    if args.delete:
        result = call("deleteWebhook", {"drop_pending_updates": args.drop_pending})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("✅ وب‌هوک حذف شد — حالا می‌توانید polling را اجرا کنید." if result.get("ok")
              else "❌ حذف وب‌هوک ناموفق بود")
        return 0 if result.get("ok") else 1

    payload = {
        "url": args.url,
        "allowed_updates": ALLOWED_UPDATES,
        "drop_pending_updates": args.drop_pending,
        "max_connections": 40,
    }
    if settings.webhook_secret:
        payload["secret_token"] = settings.webhook_secret
    else:
        print("⚠️ WEBHOOK_SECRET خالی است — هر کسی می‌تواند به آدرس شما POST کند.")

    result = call("setWebhook", payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print("✅ وب‌هوک تنظیم شد. حتماً /healthz را چک کنید.")
        print(json.dumps(call("getWebhookInfo"), ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
