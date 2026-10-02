"""State-less navigation: a callback string -> a fully rendered page.

Nothing is stored per-user: every page knows its own parent, so "⬅️ بازگشت"
works even after a restart, after days, or on a message from last month.

The renderer returns plain dataclasses (text + rows of button dicts) and never
touches ``telegram`` objects, which is exactly what lets the live preview site
build real screens from the real source instead of a hand-written copy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Iterable

from bot import constants as C
from bot.config import content
from bot.config.settings import settings
from bot.services.catalog import CatalogService, CatalogSnapshot, Product
from bot.utils.text import esc, shorten


@dataclass
class Button:
    text: str
    callback: str | None = None
    url: str | None = None
    style: str = "primary"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "callback": self.callback,
            "url": self.url,
            "style": self.style,
        }


@dataclass
class Page:
    id: str
    title: str
    text: str
    rows: list[list[Button]] = field(default_factory=list)
    parent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "parent": self.parent,
            "rows": [[button.to_dict() for button in row] for row in self.rows],
        }

    def callbacks(self) -> list[str]:
        return [b.callback for row in self.rows for b in row if b.callback]


class UnknownPage(Exception):
    """Raised for a callback that has no page (expired / unknown button)."""


# ---------------------------------------------------------------------------
# static pages
# ---------------------------------------------------------------------------
def _nav_buttons(parent: str | None, page_id: str) -> list[list[Button]]:
    rows: list[list[Button]] = []
    tail: list[Button] = []
    if parent:
        tail.append(Button(content.text("btn.back"), callback=C.nav(parent)))
    if page_id != C.PAGE_MAIN:
        tail.append(Button(content.text("btn.main"), callback=C.nav(C.PAGE_MAIN)))
    if tail:
        rows.append(tail)
    return rows


def render_static(page_id: str) -> Page:
    spec = content.PAGES.get(page_id)
    if spec is None:
        raise UnknownPage(page_id)
    rows = [
        [
            Button(
                item["text"],
                callback=item.get("target"),
                url=item.get("url"),
                style=item.get("style", "primary"),
            )
            for item in row
        ]
        for row in spec["buttons"]
    ]
    rows += _nav_buttons(spec.get("parent"), page_id)
    return Page(
        id=C.nav(page_id),
        title=content.page_title(page_id),
        text=content.page_text(page_id),
        rows=rows,
        parent=C.nav(spec["parent"]) if spec.get("parent") else None,
    )


# ---------------------------------------------------------------------------
# catalog pages
# ---------------------------------------------------------------------------
def render_catalog_types(type_code: str) -> Page:
    """Step 1 — pick a grade (exactly like the website's grade filter)."""
    label = content.TYPE_LABELS[type_code]
    emoji = content.TYPE_EMOJI[type_code]
    rows: list[list[Button]] = [
        [
            Button(content.GRADE_LABELS["9"], callback=C.catalog(type_code, "9")),
            Button(content.GRADE_LABELS["10"], callback=C.catalog(type_code, "10")),
        ],
        [
            Button(content.GRADE_LABELS["11"], callback=C.catalog(type_code, "11")),
            Button(content.GRADE_LABELS["12"], callback=C.catalog(type_code, "12")),
        ],
        [
            Button(
                content.GRADE_LABELS[C.GRADE_ALL],
                callback=C.catalog(type_code, C.GRADE_ALL),
            )
        ],
    ]
    rows += _nav_buttons(C.PAGE_MAIN, "catalog")
    return Page(
        id=C.catalog(type_code),
        title=label,
        text=content.text("catalog.pick_grade", emoji=emoji, type_label=label),
        rows=rows,
        parent=C.nav(C.PAGE_MAIN),
    )


def render_catalog_fields(type_code: str, grade_code: str) -> Page:
    """Step 2 — pick a field of study."""
    label = content.TYPE_LABELS[type_code]
    emoji = content.TYPE_EMOJI[type_code]
    rows: list[list[Button]] = [
        [
            Button(
                content.FIELD_LABELS[C.FIELD_RIAZI],
                callback=C.catalog(type_code, grade_code, C.FIELD_RIAZI),
            ),
            Button(
                content.FIELD_LABELS[C.FIELD_TAJROBI],
                callback=C.catalog(type_code, grade_code, C.FIELD_TAJROBI),
            ),
        ],
        [
            Button(
                content.FIELD_LABELS[C.FIELD_ENSANI],
                callback=C.catalog(type_code, grade_code, C.FIELD_ENSANI),
            ),
            Button(
                content.FIELD_LABELS[C.FIELD_ALL],
                callback=C.catalog(type_code, grade_code, C.FIELD_ALL),
            ),
        ],
    ]
    rows.append(
        [
            Button(content.text("btn.back"), callback=C.catalog(type_code)),
            Button(content.text("btn.main"), callback=C.nav(C.PAGE_MAIN)),
        ]
    )
    return Page(
        id=C.catalog(type_code, grade_code),
        title=f"{label} — {content.GRADE_LABELS[grade_code]}",
        text=content.text(
            "catalog.pick_field",
            emoji=emoji,
            type_label=label,
            grade_label=content.GRADE_LABELS[grade_code],
        ),
        rows=rows,
        parent=C.catalog(type_code),
    )


def render_catalog_list(
    type_code: str,
    grade_code: str,
    field_code: str,
    page_number: int,
    snapshot: CatalogSnapshot,
    page_size: int | None = None,
) -> Page:
    """Step 3 — the real products, paginated."""
    page_size = page_size or settings.catalog_page_size
    label = content.TYPE_LABELS[type_code]
    emoji = content.TYPE_EMOJI[type_code]
    grade_label = content.GRADE_LABELS[grade_code]
    field_label = content.FIELD_LABELS[field_code]
    page_id = C.catalog(type_code, grade_code, field_code, page_number)
    parent = C.catalog(type_code, grade_code)

    if not snapshot.ok:
        rows = [
            [
                Button(
                    content.text("catalog.all_on_site"),
                    url=content.SITE_COURSES_URL,
                    style="success",
                )
            ],
            [
                Button(content.text("btn.back"), callback=parent),
                Button(content.text("btn.main"), callback=C.nav(C.PAGE_MAIN)),
            ],
        ]
        return Page(page_id, label, content.text("catalog.unavailable"), rows, parent)

    items: list[Product] = CatalogService.filter(snapshot.items, type_code, grade_code, field_code)
    total = len(items)

    if total == 0:
        rows = [
            [
                Button(
                    content.GRADE_LABELS[C.GRADE_ALL] + " / " + content.FIELD_LABELS[C.FIELD_ALL],
                    callback=C.catalog(type_code, C.GRADE_ALL, C.FIELD_ALL, 1),
                )
            ],
            [
                Button(
                    content.text("catalog.all_on_site"),
                    url=content.SITE_COURSES_URL,
                    style="success",
                )
            ],
            [
                Button(content.text("btn.back"), callback=parent),
                Button(content.text("btn.main"), callback=C.nav(C.PAGE_MAIN)),
            ],
        ]
        text = content.text(
            "catalog.empty",
            emoji=emoji,
            type_label=label,
            grade_label=grade_label,
            field_label=field_label,
        )
        return Page(page_id, label, text, rows, parent)

    pages = max(1, math.ceil(total / page_size))
    page_number = min(max(1, page_number), pages)
    start = (page_number - 1) * page_size
    chunk = items[start : start + page_size]

    from bot.utils.text import fa_digits

    body = [
        content.text(
            "catalog.list_header",
            emoji=emoji,
            type_label=label,
            grade_label=grade_label,
            field_label=field_label,
            count=fa_digits(total),
            page=fa_digits(page_number),
            pages=fa_digits(pages),
        )
    ]
    rows: list[list[Button]] = []
    for offset, item in enumerate(chunk, start=start + 1):
        description = f"{esc(shorten(item.description, 90))}\n" if item.description else ""
        body.append(
            content.text(
                "catalog.item_line",
                index=fa_digits(offset),
                title=esc(item.title),
                description=description,
                price=item.price_label(),
            )
        )
        rows.append(
            [
                Button(
                    content.text(
                        "catalog.open_button",
                        index=fa_digits(offset),
                        title=shorten(item.title, 40),
                    ),
                    url=item.url,
                    style="success",
                )
            ]
        )

    if snapshot.stale:
        body.append(content.text("catalog.stale_note"))

    pager: list[Button] = []
    if page_number > 1:
        pager.append(
            Button(
                content.text("btn.prev"),
                callback=C.catalog(type_code, grade_code, field_code, page_number - 1),
            )
        )
    if pages > 1:
        pager.append(Button(f"{fa_digits(page_number)}/{fa_digits(pages)}", callback="noop"))
    if page_number < pages:
        pager.append(
            Button(
                content.text("btn.next"),
                callback=C.catalog(type_code, grade_code, field_code, page_number + 1),
            )
        )
    if pager:
        rows.append(pager)

    rows.append(
        [Button(content.text("catalog.all_on_site"), url=content.SITE_COURSES_URL, style="success")]
    )
    rows.append(
        [
            Button(content.text("btn.back"), callback=parent),
            Button(content.text("btn.main"), callback=C.nav(C.PAGE_MAIN)),
        ]
    )
    return Page(page_id, label, "\n".join(body), rows, parent)


# ---------------------------------------------------------------------------
# anonymous message intro
# ---------------------------------------------------------------------------
def render_anon_intro() -> Page:
    rows = [
        [
            Button(content.text("btn.back"), callback=C.nav(C.PAGE_MAIN)),
            Button(content.text("btn.main"), callback=C.nav(C.PAGE_MAIN)),
        ]
    ]
    return Page(
        id=C.anon(C.ANON_NEW),
        title=content.text("anon.title"),
        text=content.text("anon.intro"),
        rows=rows,
        parent=C.nav(C.PAGE_MAIN),
    )


# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------
def parse_catalog(data: str) -> tuple[str, str | None, str | None, int | None]:
    parts = data.split(":")
    type_code = parts[1]
    grade = parts[2] if len(parts) > 2 else None
    field_code = parts[3] if len(parts) > 3 else None
    page_number = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else None
    if type_code not in C.CATALOG_TYPES:
        raise UnknownPage(data)
    if grade is not None and grade not in C.GRADE_CODES:
        raise UnknownPage(data)
    if field_code is not None and field_code not in C.FIELD_CODES:
        raise UnknownPage(data)
    return type_code, grade, field_code, page_number


def render(data: str, snapshot: CatalogSnapshot | None = None) -> Page:
    """Render any user-facing callback into a page (no Telegram objects)."""
    if data == C.nav(C.PAGE_MAIN) or data == "/start":
        return render_static(C.PAGE_MAIN)
    if data.startswith(f"{C.SEC_NAV}:"):
        return render_static(data.split(":", 1)[1])
    if data.startswith(f"{C.SEC_CAT}:"):
        type_code, grade, field_code, page_number = parse_catalog(data)
        if grade is None:
            return render_catalog_types(type_code)
        if field_code is None:
            return render_catalog_fields(type_code, grade)
        if snapshot is None:
            from bot.services.catalog import get_catalog

            snapshot = get_catalog().get()
        return render_catalog_list(type_code, grade, field_code, page_number or 1, snapshot)
    if data == C.anon(C.ANON_NEW):
        return render_anon_intro()
    raise UnknownPage(data)


def iter_all_pages(snapshot: CatalogSnapshot) -> Iterable[Page]:
    """Every user-facing page — used by the preview builder and its assertions."""
    for page_id in content.PAGES:
        yield render_static(page_id)
    for type_code in C.CATALOG_TYPES:
        yield render_catalog_types(type_code)
        for grade in C.GRADE_CODES:
            yield render_catalog_fields(type_code, grade)
            for field_code in C.FIELD_CODES:
                items = CatalogService.filter(snapshot.items, type_code, grade, field_code)
                pages = max(1, math.ceil(len(items) / settings.catalog_page_size))
                for number in range(1, pages + 1):
                    page = render_catalog_list(type_code, grade, field_code, number, snapshot)
                    yield page
                    if number == 1:
                        # the field buttons link to "cat:<t>:<g>:<f>" (page 1 implied)
                        yield replace(page, id=C.catalog(type_code, grade, field_code))
    yield render_anon_intro()
