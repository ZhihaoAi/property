#!/usr/bin/env python3
"""Render-check the dashboard with Playwright CLI and save screenshots."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


BASE_DIR = Path("/Users/zhihao.ai/projects/property")
PLAYWRIGHT_BIN = Path("/Users/zhihao.ai/Library/Python/3.9/bin/playwright")
SERVER_PORT = 8765
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}/index.html"
OUTPUT_DIR = BASE_DIR / "artifacts" / "render_verify"

CHECKS = [
    {
        "name": "s2_focus",
        "tab": "s2",
        "selector": "#lv_focus_content .ai",
        "summary": "Lakeville / Lake Grande 细户型卡片",
    },
    {
        "name": "s10_pk",
        "tab": "s10",
        "selector": "#overall_projects_table tbody tr",
        "summary": "小区PK表",
    },
    {
        "name": "s12_scraped",
        "tab": "s12",
        "selector": "#scraped_projects_table tbody tr",
        "summary": "已爬数据表",
    },
]


def wait_for_server(timeout_seconds: int = 10) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(SERVER_URL, timeout=1) as response:
                if response.status == 200:
                    return
        except urllib.error.URLError as exc:
            last_error = exc
            time.sleep(0.2)
    raise RuntimeError(f"http.server did not start in time: {last_error}")


def run_check(check: dict[str, str]) -> Path:
    screenshot_path = OUTPUT_DIR / f"{check['name']}.png"
    url = f"{SERVER_URL}?tab={check['tab']}"
    cmd = [
        str(PLAYWRIGHT_BIN),
        "screenshot",
        "--browser",
        "chromium",
        "--viewport-size",
        "1440,2200",
        "--wait-for-selector",
        check["selector"],
        "--wait-for-timeout",
        "1500",
        "--timeout",
        "30000",
        "--full-page",
        url,
        str(screenshot_path),
    ]
    subprocess.run(cmd, check=True, cwd=BASE_DIR)
    if not screenshot_path.exists() or screenshot_path.stat().st_size == 0:
        raise RuntimeError(f"screenshot missing for {check['name']}")
    return screenshot_path


def ensure_prereqs() -> None:
    if not PLAYWRIGHT_BIN.exists():
        raise RuntimeError(f"playwright CLI not found: {PLAYWRIGHT_BIN}")
    if shutil.which("python3") is None:
        raise RuntimeError("python3 not found")


def main() -> int:
    ensure_prereqs()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(SERVER_PORT)],
        cwd=BASE_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        wait_for_server()
        print(f"server: {SERVER_URL}")
        print(f"output: {OUTPUT_DIR}")
        for check in CHECKS:
            screenshot_path = run_check(check)
            print(f"{check['name']}: ok -> {screenshot_path} ({check['summary']})")
        print("render verification complete")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
