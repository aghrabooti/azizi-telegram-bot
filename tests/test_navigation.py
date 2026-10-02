"""Navigation: every section, Back / Main menu, expired buttons, no dead links."""

from __future__ import annotations

import pytest

from bot import constants as C
from bot.config import content
from bot.handlers import navigation as nav_handlers
from bot.handlers import start as start_handlers
from bot.services.catalog import get_catalog
from bot.services.navigation import iter_all_pages, render, render_static
from tests.fakes import callback_update, text_update


def register_phone(db, user_id: int = 500) -> None:
    db.upsert_user(user_id)
    db.set_phone(user_id, "+989121234567")


async def test_start_shows_main_menu(isolated_env, context):
    register_phone(isolated_env)
    update, _ = text_update("/start")
    await start_handlers.cmd_start(update, context)
    assert "آکادمی استاد مهدی عزیزی" in context.bot.texts[0]


@pytest.mark.parametrize(
    "callback",
    ["nav:about", "nav:social", "nav:support", "nav:help", "cat:c", "cat:b", "cat:n"],
)
async def test_every_section_renders(isolated_env, context, callback):
    register_phone(isolated_env)
    update, query = callback_update(callback)
    if callback.startswith("nav:"):
        await nav_handlers.on_nav(update, context)
    else:
        await nav_handlers.on_catalog(update, context)
    assert query.edits, f"{callback} rendered nothing"
    assert len(query.edits[0]["text"]) > 10


async def test_every_page_has_back_and_main(isolated_env):
    snapshot = get_catalog().get()
    for page in iter_all_pages(snapshot):
        if page.id == C.nav(C.PAGE_MAIN):
            continue
        callbacks = page.callbacks()
        assert C.nav(C.PAGE_MAIN) in callbacks, f"{page.id} has no main-menu button"
        assert page.parent is not None, f"{page.id} has no parent"


async def test_no_dead_buttons(isolated_env):
    """The exact assertion the preview build runs — kept in the test suite too."""
    snapshot = get_catalog().get()
    pages = {page.id: page for page in iter_all_pages(snapshot)}
    known = set(pages) | {"noop"}
    for page in pages.values():
        for callback in page.callbacks():
            assert callback in known, f"dead button {callback} on {page.id}"


async def test_callback_data_is_short_enough(isolated_env):
    snapshot = get_catalog().get()
    for page in iter_all_pages(snapshot):
        for callback in page.callbacks():
            assert len(callback.encode("utf-8")) <= 64


async def test_expired_button_tells_the_user(isolated_env, context):
    register_phone(isolated_env)
    update, query = callback_update("nav:this_page_no_longer_exists")
    await nav_handlers.on_unknown_callback(update, context)
    assert any(content.text("error.expired") == answer["text"] for answer in query.answers)
    assert context.bot.messages  # user is not left stranded: menu is re-sent


async def test_back_navigation_is_stateless(isolated_env):
    page = render("cat:c:11:r:1")
    assert page.parent == "cat:c:11"
    assert render(page.parent).parent == "cat:c"
    assert render("cat:c").parent == C.nav(C.PAGE_MAIN)


async def test_social_page_lists_the_four_official_pages(isolated_env):
    page = render_static(C.PAGE_SOCIAL)
    urls = [button.url for row in page.rows for button in row if button.url]
    assert "https://t.me/mahdiazizi_math" in urls
    assert "https://ble.ir/mahdiiazizii_math" in urls
    assert "https://www.aparat.com/mahdiazizii" in urls
    assert "https://www.instagram.com/mahdiazizi_math/" in urls


async def test_site_button_points_to_the_site(isolated_env):
    page = render_static(C.PAGE_MAIN)
    urls = [button.url for row in page.rows for button in row if button.url]
    assert content.SITE_URL in urls
