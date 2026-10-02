"""Webhook security + health endpoint (no Telegram connection involved)."""

from __future__ import annotations

import io
import json

import pytest

from bot.config.settings import settings
from bot.webhook import app as webhook_module


def environ(path: str, method: str = "POST", secret: str | None = None, body: bytes = b"{}"):
    env = {
        "PATH_INFO": path,
        "REQUEST_METHOD": method,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    if secret is not None:
        env["HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN"] = secret
    return env


class Recorder:
    def __init__(self) -> None:
        self.status = ""
        self.headers: list[tuple[str, str]] = []

    def __call__(self, status, headers):
        self.status = status
        self.headers = headers


@pytest.fixture
def wsgi(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "s3cret-token")
    monkeypatch.setattr(settings, "webhook_path", "/telegram/webhook")
    # never boot a real Application in tests
    monkeypatch.setattr(webhook_module.runtime, "ensure_started", lambda: None)
    monkeypatch.setattr(webhook_module.runtime, "wait_ready", lambda timeout: False)
    return webhook_module.create_app(settings)


def test_wrong_secret_is_rejected(wsgi):
    recorder = Recorder()
    body = wsgi(environ("/telegram/webhook", secret="wrong"), recorder)
    assert recorder.status.startswith("403")
    assert b"forbidden" in b"".join(body)


def test_missing_secret_is_rejected(wsgi):
    recorder = Recorder()
    wsgi(environ("/telegram/webhook"), recorder)
    assert recorder.status.startswith("403")


def test_wrong_path_is_404(wsgi):
    recorder = Recorder()
    wsgi(environ("/wrong/path", secret="s3cret-token"), recorder)
    assert recorder.status.startswith("404")


def test_get_on_webhook_is_405(wsgi):
    recorder = Recorder()
    wsgi(environ("/telegram/webhook", method="GET", secret="s3cret-token"), recorder)
    assert recorder.status.startswith("405")


def test_healthz_reports_state_and_version(wsgi):
    recorder = Recorder()
    body = json.loads(b"".join(wsgi(environ("/healthz", method="GET"), recorder)))
    assert recorder.status.startswith("200")
    assert body["version"]
    assert body["state"] in {"idle", "starting", "ready", "init-failed"}
    assert "api_root" in body


def test_valid_secret_but_cold_runtime_returns_503(wsgi):
    recorder = Recorder()
    body = b"".join(
        wsgi(environ("/telegram/webhook", secret="s3cret-token", body=b'{"update_id":1}'),
             recorder)
    )
    assert recorder.status.startswith("503")
    assert b"state" in body


def test_valid_secret_with_ready_runtime_returns_200(monkeypatch, wsgi):
    submitted: list[dict] = []
    monkeypatch.setattr(webhook_module.runtime, "wait_ready", lambda timeout: True)
    def _submit(payload):
        submitted.append(payload)
        return True

    monkeypatch.setattr(webhook_module.runtime, "submit", _submit)
    recorder = Recorder()
    body = b"".join(
        wsgi(environ("/telegram/webhook", secret="s3cret-token", body=b'{"update_id":7}'),
             recorder)
    )
    assert recorder.status.startswith("200")
    assert submitted == [{"update_id": 7}]
    assert b'"ok":true' in body


def test_bad_json_is_400(monkeypatch, wsgi):
    monkeypatch.setattr(webhook_module.runtime, "wait_ready", lambda timeout: True)
    recorder = Recorder()
    wsgi(environ("/telegram/webhook", secret="s3cret-token", body=b"not-json"), recorder)
    assert recorder.status.startswith("400")


def test_responses_are_never_cached(wsgi):
    recorder = Recorder()
    wsgi(environ("/healthz", method="GET"), recorder)
    headers = dict(recorder.headers)
    assert headers["Cache-Control"] == "no-store"


def test_allowed_updates_contains_callback_query():
    from bot.app import ALLOWED_UPDATES

    assert "callback_query" in ALLOWED_UPDATES
