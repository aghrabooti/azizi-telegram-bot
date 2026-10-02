"""All user-facing content in one place.

Changing a word in the bot must never require touching logic.  Every string the
user can see lives in :data:`TEXTS`, and every static screen lives in
:data:`PAGES` (text + buttons + parent page, so navigation is state-less).

Admins can override any key in :data:`EDITABLE_KEYS` live from Telegram; the
override is stored in SQLite and wins over the defaults below (see
``bot.services.content_store``).
"""

from __future__ import annotations

from typing import Any, Callable

from bot import constants as C

# ---------------------------------------------------------------------------
# site / links  (single source of truth for every external URL)
# ---------------------------------------------------------------------------
SITE_URL = "https://www.mahdiazizi.com"
SITE_COURSES_URL = f"{SITE_URL}/courses"
SITE_ABOUT_URL = f"{SITE_URL}/about-us"
SITE_LOGIN_URL = f"{SITE_URL}/login"
SITE_REGISTER_URL = f"{SITE_URL}/register"
SITE_DETAIL_URL = f"{SITE_URL}/courses-detail?id={{id}}"

#: the four official pages listed on the "درباره ما" page of the website
SOCIAL_LINKS: tuple[dict[str, str], ...] = (
    {
        "key": "telegram",
        "title": "کانال تلگرام",
        "handle": "t.me/mahdiazizi_math",
        "url": "https://t.me/mahdiazizi_math",
        "note": "۵۹٬۰۰۰+ عضو",
    },
    {
        "key": "bale",
        "title": "کانال بله",
        "handle": "ble.ir/mahdiiazizii_math",
        "url": "https://ble.ir/mahdiiazizii_math",
        "note": "۱۳٬۱۰۰+ عضو",
    },
    {
        "key": "aparat",
        "title": "آپارات",
        "handle": "aparat.com/mahdiazizii",
        "url": "https://www.aparat.com/mahdiazizii",
        "note": "۷٬۴۰۰+ دنبال‌کننده",
    },
    {
        "key": "instagram",
        "title": "اینستاگرام",
        "handle": "instagram.com/mahdiazizi_math",
        "url": "https://www.instagram.com/mahdiazizi_math/",
        "note": "صفحه‌ی رسمی",
    },
)

SUPPORT_URL = "https://t.me/math1360"

# ---------------------------------------------------------------------------
# labels for catalog filters
# ---------------------------------------------------------------------------
TYPE_LABELS = {
    C.TYPE_COURSE: "دوره‌های آموزشی",
    C.TYPE_BOOK: "کتاب‌ها",
    C.TYPE_NOTE: "جزوه‌ها",
}
TYPE_EMOJI = {C.TYPE_COURSE: "🎓", C.TYPE_BOOK: "📚", C.TYPE_NOTE: "📝"}

GRADE_LABELS = {
    C.GRADE_ALL: "همه پایه‌ها",
    "9": "نهم",
    "10": "دهم",
    "11": "یازدهم",
    "12": "دوازدهم",
}

FIELD_LABELS = {
    C.FIELD_ALL: "همه رشته‌ها",
    C.FIELD_RIAZI: "ریاضی فیزیک",
    C.FIELD_TAJROBI: "علوم تجربی",
    C.FIELD_ENSANI: "علوم انسانی",
}

# ---------------------------------------------------------------------------
# texts
# ---------------------------------------------------------------------------
TEXTS: dict[str, str] = {
    # --- onboarding / phone gate -------------------------------------------------
    "phone.request": (
        "سلام {name} عزیز 👋\n"
        "به ربات رسمی <b>آکادمی استاد مهدی عزیزی</b> خوش آمدید.\n\n"
        "برای ورود به ربات، لطفاً شماره‌ی موبایل خود را ثبت کنید.\n"
        "کافی است روی دکمه‌ی «📱 ارسال شماره‌ی من» پایین صفحه بزنید.\n\n"
        "<i>شماره فقط برای پشتیبانی و مشاوره‌ی آموزشی استفاده می‌شود و در "
        "اختیار هیچ شخص دیگری قرار نمی‌گیرد.</i>"
    ),
    "phone.button": "📱 ارسال شماره‌ی من",
    "phone.invalid": (
        "❌ شماره‌ی معتبری دریافت نشد.\n\n"
        "لطفاً به‌جای تایپ کردن، روی دکمه‌ی «📱 ارسال شماره‌ی من» در پایین صفحه بزنید.\n"
        "اگر شماره را تایپ می‌کنید باید با کد کشور و + باشد؛ مثال: <code>+989121234567</code>"
    ),
    "phone.not_text": (
        "برای ورود به ربات ابتدا باید شماره‌ی موبایلتان ثبت شود.\n"
        "لطفاً روی دکمه‌ی «📱 ارسال شماره‌ی من» در پایین صفحه بزنید."
    ),
    "phone.foreign_contact": (
        "❌ این شماره متعلق به حساب شما نیست.\n"
        "لطفاً با دکمه‌ی «📱 ارسال شماره‌ی من» شماره‌ی خودتان را بفرستید."
    ),
    "phone.saved": "✅ شماره‌ی شما ثبت شد: <code>{phone}</code>",
    "phone.gate_callback": (
        "برای استفاده از ربات ابتدا باید شماره‌ی موبایلتان ثبت شود. "
        "لطفاً دکمه‌ی پایین صفحه را بزنید."
    ),
    # --- main menu ---------------------------------------------------------------
    "main.title": "منوی اصلی",
    "main.text": (
        "🎯 <b>آکادمی استاد مهدی عزیزی</b>\n"
        "آموزش مفهومی ریاضیات | نهم تا دوازدهم\n\n"
        "از منوی زیر انتخاب کنید:"
    ),
    # --- about -------------------------------------------------------------------
    "about.title": "درباره‌ی استاد مهدی عزیزی",
    "about.text": (
        "👨‍🏫 <b>استاد مهدی عزیزی</b>\n"
        "مدرس ریاضیات و حسابان کنکور، دانش‌آموخته‌ی کارشناسی ریاضی محض "
        "دانشگاه شهید بهشتی و مؤلف کتاب‌های کمک‌آموزشی.\n\n"
        "آکادمی عزیزی با هدف آموزش مفهومی و عمیق ریاضیات دوره‌ی متوسطه شکل گرفته است؛ "
        "تمرکز بر <b>فهمیدن</b> به‌جای حفظ‌کردن، با پوشش کامل پایه‌های نهم تا دوازدهم "
        "در رشته‌های ریاضی و تجربی.\n\n"
        "• 🎥 پکیج‌های ویدئویی مفهومی و تستی\n"
        "• 📝 جزوه‌های اختصاصی هر فصل\n"
        "• 📚 کتاب و جزوه‌ی چاپی ارسالی به سراسر کشور\n"
        "• 🔴 کلاس‌های آنلاین زنده\n"
        "• 💬 پشتیبانی و رفع اشکال تا روز امتحان"
    ),
    # --- social ------------------------------------------------------------------
    "social.title": "صفحات استاد مهدی عزیزی",
    "social.text": (
        "🔗 <b>صفحات رسمی استاد مهدی عزیزی</b>\n\n"
        "محتوای رایگان، نمونه تدریس‌ها و تحلیل آزمون‌ها در کانال‌های رسمی زیر منتشر می‌شود:\n\n"
        "{list}\n"
        "⚠️ هر کانال یا صفحه‌ای غیر از این چهار مورد، به آکادمی عزیزی تعلق ندارد."
    ),
    # --- site --------------------------------------------------------------------
    "site.title": "ورود به سایت",
    "site.text": (
        "🌐 <b>سایت رسمی آکادمی</b>\n\n"
        "در سایت می‌توانید پکیج‌ها را ببینید، ثبت‌نام کنید و بعد از خرید، "
        "دوره‌ها بلافاصله در داشبورد شما باز می‌شوند.\n\n"
        f"آدرس: {SITE_URL}"
    ),
    # --- support -----------------------------------------------------------------
    "support.title": "پشتیبانی",
    "support.text": (
        "💬 <b>پشتیبانی آموزشی</b>\n\n"
        "برای سوال درباره‌ی پکیج‌ها، خرید، ارسال پستی یا رفع اشکال، "
        "با پشتیبانی در تلگرام در ارتباط باشید.\n\n"
        "اگر ترجیح می‌دهید هویت‌تان فاش نشود، از گزینه‌ی «ارسال پیام ناشناس» در منوی اصلی "
        "استفاده کنید."
    ),
    # --- help --------------------------------------------------------------------
    "help.title": "راهنما",
    "help.text": (
        "ℹ️ <b>راهنمای ربات</b>\n\n"
        "• /start — شروع دوباره و نمایش منوی اصلی\n"
        "• /menu — نمایش منوی اصلی\n"
        "• /help — همین صفحه\n\n"
        "در هر صفحه دکمه‌ی «⬅️ بازگشت» شما را به صفحه‌ی قبل و دکمه‌ی «🏠 منوی اصلی» "
        "به ابتدای ربات برمی‌گرداند."
    ),
    # --- catalog -----------------------------------------------------------------
    "catalog.pick_grade": (
        "{emoji} <b>{type_label}</b>\n\nپایه‌ی تحصیلی مورد نظر را انتخاب کنید:"
    ),
    "catalog.pick_field": (
        "{emoji} <b>{type_label}</b> — {grade_label}\n\nرشته‌ی تحصیلی را انتخاب کنید:"
    ),
    "catalog.list_header": (
        "{emoji} <b>{type_label}</b>\n"
        "پایه: {grade_label} | رشته: {field_label}\n"
        "تعداد: {count} مورد | صفحه {page} از {pages}\n"
        "➖➖➖➖➖➖➖➖➖➖"
    ),
    "catalog.item_line": "<b>{index}. {title}</b>\n{description}💰 {price}\n",
    "catalog.empty": (
        "{emoji} <b>{type_label}</b>\n"
        "پایه: {grade_label} | رشته: {field_label}\n\n"
        "فعلاً موردی با این فیلتر ثبت نشده است.\n"
        "می‌توانید فیلتر دیگری انتخاب کنید یا همه‌ی موارد را ببینید."
    ),
    "catalog.unavailable": (
        "⚠️ در حال حاضر دریافت لیست از سایت ممکن نیست.\n\n"
        "لطفاً چند دقیقه‌ی دیگر دوباره تلاش کنید یا مستقیماً از سایت ببینید:\n"
        f"{SITE_COURSES_URL}"
    ),
    "catalog.price_free": "رایگان",
    "catalog.price_unknown": "برای قیمت به سایت مراجعه کنید",
    "catalog.price_toman": "{amount} تومان",
    "catalog.open_button": "{index}. {title}",
    "catalog.all_on_site": "🌐 مشاهده‌ی همه در سایت",
    "catalog.stale_note": "\n<i>(لیست از آخرین نسخه‌ی ذخیره‌شده نمایش داده می‌شود)</i>",
    # --- anonymous ---------------------------------------------------------------
    "anon.title": "ارسال پیام ناشناس",
    "anon.intro": (
        "🕵️ <b>ارسال پیام ناشناس</b>\n\n"
        "پیام شما بدون نام، بدون یوزرنیم و بدون شماره برای مدیریت ارسال می‌شود؛ "
        "فقط یک کد تصادفی کنار پیام می‌آید تا پاسخ به شما برسد.\n\n"
        "متن پیام خود را بنویسید و ارسال کنید."
    ),
    "anon.sent": (
        "✅ پیام شما با کد <code>{code}</code> ارسال شد.\n"
        "اگر مدیریت پاسخ بدهد، همین‌جا به شما اطلاع داده می‌شود."
    ),
    "anon.too_short": "پیام خیلی کوتاه است. لطفاً کمی کامل‌تر بنویسید (حداقل ۵ کاراکتر).",
    "anon.too_long": "پیام طولانی‌تر از حد مجاز است (حداکثر ۴۰۰۰ کاراکتر).",
    "anon.only_text": "فقط پیام متنی پذیرفته می‌شود. لطفاً متن پیام را بنویسید.",
    "anon.cancelled": "ارسال پیام ناشناس لغو شد.",
    "anon.rate_limited": "لطفاً کمی صبر کنید؛ شما به‌تازگی پیام فرستاده‌اید.",
    "anon.reply_to_user": "📬 <b>پاسخ مدیریت به پیام {code}:</b>\n\n{text}",
    # --- generic -----------------------------------------------------------------
    "btn.back": "⬅️ بازگشت",
    "btn.main": "🏠 منوی اصلی",
    "btn.prev": "⬅️ قبلی",
    "btn.next": "بعدی ➡️",
    "error.expired": "این دکمه منقضی شده است. لطفاً /start را بزنید.",
    "error.generic": "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید یا /start را بزنید.",
    "error.admin_only": "این بخش فقط برای مدیران است.",
}

# ---------------------------------------------------------------------------
# keys an admin may edit from inside Telegram
# ---------------------------------------------------------------------------
EDITABLE_KEYS: tuple[tuple[str, str], ...] = (
    ("main.text", "متن منوی اصلی"),
    ("about.text", "متن درباره‌ی استاد"),
    ("social.text", "متن صفحات رسمی"),
    ("site.text", "متن ورود به سایت"),
    ("support.text", "متن پشتیبانی"),
    ("anon.intro", "متن ارسال پیام ناشناس"),
    ("phone.request", "متن درخواست شماره"),
    ("help.text", "متن راهنما"),
)

# ---------------------------------------------------------------------------
# static pages: text + buttons + parent (navigation is state-less)
# ---------------------------------------------------------------------------
PAGES: dict[str, dict[str, Any]] = {
    C.PAGE_MAIN: {
        "title_key": "main.title",
        "text_key": "main.text",
        "parent": None,
        "buttons": [
            [{"text": "🎓 مشاهده دوره‌ها", "target": C.catalog(C.TYPE_COURSE)}],
            [{"text": "📝 مشاهده جزوه‌ها", "target": C.catalog(C.TYPE_NOTE)}],
            [{"text": "📚 مشاهده کتاب‌ها", "target": C.catalog(C.TYPE_BOOK)}],
            [{"text": "🌐 ورود به سایت", "url": SITE_URL, "style": "success"}],
            [{"text": "👤 صفحات استاد مهدی عزیزی", "target": C.nav(C.PAGE_SOCIAL)}],
            [{"text": "🕵️ ارسال پیام ناشناس", "target": C.anon(C.ANON_NEW)}],
            [
                {"text": "ℹ️ درباره‌ی آکادمی", "target": C.nav(C.PAGE_ABOUT)},
                {"text": "💬 پشتیبانی", "target": C.nav(C.PAGE_SUPPORT)},
            ],
        ],
    },
    C.PAGE_ABOUT: {
        "title_key": "about.title",
        "text_key": "about.text",
        "parent": C.PAGE_MAIN,
        "buttons": [
            [{"text": "👤 صفحات رسمی استاد", "target": C.nav(C.PAGE_SOCIAL)}],
            [{"text": "🌐 صفحه‌ی درباره ما در سایت", "url": SITE_ABOUT_URL, "style": "success"}],
        ],
    },
    C.PAGE_SOCIAL: {
        "title_key": "social.title",
        "text_key": "social.text",
        "parent": C.PAGE_MAIN,
        "buttons": [
            [{"text": f"📣 {link['title']}", "url": link["url"], "style": "success"}]
            for link in SOCIAL_LINKS
        ],
    },
    C.PAGE_SITE: {
        "title_key": "site.title",
        "text_key": "site.text",
        "parent": C.PAGE_MAIN,
        "buttons": [
            [{"text": "🌐 باز کردن سایت", "url": SITE_URL, "style": "success"}],
            [{"text": "🛒 فروشگاه پکیج‌ها", "url": SITE_COURSES_URL, "style": "success"}],
            [{"text": "🔑 ورود / ثبت‌نام", "url": SITE_LOGIN_URL, "style": "success"}],
        ],
    },
    C.PAGE_SUPPORT: {
        "title_key": "support.title",
        "text_key": "support.text",
        "parent": C.PAGE_MAIN,
        "buttons": [
            [{"text": "💬 چت با پشتیبانی", "url": SUPPORT_URL, "style": "success"}],
            [{"text": "🕵️ ارسال پیام ناشناس", "target": C.anon(C.ANON_NEW)}],
        ],
    },
    C.PAGE_HELP: {
        "title_key": "help.title",
        "text_key": "help.text",
        "parent": C.PAGE_MAIN,
        "buttons": [],
    },
}

# ---------------------------------------------------------------------------
# text resolution (with live admin overrides)
# ---------------------------------------------------------------------------
#: installed by bot.services.content_store at startup; keeps content.py free of
#: database imports (and therefore importable by the preview builder/tests).
_override_resolver: Callable[[str], str | None] | None = None


def set_override_resolver(resolver: Callable[[str], str | None] | None) -> None:
    global _override_resolver
    _override_resolver = resolver


def text(key: str, **kwargs: Any) -> str:
    """Return content for *key*, honouring admin overrides, then format it."""
    value: str | None = None
    if _override_resolver is not None:
        try:
            value = _override_resolver(key)
        except Exception:  # pragma: no cover - never break rendering
            value = None
    if value is None:
        value = TEXTS.get(key, key)
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return value
    return value


def default_text(key: str) -> str:
    return TEXTS.get(key, "")


def social_list_text() -> str:
    lines = [
        f"• <b>{link['title']}</b> — {link['handle']}\n  <i>{link['note']}</i>"
        for link in SOCIAL_LINKS
    ]
    return "\n".join(lines) + "\n"


def page_text(page_id: str) -> str:
    """Render the body of a static page."""
    spec = PAGES[page_id]
    if page_id == C.PAGE_SOCIAL:
        return text(spec["text_key"], list=social_list_text())
    return text(spec["text_key"])


def page_title(page_id: str) -> str:
    return text(PAGES[page_id]["title_key"])
