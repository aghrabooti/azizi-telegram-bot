"""Catalog: schema-tolerant normalisation, filters, pagination, fallbacks."""

from __future__ import annotations

import json

import pytest

from bot import constants as C
from bot.services.catalog import (
    CatalogService,
    CatalogSnapshot,
    Product,
    normalize_row,
    parse_field,
    parse_grade,
)
from bot.services.navigation import render_catalog_list


@pytest.mark.parametrize(
    "raw,expected",
    [(9, 9), ("10", 10), ("پایه 11", 11), ("دوازدهم", 12), ("grade-12", 12),
     (None, None), ("", None), ("۹", 9), (7, None)],
)
def test_parse_grade(raw, expected):
    assert parse_grade(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [("ریاضی", "riazi"), ("ریاضی فیزیک", "riazi"), ("علوم تجربی", "tajrobi"),
     ("تجربی", "tajrobi"), ("انسانی", "ensani"), ("math", "riazi"), (None, None),
     ("نامشخص", None)],
)
def test_parse_field(raw, expected):
    assert parse_field(raw) == expected


def test_normalize_row_tolerates_unknown_column_names():
    row = {
        "uuid": "abc-123",
        "name": "سالیانه ریاضی دهم",
        "summary": "آموزش کامل",
        "cost": "2200000",
        "grade_level": "پایه 10",
        "major": "ریاضی فیزیک",
        "cover_url": "https://img",
    }
    product = normalize_row(row, "course")
    assert product is not None
    assert product.title == "سالیانه ریاضی دهم"
    assert product.price == 2_200_000
    assert product.grade == 10
    assert product.field == "riazi"
    assert product.url.endswith("abc-123")


def test_normalize_row_detects_books_and_notes():
    book = normalize_row({"id": "1", "title": "کتاب جامع ریاضی", "type": "book"}, "course")
    note = normalize_row({"id": "2", "title": "جزوه فصل اول"}, "course")
    assert book.type == "book"
    assert note.type == "note"


def test_inactive_rows_are_skipped():
    assert normalize_row({"id": "1", "title": "x", "is_active": False}, "course") is None
    assert normalize_row({"id": "1", "title": "x", "published": "false"}, "course") is None


def _items() -> list[Product]:
    return [
        Product("1", "course", "A", grade=9, field=None),
        Product("2", "course", "B", grade=10, field="riazi"),
        Product("3", "course", "C", grade=10, field="tajrobi"),
        Product("4", "book", "D", grade=12, field="tajrobi"),
        Product("5", "note", "E", grade=11, field="riazi"),
    ]


def test_filter_by_type_grade_field():
    items = _items()
    assert len(CatalogService.filter(items, C.TYPE_COURSE)) == 3
    assert len(CatalogService.filter(items, C.TYPE_BOOK)) == 1
    assert len(CatalogService.filter(items, C.TYPE_NOTE)) == 1
    assert [p.id for p in CatalogService.filter(items, C.TYPE_COURSE, "10")] == ["2", "3"]
    assert [
        p.id for p in CatalogService.filter(items, C.TYPE_COURSE, "10", C.FIELD_TAJROBI)
    ] == ["3"]


def test_items_without_field_appear_in_every_field():
    items = _items()
    result = CatalogService.filter(items, C.TYPE_COURSE, "9", C.FIELD_ENSANI)
    assert [p.id for p in result] == ["1"]


def test_seed_snapshot_is_used_when_supabase_is_not_configured(isolated_env):
    service = CatalogService()
    snapshot = service.get()
    assert snapshot.source in {"seed", "cache"}
    assert snapshot.items
    assert snapshot.counts()["course"] > 10


def test_cache_is_preferred_over_seed(isolated_env, monkeypatch):
    from bot.config.settings import settings

    payload = {
        "fetched_at": 1,
        "items": [Product("x", "course", "کش", grade=9).to_dict()],
    }
    settings.ensure_dirs()
    settings.catalog_cache_path.write_text(json.dumps(payload), encoding="utf-8")
    snapshot = CatalogService().get()
    assert snapshot.source == "cache"
    assert snapshot.items[0].title == "کش"


def test_pagination_and_empty_state(isolated_env):
    items = [Product(str(i), "course", f"دوره {i}", grade=10, field="riazi")
             for i in range(14)]
    snapshot = CatalogSnapshot(items, "live", 1.0)
    first = render_catalog_list(C.TYPE_COURSE, "10", C.FIELD_RIAZI, 1, snapshot)
    assert "cat:c:10:r:2" in first.callbacks()
    last = render_catalog_list(C.TYPE_COURSE, "10", C.FIELD_RIAZI, 3, snapshot)
    assert "cat:c:10:r:2" in last.callbacks()

    empty = render_catalog_list(C.TYPE_NOTE, "9", C.FIELD_ENSANI, 1, snapshot)
    assert "فعلاً موردی" in empty.text


def test_unavailable_catalog_gives_a_link_instead_of_silence(isolated_env):
    page = render_catalog_list(C.TYPE_COURSE, "9", C.FIELD_ALL, 1, CatalogSnapshot([], "none"))
    assert "دریافت لیست از سایت ممکن نیست" in page.text
    assert any(button.url for row in page.rows for button in row)


def test_prices_are_formatted_like_the_website(isolated_env):
    product = Product("1", "course", "x", price=2_200_000)
    assert "۲٬۲۰۰٬۰۰۰" in product.price_label()
    assert "تومان" in product.price_label()
    assert Product("2", "course", "y", price=None).price_label()
