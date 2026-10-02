"""Shared fixtures: isolated database, isolated settings, no network."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot.config import content  # noqa: E402
from bot.config.settings import settings  # noqa: E402
from bot.services import catalog as catalog_module  # noqa: E402
from bot.services.content_store import ContentStore, set_store  # noqa: E402
from bot.services.database import Database, set_db  # noqa: E402
from tests.fakes import FakeBot, FakeContext  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Every test gets its own data dir, database and content store."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "admin_ids", (999,))
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_anon_key", "")
    monkeypatch.setattr(settings, "catalog_page_size", 6)
    monkeypatch.setattr(settings, "anon_notify", True)
    monkeypatch.setattr(settings, "anon_inbox_chat_id", "")
    monkeypatch.setattr(settings, "button_style_mode", "auto")

    db = Database(tmp_path / "test.db")
    set_db(db)
    store = ContentStore(db)
    set_store(store)

    catalog_module.set_catalog(catalog_module.CatalogService(settings))

    yield db

    content.set_override_resolver(None)
    set_db(None)
    set_store(None)
    catalog_module.set_catalog(None)
    db.close()


@pytest.fixture
def bot() -> FakeBot:
    return FakeBot()


@pytest.fixture
def context(bot) -> FakeContext:
    return FakeContext(bot)
