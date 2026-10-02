#!/usr/bin/env python3
"""Live preview server (port 8080).

    python dev/preview/server.py            # http://0.0.0.0:8080

Serves:
  /                     browser simulator of the bot, built from the real source
  /app-data.json        the generated page map (dev/preview/build.py)
  /api/files            list of source files
  /api/source?path=…    content of one source file
  /api/verify           automatic HTTP self-check (returns JSON)
  /download             versioned, cache-busting zip with BUILD_INFO.txt

Everything is served with ``Cache-Control: no-store`` and *without*
``X-Frame-Options`` so the page can be embedded in the Arena preview iframe.
"""

from __future__ import annotations

import json
import mimetypes
import sys
import threading
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PREVIEW_DIR = Path(__file__).resolve().parent
STATIC_DIR = PREVIEW_DIR / "static"
APP_DATA = STATIC_DIR / "app-data.json"

PORT = 8080
_zip_lock = threading.Lock()
_zip_path: Path | None = None


def ensure_app_data() -> dict:
    if not APP_DATA.exists():
        rebuild()
    return json.loads(APP_DATA.read_text(encoding="utf-8"))


def rebuild() -> None:
    import importlib

    module = importlib.import_module("dev.preview.build")
    importlib.reload(module)
    module.main()


def ensure_zip() -> Path:
    global _zip_path
    with _zip_lock:
        if _zip_path is None or not _zip_path.exists():
            from scripts.make_zip import build

            _zip_path = build()
        return _zip_path


def safe_source_path(relative: str) -> Path | None:
    candidate = (ROOT / relative).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    parts = set(candidate.relative_to(ROOT).parts)
    if parts & {".git", ".venv", "data", "dist", "__pycache__"}:
        return None
    if candidate.name == ".env":
        return None
    return candidate


class Handler(BaseHTTPRequestHandler):
    server_version = "AziziPreview/1.0"

    # ---------------------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str,
              extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Security-Policy", "frame-ancestors *")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, payload: object, status: int = 200) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def log_message(self, fmt: str, *args) -> None:  # quieter logs
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ---------------------------------------------------------------
    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802, C901
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._serve_static("index.html")
            return
        if path == "/app-data.json":
            if not APP_DATA.exists():
                rebuild()
            self._serve_file(APP_DATA, "application/json; charset=utf-8")
            return
        if path.startswith("/static/"):
            self._serve_static(path[len("/static/"):])
            return
        if path == "/api/files":
            self._json(ensure_app_data().get("sources", []))
            return
        if path == "/api/source":
            relative = (query.get("path") or [""])[0]
            target = safe_source_path(relative)
            if target is None:
                self._json({"error": "not found"}, 404)
                return
            self._json({
                "path": relative,
                "size": target.stat().st_size,
                "content": target.read_text(encoding="utf-8", errors="replace"),
            })
            return
        if path == "/api/rebuild":
            try:
                rebuild()
                global _zip_path
                _zip_path = None
                self._json({"ok": True, **ensure_app_data()["catalog"]})
            except BaseException as exc:  # noqa: BLE001
                self._json({"ok": False, "error": str(exc)}, 500)
            return
        if path == "/api/verify":
            self._json(self.run_verification())
            return
        if path == "/api/build-info":
            archive = ensure_zip()
            self._json({
                "name": archive.name,
                "bytes": archive.stat().st_size,
                "built_at": datetime.fromtimestamp(archive.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            })
            return
        if path == "/download":
            archive = ensure_zip()
            self._send(
                200,
                archive.read_bytes(),
                "application/zip",
                {"Content-Disposition": f'attachment; filename="{archive.name}"'},
            )
            return
        if path == "/healthz":
            self._json({"status": "ok", "pages": len(ensure_app_data().get("pages", {}))})
            return
        self._json({"error": "not found"}, 404)

    # ---------------------------------------------------------------
    def _serve_static(self, relative: str) -> None:
        target = (STATIC_DIR / relative).resolve()
        try:
            target.relative_to(STATIC_DIR)
        except ValueError:
            self._json({"error": "forbidden"}, 403)
            return
        if not target.is_file():
            self._json({"error": "not found"}, 404)
            return
        guessed = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if guessed.startswith("text/") or guessed in ("application/javascript",
                                                      "application/json"):
            guessed += "; charset=utf-8"
        self._serve_file(target, guessed)

    def _serve_file(self, target: Path, content_type: str) -> None:
        self._send(200, target.read_bytes(), content_type)

    # ---------------------------------------------------------------
    def run_verification(self) -> dict:
        base = f"http://127.0.0.1:{PORT}"
        checks: list[dict] = []

        def http(path: str) -> tuple[int, bytes]:
            request = urllib.request.Request(base + path)
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, response.read()

        def record(name: str, ok: bool, detail: str) -> None:
            checks.append({"name": name, "ok": bool(ok), "detail": detail})

        for route in ("/", "/app-data.json", "/api/files", "/healthz"):
            try:
                status, body = http(route)
                record(f"GET {route}", status == 200 and len(body) > 0,
                       f"HTTP {status} — {len(body)} بایت")
            except Exception as exc:  # noqa: BLE001
                record(f"GET {route}", False, str(exc))

        try:
            data = json.loads(APP_DATA.read_text(encoding="utf-8"))
            pages = data["pages"]
            admin = data["admin_pages"]
            actions = data["actions"]
            known = set(pages) | set(admin) | set(actions)
            dead = [
                (page_id, button["callback"])
                for page_id, page in {**pages, **admin}.items()
                for row in page["rows"]
                for button in row
                if button.get("callback") and button["callback"] not in known
            ]
            record("هیچ دکمه‌ای بدون صفحه نیست", not dead,
                   "همه‌ی callbackها صفحه دارند" if not dead else f"{len(dead)} دکمه‌ی مرده")
            record("تعداد صفحات", len(pages) > 50,
                   f"{len(pages)} صفحه‌ی کاربری + {len(admin)} صفحه‌ی ادمین")
            styles = [
                button["style"]
                for page in {**pages, **admin}.values()
                for row in page["rows"]
                for button in row
            ]
            bad = sorted({s for s in styles if s not in {"primary", "success", "danger"}})
            record("استایل دکمه‌ها معتبر است", not bad,
                   "primary/success/danger" if not bad else f"نامعتبر: {bad}")
        except Exception as exc:  # noqa: BLE001
            record("بررسی app-data.json", False, str(exc))

        try:
            import zipfile

            archive = ensure_zip()
            with zipfile.ZipFile(archive) as zf:
                names = zf.namelist()
            leaked = [n for n in names if n.endswith("/.env") or "/data/" in n]
            size = archive.stat().st_size
            record("زیپ ساخته شد", size > 0, f"{archive.name} — {size} بایت دقیق")
            record("زیپ شامل .env یا data/ نیست", not leaked,
                   "پاک است" if not leaked else f"نشتی: {leaked[:3]}")
            record("BUILD_INFO.txt داخل زیپ هست",
                   any(n.endswith("BUILD_INFO.txt") for n in names),
                   f"{len(names)} فایل در آرشیو")
        except Exception as exc:  # noqa: BLE001
            record("بررسی زیپ", False, str(exc))

        ok = all(check["ok"] for check in checks)
        return {"ok": ok, "checked_at": datetime.now().strftime("%H:%M:%S"), "checks": checks}


def main() -> int:
    rebuild()
    ensure_zip()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"🌐 preview server on http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
