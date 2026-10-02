"""Callback-data vocabulary.

Every callback_data follows one short pattern::

    <section>[:<action>][:<key>]

Telegram limits callback_data to 64 **bytes**, and Persian text is 2 bytes per
character, so we never put human text inside callback data — only short ASCII
codes that are mapped back to content here.

Keeping all of it in one module means:
  * the preview builder can enumerate every possible callback and assert that
    a page exists for it (dev/preview/build.py), and
  * a typo becomes an import error instead of a silent dead button.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# sections
# --------------------------------------------------------------------------
SEC_NAV = "nav"  # static pages
SEC_CAT = "cat"  # catalog browsing (courses / books / notes)
SEC_ANON = "anon"  # anonymous message flow
SEC_ADM = "adm"  # admin panel
SEC_NOOP = "noop"  # non-clickable label (page counters, etc.)

# --------------------------------------------------------------------------
# static pages (nav:<page>)
# --------------------------------------------------------------------------
PAGE_MAIN = "main"
PAGE_ABOUT = "about"
PAGE_SOCIAL = "social"
PAGE_SITE = "site"
PAGE_SUPPORT = "support"
PAGE_HELP = "help"

STATIC_PAGES = (PAGE_MAIN, PAGE_ABOUT, PAGE_SOCIAL, PAGE_SITE, PAGE_SUPPORT, PAGE_HELP)

# --------------------------------------------------------------------------
# catalog (cat:<type>[:<grade>[:<field>[:<page>]]])
# --------------------------------------------------------------------------
TYPE_COURSE = "c"
TYPE_BOOK = "b"
TYPE_NOTE = "n"
CATALOG_TYPES = (TYPE_COURSE, TYPE_BOOK, TYPE_NOTE)

#: short code -> canonical product type used by the catalog service
TYPE_SLUGS = {TYPE_COURSE: "course", TYPE_BOOK: "book", TYPE_NOTE: "note"}
SLUG_TYPES = {v: k for k, v in TYPE_SLUGS.items()}

GRADE_ALL = "a"
GRADES = ("9", "10", "11", "12")
GRADE_CODES = (GRADE_ALL,) + GRADES

FIELD_ALL = "a"
FIELD_RIAZI = "r"  # ریاضی فیزیک
FIELD_TAJROBI = "t"  # علوم تجربی
FIELD_ENSANI = "h"  # علوم انسانی
FIELD_CODES = (FIELD_ALL, FIELD_RIAZI, FIELD_TAJROBI, FIELD_ENSANI)

#: short code -> canonical field slug used by the catalog service
FIELD_SLUGS = {
    FIELD_RIAZI: "riazi",
    FIELD_TAJROBI: "tajrobi",
    FIELD_ENSANI: "ensani",
}
SLUG_FIELDS = {v: k for k, v in FIELD_SLUGS.items()}

# --------------------------------------------------------------------------
# anonymous messages (anon:<action>[:<key>])
# --------------------------------------------------------------------------
ANON_NEW = "new"
ANON_CANCEL = "cancel"

# --------------------------------------------------------------------------
# admin panel (adm:<section>[:<action>][:<key>])
# --------------------------------------------------------------------------
ADM_HOME = "home"
ADM_STATS = "stats"
ADM_USERS = "users"
ADM_LOGS = "logs"
ADM_DB = "db"
ADM_CONTENT = "content"
ADM_ANON = "anon"
ADM_CATALOG = "catalog"

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def cb(*parts: object) -> str:
    """Join callback parts: ``cb("cat", "c", "9")`` -> ``"cat:c:9"``."""
    return ":".join(str(p) for p in parts if p is not None and p != "")


def nav(page: str) -> str:
    return cb(SEC_NAV, page)


def catalog(
    type_code: str,
    grade: str | None = None,
    field: str | None = None,
    page: int | None = None,
) -> str:
    return cb(SEC_CAT, type_code, grade, field, page)


def admin(section: str, action: str | None = None, key: object | None = None) -> str:
    return cb(SEC_ADM, section, action, key)


def anon(action: str, key: object | None = None) -> str:
    return cb(SEC_ANON, action, key)


# --------------------------------------------------------------------------
# regex patterns used when registering handlers
# --------------------------------------------------------------------------
PATTERN_NAV = r"^nav:(?:main|about|social|site|support|help)$"
PATTERN_CAT = r"^cat:[cbn](?::(?:a|9|10|11|12))?(?::[arth])?(?::\d+)?$"
PATTERN_ANON = r"^anon:(?:new|cancel)$"
PATTERN_ADM = r"^adm:[a-z_]+(?::[a-z_0-9]+)?(?::[-\w]+)?$"
PATTERN_NOOP = r"^noop(?::.*)?$"
#: matches literally every callback the bot can produce (used by the phone gate
#: handler registered in group -1, before anything else)
PATTERN_ANY = r".*"
