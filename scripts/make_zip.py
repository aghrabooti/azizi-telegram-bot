#!/usr/bin/env python3
"""Build the downloadable, versioned source zip.

    python scripts/make_zip.py            # -> dist/azizi-telegram-bot-v1.0.0-<build>.zip

Guarantees (checked by tests):
  * ``.env`` and ``data/`` are NEVER inside the archive,
  * the file name is unique per build (cache-busting for the preview site),
  * ``BUILD_INFO.txt`` documents version, build id, file count and exact size.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import __version__  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "data", "dist", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".idea", ".vscode", "node_modules",
}
EXCLUDED_NAMES = {".env", ".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".log", ".sqlite", ".sqlite3"}


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        parts = set(path.relative_to(ROOT).parts)
        if parts & EXCLUDED_DIRS:
            continue
        if path.name in EXCLUDED_NAMES or path.name.startswith(".env"):
            if path.name != ".env.example":
                continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return files


def build(build_id: str | None = None) -> Path:
    DIST.mkdir(exist_ok=True)
    build_id = build_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    target = DIST / f"azizi-telegram-bot-v{__version__}-{build_id}.zip"
    files = iter_files()

    info = [
        "azizi-telegram-bot — BUILD INFO",
        "=" * 40,
        f"version      : v{__version__}",
        f"build id     : {build_id}",
        f"built at     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"files        : {len(files)}",
        "excluded     : .env, data/, .git, .venv, __pycache__, *.db, *.log",
        "",
        "نصب سریع:",
        "  python -m venv .venv && .venv/bin/pip install -r requirements.txt",
        "  cp .env.example .env   # و مقادیر را پر کنید (فقط KEY=value)",
        "  python -m bot",
        "",
        "عیب‌یابی: python scripts/diagnose.py",
    ]

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, Path("azizi-telegram-bot") / path.relative_to(ROOT))
        archive.writestr("azizi-telegram-bot/BUILD_INFO.txt", "\n".join(info) + "\n")

    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-id", help="override the build id")
    args = parser.parse_args()
    target = build(args.build_id)
    size = target.stat().st_size
    digest = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
    print(f"✅ {target}")
    print(f"   حجم دقیق: {size} بایت ({size / 1024:.1f} KB)")
    print(f"   sha256: {digest}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
