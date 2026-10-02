"""Admin panel *views* — pure functions: data in, :class:`Page` out.

Keeping them free of Telegram objects means the live preview site renders the
exact same admin screens from the exact same code, with sample data.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from bot import constants as C
from bot.config import content
from bot.services.navigation import Button, Page
from bot.utils.text import esc, fa_digits, human_size, shorten

BACK_ROW = [Button(content.text("btn.back"), callback=C.admin(C.ADM_HOME))]
HOME_ROW = [
    Button(content.text("btn.back"), callback=C.admin(C.ADM_HOME)),
    Button(content.text("btn.main"), callback=C.nav(C.PAGE_MAIN)),
]


def home(stats: Mapping[str, Any]) -> Page:
    users = stats.get("users", {})
    events = stats.get("events", {})
    text = (
        "🛠 <b>پنل مدیریت</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"👥 کاربران: <b>{fa_digits(users.get('total', 0))}</b>"
        f" (امروز: {fa_digits(users.get('today', 0))})\n"
        f"📱 دارای شماره: <b>{fa_digits(users.get('with_phone', 0))}</b>\n"
        f"👁 بازدید صفحات: <b>{fa_digits(events.get('total', 0))}</b>"
        f" (امروز: {fa_digits(events.get('today', 0))})\n"
        f"📨 پیام‌های ناشناس: <b>{fa_digits(stats.get('anon_total', 0))}</b>"
        f" (خوانده‌نشده: {fa_digits(stats.get('anon_unread', 0))})"
    )
    unread = stats.get("anon_unread", 0)
    anon_label = "📨 پیام‌های ناشناس" + (f" ({fa_digits(unread)})" if unread else "")
    rows = [
        [Button("📊 آمار", callback=C.admin(C.ADM_STATS))],
        [Button("👥 کاربران و شماره‌ها", callback=C.admin(C.ADM_USERS))],
        [Button(anon_label, callback=C.admin(C.ADM_ANON))],
        [Button("📋 لاگ‌ها", callback=C.admin(C.ADM_LOGS))],
        [Button("💾 پشتیبان دیتابیس", callback=C.admin(C.ADM_DB))],
        [Button("✏️ ویرایش محتوا", callback=C.admin(C.ADM_CONTENT))],
        [Button("🗂 وضعیت کاتالوگ", callback=C.admin(C.ADM_CATALOG))],
        [Button(content.text("btn.main"), callback=C.nav(C.PAGE_MAIN))],
    ]
    return Page(C.admin(C.ADM_HOME), "پنل مدیریت", text, rows, C.nav(C.PAGE_MAIN))


def stats(data: Mapping[str, Any]) -> Page:
    users = data.get("users", {})
    events = data.get("events", {})

    def _top(rows: Sequence[tuple[str, int]]) -> str:
        if not rows:
            return "—"
        return "\n".join(
            f"{fa_digits(i)}. <code>{esc(key)}</code> — {fa_digits(count)}"
            for i, (key, count) in enumerate(rows, start=1)
        )

    text = (
        "📊 <b>آمار</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"👥 کل کاربران: <b>{fa_digits(users.get('total', 0))}</b>\n"
        f"🆕 کاربران امروز: <b>{fa_digits(users.get('today', 0))}</b>\n"
        f"📱 دارای شماره: <b>{fa_digits(users.get('with_phone', 0))}</b>\n"
        f"👁 کل بازدیدها: <b>{fa_digits(events.get('total', 0))}</b>\n"
        f"👁 بازدید امروز: <b>{fa_digits(events.get('today', 0))}</b>\n"
        f"🙋 کاربران فعال امروز: <b>{fa_digits(events.get('active_today', 0))}</b>\n\n"
        "🔝 <b>پربازدیدترین‌ها (کل)</b>\n"
        f"{_top(data.get('top_all', []))}\n\n"
        "🔝 <b>پربازدیدترین‌ها (امروز)</b>\n"
        f"{_top(data.get('top_today', []))}"
    )
    rows = [
        [Button("🗑 پاک‌کردن آمار", callback=C.admin(C.ADM_STATS, "reset"), style="danger")],
        HOME_ROW,
    ]
    return Page(C.admin(C.ADM_STATS), "آمار", text, rows, C.admin(C.ADM_HOME))


def stats_reset_confirm() -> Page:
    text = (
        "⚠️ <b>پاک‌کردن آمار</b>\n\n"
        "همه‌ی رویدادهای ثبت‌شده (بازدید صفحات) حذف می‌شوند. "
        "کاربران و پیام‌ها دست‌نخورده می‌مانند.\n\nمطمئن هستید؟"
    )
    rows = [
        [
            Button(
                "بله، پاک کن", callback=C.admin(C.ADM_STATS, "reset", "yes"), style="danger"
            ),
            Button("انصراف", callback=C.admin(C.ADM_STATS)),
        ]
    ]
    return Page(C.admin(C.ADM_STATS, "reset"), "پاک‌کردن آمار", text, rows, C.admin(C.ADM_STATS))


def users(rows_data: Sequence[Mapping[str, Any]], counts: Mapping[str, int], page: int,
          pages: int) -> Page:
    lines = [
        "👥 <b>کاربران و شماره‌ها</b>",
        f"کل: {fa_digits(counts.get('total', 0))} | "
        f"دارای شماره: {fa_digits(counts.get('with_phone', 0))} | "
        f"امروز: {fa_digits(counts.get('today', 0))}",
        f"صفحه {fa_digits(page)} از {fa_digits(pages)}",
        "➖➖➖➖➖➖➖➖➖➖",
    ]
    if not rows_data:
        lines.append("هنوز کاربری ثبت نشده است.")
    for row in rows_data:
        name = " ".join(filter(None, [row.get("first_name"), row.get("last_name")])) or "—"
        username = f"@{row['username']}" if row.get("username") else "—"
        phone = row.get("phone") or "—"
        lines.append(
            f"• <b>{esc(shorten(name, 30))}</b> | {esc(username)}\n"
            f"  <code>{esc(phone)}</code> | <code>{row.get('user_id')}</code>\n"
            f"  ثبت‌نام: {esc(str(row.get('created_at') or '')[:16])}"
        )
    nav_row: list[Button] = []
    if page > 1:
        nav_row.append(
            Button(content.text("btn.prev"), callback=C.admin(C.ADM_USERS, "page", page - 1))
        )
    if page < pages:
        nav_row.append(
            Button(content.text("btn.next"), callback=C.admin(C.ADM_USERS, "page", page + 1))
        )
    rows = [[Button("📥 خروجی CSV (اکسل فارسی)", callback=C.admin(C.ADM_USERS, "csv"))]]
    if nav_row:
        rows.insert(0, nav_row)
    rows.append(HOME_ROW)
    return Page(C.admin(C.ADM_USERS), "کاربران", "\n".join(lines), rows, C.admin(C.ADM_HOME))


def logs(lines: Sequence[str], log_path: str, size: int) -> Page:
    body = "\n".join(lines) if lines else "لاگی ثبت نشده است."
    text = (
        "📋 <b>لاگ‌ها</b>\n"
        f"<code>{esc(log_path)}</code> — {esc(human_size(size))}\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"<pre>{esc(body)}</pre>"
    )
    rows = [
        [Button("⬇️ دانلود فایل کامل", callback=C.admin(C.ADM_LOGS, "file"))],
        [Button("🔄 تازه‌سازی", callback=C.admin(C.ADM_LOGS))],
        HOME_ROW,
    ]
    return Page(C.admin(C.ADM_LOGS), "لاگ‌ها", text, rows, C.admin(C.ADM_HOME))


def database(info: Mapping[str, Any]) -> Page:
    text = (
        "💾 <b>پشتیبان‌گیری و بازیابی</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"فایل: <code>{esc(info.get('path', ''))}</code>\n"
        f"حجم: {esc(human_size(int(info.get('size', 0))))}\n"
        f"کاربران: {fa_digits(info.get('users', 0))} | "
        f"رویدادها: {fa_digits(info.get('events', 0))}\n\n"
        "پشتیبان با online backup رسمی SQLite گرفته می‌شود؛ "
        "لازم نیست ربات را متوقف کنید."
    )
    rows = [
        [Button("📦 گرفتن پشتیبان", callback=C.admin(C.ADM_DB, "backup"), style="success")],
        [Button("♻️ بازیابی از فایل", callback=C.admin(C.ADM_DB, "restore"), style="danger")],
        HOME_ROW,
    ]
    return Page(C.admin(C.ADM_DB), "دیتابیس", text, rows, C.admin(C.ADM_HOME))


def content_list(overrides: Mapping[str, str]) -> Page:
    lines = [
        "✏️ <b>ویرایش زنده‌ی محتوا</b>",
        "متن‌ها در دیتابیس ذخیره می‌شوند و بعد از ری‌استارت هم باقی می‌مانند.",
        "➖➖➖➖➖➖➖➖➖➖",
    ]
    rows: list[list[Button]] = []
    for index, (key, label) in enumerate(content.EDITABLE_KEYS):
        changed = "✅" if key in overrides else "▫️"
        lines.append(f"{changed} {esc(label)} — <code>{esc(key)}</code>")
        rows.append([Button(f"{changed} {label}", callback=C.admin(C.ADM_CONTENT, "edit", index))])
    rows.append(HOME_ROW)
    return Page(C.admin(C.ADM_CONTENT), "ویرایش محتوا", "\n".join(lines), rows,
                C.admin(C.ADM_HOME))


def content_edit(index: int, key: str, label: str, current: str, overridden: bool) -> Page:
    text = (
        f"✏️ <b>{esc(label)}</b>\n"
        f"<code>{esc(key)}</code>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"<b>متن فعلی:</b>\n<pre>{esc(current)}</pre>\n"
        "متن جدید را همین‌جا بفرستید. برای انصراف /cancel را بزنید."
    )
    rows: list[list[Button]] = []
    if overridden:
        rows.append(
            [
                Button(
                    "↩️ بازگشت به متن پیش‌فرض",
                    callback=C.admin(C.ADM_CONTENT, "reset", index),
                    style="danger",
                )
            ]
        )
    rows.append([Button(content.text("btn.back"), callback=C.admin(C.ADM_CONTENT))])
    return Page(
        C.admin(C.ADM_CONTENT, "edit", index), label, text, rows, C.admin(C.ADM_CONTENT)
    )


def anon_list(messages: Sequence[Mapping[str, Any]], page: int, pages: int, total: int,
              unread: int) -> Page:
    lines = [
        "📨 <b>پیام‌های ناشناس</b>",
        f"کل: {fa_digits(total)} | خوانده‌نشده: {fa_digits(unread)} | "
        f"صفحه {fa_digits(page)} از {fa_digits(pages)}",
        "فرستنده کاملاً ناشناس است؛ فقط کد پیام نمایش داده می‌شود.",
        "➖➖➖➖➖➖➖➖➖➖",
    ]
    rows: list[list[Button]] = []
    if not messages:
        lines.append("هنوز پیامی دریافت نشده است.")
    for row in messages:
        mark = "🟢" if not row.get("is_read") else "⚪️"
        answered = "↩️" if row.get("reply_body") else ""
        preview = shorten(str(row.get("body", "")).replace("\n", " "), 60)
        lines.append(
            f"{mark} <code>#{esc(row.get('code'))}</code> {answered}\n"
            f"  {esc(preview)}\n  🕐 {esc(str(row.get('created_at'))[:16])}"
        )
        rows.append(
            [
                Button(
                    f"{mark} #{row.get('code')} — {shorten(preview, 28)}",
                    callback=C.admin(C.ADM_ANON, "view", row.get("id")),
                )
            ]
        )
    nav_row: list[Button] = []
    if page > 1:
        nav_row.append(
            Button(content.text("btn.prev"), callback=C.admin(C.ADM_ANON, "page", page - 1))
        )
    if page < pages:
        nav_row.append(
            Button(content.text("btn.next"), callback=C.admin(C.ADM_ANON, "page", page + 1))
        )
    if nav_row:
        rows.append(nav_row)
    rows.append(HOME_ROW)
    return Page(C.admin(C.ADM_ANON), "پیام‌های ناشناس", "\n".join(lines), rows,
                C.admin(C.ADM_HOME))


def anon_detail(row: Mapping[str, Any]) -> Page:
    reply = row.get("reply_body")
    text = (
        f"🕵️ <b>پیام ناشناس</b> <code>#{esc(row.get('code'))}</code>\n"
        f"🕐 {esc(str(row.get('created_at'))[:16])}\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"{esc(row.get('body', ''))}\n"
        "➖➖➖➖➖➖➖➖➖➖"
    )
    if reply:
        text += f"\n↩️ <b>پاسخ شما:</b>\n{esc(reply)}\n🕐 {esc(str(row.get('replied_at'))[:16])}"
    rows = [
        [
            Button(
                "✍️ پاسخ به فرستنده",
                callback=C.admin(C.ADM_ANON, "reply", row.get("id")),
                style="success",
            )
        ],
        [Button(content.text("btn.back"), callback=C.admin(C.ADM_ANON))],
        [Button(content.text("btn.main"), callback=C.nav(C.PAGE_MAIN))],
    ]
    return Page(
        C.admin(C.ADM_ANON, "view", row.get("id")),
        f"#{row.get('code')}",
        text,
        rows,
        C.admin(C.ADM_ANON),
    )


def catalog_status(info: Mapping[str, Any]) -> Page:
    source_labels = {
        "live": "🟢 زنده از Supabase",
        "cache": "🟡 کش محلی (آخرین دریافت موفق)",
        "seed": "🟠 نسخه‌ی همراه ربات (snapshot سایت)",
        "none": "🔴 بدون داده",
    }
    counts = info.get("counts", {})
    text = (
        "🗂 <b>وضعیت کاتالوگ</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"منبع: {source_labels.get(info.get('source', 'none'), info.get('source'))}\n"
        f"آخرین دریافت: {esc(info.get('fetched_at_label', '—'))}\n"
        f"🎓 دوره: {fa_digits(counts.get('course', 0))} | "
        f"📚 کتاب: {fa_digits(counts.get('book', 0))} | "
        f"📝 جزوه: {fa_digits(counts.get('note', 0))}\n"
        f"Supabase تنظیم شده؟ {'بله' if info.get('configured') else 'خیر'}\n"
    )
    if info.get("error"):
        text += f"\n⚠️ آخرین خطا:\n<code>{esc(shorten(str(info['error']), 300))}</code>"
    rows = [
        [Button("🔄 دریافت دوباره", callback=C.admin(C.ADM_CATALOG, "refresh"), style="success")],
        HOME_ROW,
    ]
    return Page(C.admin(C.ADM_CATALOG), "کاتالوگ", text, rows, C.admin(C.ADM_HOME))
