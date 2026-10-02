"""Product catalog (courses / books / notes) coming from the real website.

Source of truth (in order):

1. **Supabase REST** — the same public ``anon`` key the website uses in the
   browser (``SUPABASE_URL`` + ``SUPABASE_ANON_KEY``).  This is the live data.
2. **Disk cache** — the last successful live fetch (``data/catalog_cache.json``);
   used when the host temporarily cannot reach Supabase so the bot never shows
   an empty shop.
3. **Seed snapshot** — ``bot/config/catalog_seed.json``, captured from the
   public JSON-LD of https://www.mahdiazizi.com/courses.  Last-resort fallback
   only; the admin panel always shows which source is being used.

Column names differ between projects, so every row goes through a tolerant
normaliser instead of assuming a schema.  ``scripts/probe_supabase.py`` prints
the real schema when you have the key — never guess, measure.
"""

from __future__ import annotations

import json
import logging
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from bot import constants as C
from bot.config import content
from bot.config.settings import Settings
from bot.config.settings import settings as default_settings
from bot.utils.text import to_en_digits

logger = logging.getLogger(__name__)

SEED_PATH = Path(__file__).resolve().parents[1] / "config" / "catalog_seed.json"

TYPE_COURSE = "course"
TYPE_BOOK = "book"
TYPE_NOTE = "note"

_TITLE_KEYS = ("title", "name", "course_name", "book_name", "note_name", "label")
_DESC_KEYS = ("description", "short_description", "summary", "subtitle", "excerpt", "intro")
_PRICE_KEYS = ("price", "amount", "cost", "final_price", "price_toman", "sale_price")
_GRADE_KEYS = ("grade", "grade_level", "level", "base", "paye", "grade_name", "educational_level")
_FIELD_KEYS = ("field", "major", "branch", "discipline", "field_name", "reshte", "study_field")
_IMAGE_KEYS = ("image", "image_url", "cover", "cover_url", "thumbnail", "picture", "photo")
_ACTIVE_KEYS = ("is_active", "active", "published", "is_published", "visible", "enabled")
_TYPE_HINTS = {
    TYPE_BOOK: ("book", "کتاب"),
    TYPE_NOTE: ("note", "جزوه", "pamphlet", "booklet"),
    TYPE_COURSE: ("course", "دوره", "package", "پکیج"),
}

_GRADE_WORDS = {
    "نهم": 9,
    "دهم": 10,
    "یازدهم": 11,
    "دوازدهم": 12,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
}


# ---------------------------------------------------------------------------
# data model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Product:
    id: str
    type: str
    title: str
    description: str = ""
    price: int | None = None
    grade: int | None = None
    field: str | None = None
    url: str = ""
    image: str = ""

    def price_label(self) -> str:
        from bot.utils.text import format_price

        return format_price(
            self.price,
            free_label=content.text("catalog.price_free"),
            unknown_label=content.text("catalog.price_unknown"),
            toman_template=content.text("catalog.price_toman"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CatalogSnapshot:
    items: list[Product] = field(default_factory=list)
    source: str = "none"  # live | cache | seed | none
    fetched_at: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.items)

    @property
    def stale(self) -> bool:
        return self.source in {"cache", "seed"}

    def counts(self) -> dict[str, int]:
        out = {TYPE_COURSE: 0, TYPE_BOOK: 0, TYPE_NOTE: 0}
        for item in self.items:
            out[item.type] = out.get(item.type, 0) + 1
        return out


# ---------------------------------------------------------------------------
# normalisation helpers
# ---------------------------------------------------------------------------
def _first(row: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def parse_grade(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = int(value)
        return number if 9 <= number <= 12 else None
    text_value = to_en_digits(str(value))
    # longest first: "دوازدهم" contains "دهم", "یازدهم" contains "دهم"
    for word, number in sorted(_GRADE_WORDS.items(), key=lambda kv: -len(kv[0])):
        if word in text_value:
            return number
    digits = "".join(ch for ch in text_value if ch.isdigit())
    if digits:
        try:
            number = int(digits[-2:]) if len(digits) >= 2 else int(digits)
        except ValueError:
            return None
        if 9 <= number <= 12:
            return number
    return None


def parse_field(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip().lower()
    if not text_value:
        return None
    if "تجرب" in text_value or "experimental" in text_value or text_value in {"tajrobi", "sci"}:
        return "tajrobi"
    if "انسان" in text_value or "humanities" in text_value or text_value == "ensani":
        return "ensani"
    if "ریاض" in text_value or "math" in text_value or text_value in {"riazi", "riyazi"}:
        return "riazi"
    return None


def parse_price(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = "".join(ch for ch in to_en_digits(str(value)) if ch.isdigit())
    return int(digits) if digits else None


def detect_type(row: dict[str, Any], fallback: str, type_column: str = "type") -> str:
    raw = row.get(type_column) or row.get("category") or row.get("kind")
    haystacks = [str(raw or "").lower()]
    title = str(_first(row, _TITLE_KEYS) or "")
    haystacks.append(title.lower())
    for product_type, hints in _TYPE_HINTS.items():
        for hint in hints:
            if hint in haystacks[0]:
                return product_type
    for product_type in (TYPE_BOOK, TYPE_NOTE):
        for hint in _TYPE_HINTS[product_type]:
            if title.startswith(hint):
                return product_type
    return fallback


def normalize_row(
    row: dict[str, Any],
    fallback_type: str,
    *,
    site_base: str = content.SITE_URL,
    type_column: str = "type",
) -> Product | None:
    title = _first(row, _TITLE_KEYS)
    if not title:
        return None

    active = _first(row, _ACTIVE_KEYS)
    if isinstance(active, bool) and active is False:
        return None
    if isinstance(active, str) and active.lower() in {"false", "0", "draft", "disabled"}:
        return None

    identifier = str(_first(row, ("id", "uuid", "slug", "code")) or title)
    url = row.get("url") or row.get("link") or f"{site_base}/courses-detail?id={identifier}"
    image = _first(row, _IMAGE_KEYS) or ""

    return Product(
        id=identifier,
        type=detect_type(row, fallback_type, type_column),
        title=str(title).strip(),
        description=str(_first(row, _DESC_KEYS) or "").strip(),
        price=parse_price(_first(row, _PRICE_KEYS)),
        grade=parse_grade(_first(row, _GRADE_KEYS)),
        field=parse_field(_first(row, _FIELD_KEYS)),
        url=str(url),
        image=str(image),
    )


# ---------------------------------------------------------------------------
# service
# ---------------------------------------------------------------------------
class CatalogService:
    def __init__(self, cfg: Settings | None = None) -> None:
        self.settings = cfg or default_settings
        self._lock = threading.RLock()
        self._snapshot: CatalogSnapshot | None = None
        self._last_error: str | None = None
        self._last_attempt: float = 0.0

    # -- public API ------------------------------------------------------
    def get(self, *, force: bool = False) -> CatalogSnapshot:
        """Return the catalog, refreshing from Supabase when the cache expired."""
        with self._lock:
            snapshot = self._snapshot
            fresh = (
                snapshot is not None
                and snapshot.source == "live"
                and (time.time() - snapshot.fetched_at) < self.settings.catalog_ttl
            )
            if fresh and not force:
                return snapshot

            if self.settings.supabase_configured:
                try:
                    items = self._fetch_live()
                    if items:
                        self._snapshot = CatalogSnapshot(items, "live", time.time())
                        self._last_error = None
                        self._write_cache(self._snapshot)
                        return self._snapshot
                    self._last_error = "Supabase returned zero rows"
                except Exception as exc:  # noqa: BLE001 - reported to admin panel
                    self._last_error = f"{type(exc).__name__}: {exc}"
                    logger.warning("catalog: live fetch failed: %s", self._last_error)
            else:
                self._last_error = "SUPABASE_ANON_KEY/SUPABASE_URL تنظیم نشده است"

            if snapshot is not None and snapshot.items:
                snapshot.error = self._last_error
                return snapshot

            fallback = self._load_cache() or self._load_seed()
            fallback.error = self._last_error
            self._snapshot = fallback
            return fallback

    async def get_async(self, *, force: bool = False) -> CatalogSnapshot:
        import asyncio

        return await asyncio.to_thread(self.get, force=force)

    def invalidate(self) -> None:
        with self._lock:
            self._snapshot = None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    # -- filtering -------------------------------------------------------
    @staticmethod
    def filter(
        items: Iterable[Product],
        type_code: str,
        grade_code: str = C.GRADE_ALL,
        field_code: str = C.FIELD_ALL,
    ) -> list[Product]:
        wanted_type = C.TYPE_SLUGS.get(type_code, TYPE_COURSE)
        wanted_grade = None if grade_code in (C.GRADE_ALL, None) else int(grade_code)
        wanted_field = (
            C.FIELD_SLUGS.get(field_code) if field_code not in (C.FIELD_ALL, None) else None
        )

        out: list[Product] = []
        for item in items:
            if item.type != wanted_type:
                continue
            if wanted_grade is not None and item.grade != wanted_grade:
                continue
            # Items without a field are shown under every field (the website
            # treats "no field" as "all fields"); a different field is skipped.
            if wanted_field is not None and item.field not in (None, wanted_field):
                continue
            out.append(item)
        out.sort(key=lambda p: ((p.grade or 99), p.title))
        return out

    # -- internals -------------------------------------------------------
    def _fetch_live(self) -> list[Product]:
        cfg = self.settings
        products: list[Product] = []
        if cfg.single_table:
            rows = self._request(cfg.single_table)
            for row in rows:
                item = normalize_row(
                    row, TYPE_COURSE, site_base=cfg.site_base_url, type_column=cfg.type_column
                )
                if item:
                    products.append(item)
            return products

        for table, fallback_type in (
            (cfg.table_courses, TYPE_COURSE),
            (cfg.table_books, TYPE_BOOK),
            (cfg.table_notes, TYPE_NOTE),
        ):
            if not table:
                continue
            try:
                rows = self._request(table)
            except urllib.error.HTTPError as exc:
                if exc.code in (404, 400):  # table does not exist in this project
                    logger.warning("catalog: table %s not available (HTTP %s)", table, exc.code)
                    continue
                raise
            for row in rows:
                item = normalize_row(
                    row, fallback_type, site_base=cfg.site_base_url, type_column=cfg.type_column
                )
                if item:
                    products.append(item)
        return products

    def _request(self, table: str, limit: int = 500) -> list[dict[str, Any]]:
        cfg = self.settings
        query = urllib.parse.urlencode({"select": "*", "limit": str(limit)})
        url = f"{cfg.supabase_url}/rest/v1/{urllib.parse.quote(table)}?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "apikey": cfg.supabase_anon_key,
                "Authorization": f"Bearer {cfg.supabase_anon_key}",
                "Accept": "application/json",
                "User-Agent": "azizi-telegram-bot/1.0",
            },
        )
        context = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=15, context=context) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, list) else []

    def _write_cache(self, snapshot: CatalogSnapshot) -> None:
        try:
            self.settings.ensure_dirs()
            self.settings.catalog_cache_path.write_text(
                json.dumps(
                    {
                        "fetched_at": snapshot.fetched_at,
                        "items": [item.to_dict() for item in snapshot.items],
                    },
                    ensure_ascii=False,
                    indent=1,
                ),
                encoding="utf-8",
            )
        except OSError as exc:  # pragma: no cover
            logger.warning("catalog: cannot write cache: %s", exc)

    def _load_cache(self) -> CatalogSnapshot | None:
        path = self.settings.catalog_cache_path
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            items = [Product(**row) for row in payload.get("items", [])]
            if not items:
                return None
            return CatalogSnapshot(items, "cache", float(payload.get("fetched_at", 0)))
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("catalog: cannot read cache: %s", exc)
            return None

    def _load_seed(self) -> CatalogSnapshot:
        try:
            payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
            items = [Product(**row) for row in payload.get("items", [])]
            return CatalogSnapshot(items, "seed", 0.0)
        except (OSError, ValueError, TypeError) as exc:
            logger.error("catalog: seed snapshot unreadable: %s", exc)
            return CatalogSnapshot([], "none", 0.0, str(exc))


_service: CatalogService | None = None


def get_catalog() -> CatalogService:
    global _service
    if _service is None:
        _service = CatalogService()
    return _service


def set_catalog(service: CatalogService | None) -> None:
    """Test/preview hook."""
    global _service
    _service = service
