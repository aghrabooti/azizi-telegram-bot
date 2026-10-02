"""Button styling rules + the downloadable zip must never leak secrets."""

from __future__ import annotations

import zipfile

import pytest

from bot.config.settings import settings
from bot.keyboards import builder
from bot.services.catalog import get_catalog
from bot.services.navigation import iter_all_pages


def test_default_style_is_primary(monkeypatch):
    monkeypatch.setattr(settings, "button_style_mode", "auto")
    assert builder.resolve_style(None) in (None, "primary")
    if builder.SUPPORTS_BUTTON_STYLES:
        assert builder.resolve_style(None) == "primary"


def test_invalid_style_falls_back_to_primary(monkeypatch):
    monkeypatch.setattr(settings, "button_style_mode", "auto")
    # "positive"/"destructive" are a 400 from the Bot API — never send them
    for bad in ("positive", "destructive", "green", ""):
        assert builder.resolve_style(bad) in (None, "primary")


def test_style_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "button_style_mode", "off")
    assert builder.resolve_style("success") is None


def test_only_three_styles_are_used_anywhere(isolated_env):
    snapshot = get_catalog().get()
    for page in iter_all_pages(snapshot):
        for row in page.rows:
            for button in row:
                assert button.style in {"primary", "success", "danger"}


def test_button_requires_a_target():
    with pytest.raises(ValueError):
        builder.inline_button("x")


def test_too_long_callback_data_is_rejected():
    with pytest.raises(ValueError):
        builder.inline_button("x", callback_data="a" * 65)


def test_external_links_are_green(isolated_env):
    from bot import constants as C
    from bot.services.navigation import render_static

    page = render_static(C.PAGE_SOCIAL)
    for row in page.rows:
        for button in row:
            if button.url:
                assert button.style == "success"


def test_zip_excludes_env_and_data(tmp_path):
    from scripts.make_zip import build

    archive = build(build_id="test")
    try:
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
        assert not [n for n in names if n.endswith("/.env")]
        assert not [n for n in names if "/data/" in n]
        assert not [n for n in names if n.endswith(".db") or n.endswith(".log")]
        assert any(n.endswith("BUILD_INFO.txt") for n in names)
        assert any(n.endswith("requirements.txt") for n in names)
        assert any(n.endswith(".env.example") for n in names)
        assert archive.stat().st_size > 1000
    finally:
        archive.unlink(missing_ok=True)


def test_log_redaction_hides_tokens():
    from bot.utils.logging import redact

    line = "https://api.telegram.org/bot8012345678:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw/getMe"
    assert "AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" not in redact(line)
    assert "REDACTED" in redact(line)
