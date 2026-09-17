#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""trace_recorder.py — запись и воспроизведение золотых траекторий CDP.

Формат: JSONL с таймстампами, действиями и скриншотами.
Использование:
  python trace_recorder.py record --profile 1 --name deepseek_hello
  python trace_recorder.py replay D:\ai-hub\logs\traces\deepseek_hello.jsonl
  python trace_recorder.py playwright-trace --profile 1 --name qwen_research
"""
import argparse
import base64
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_PORT = 9222
TRACE_DIR = Path(r"D:\ai-hub\logs\traces")
TRACE_DIR.mkdir(parents=True, exist_ok=True)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _trace_path(name):
    return TRACE_DIR / f"{name}.jsonl"


def _screenshot_b64(page):
    return base64.b64encode(page.screenshot()).decode("ascii")


def _connect(profile):
    port = BASE_PORT + profile - 1
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    return p, browser


def record(profile, name, stop_after=None):
    """Интерактивная запись: фиксирует действия, переданные через stdin.

    Каждая строка stdin — JSON-действие:
      {"op":"navigate","url":"https://chat.deepseek.com"}
      {"op":"click","selector":".ds-button--primary"}
      {"op":"fill","selector":"textarea","text":"hello"}
      {"op":"press","key":"Enter"}
      {"op":"snapshot"}
      {"op":"stop"}
    """
    p, browser = _connect(profile)
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.bring_to_front()

    path = _trace_path(name)
    fh = path.open("w", encoding="utf-8")
    meta = {"t": _now(), "op": "meta", "profile": profile, "name": name,
            "viewport": page.viewport_size}
    fh.write(json.dumps(meta, ensure_ascii=False) + "\n")
    fh.flush()

    def write_event(ev):
        ev["t"] = _now()
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
        fh.flush()

    def on_request(req):
        write_event({"op": "network", "method": req.method, "url": req.url})

    page.on("request", on_request)

    print(f"Recording to {path}")
    print("Paste JSON actions (one per line). End with {\"op\":\"stop\"}")

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                action = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"bad json: {e}")
                continue

            op = action.get("op")
            if op == "stop":
                break

            # screenshot before
            action["screenshot_before"] = _screenshot_b64(page)
            t0 = time.time()

            try:
                if op == "navigate":
                    page.goto(action["url"], timeout=60000)
                elif op == "click":
                    if "x" in action and "y" in action:
                        page.mouse.click(action["x"], action["y"])
                    else:
                        page.click(action["selector"], timeout=10000)
                elif op == "fill":
                    page.fill(action["selector"], action["text"], timeout=10000)
                elif op == "press":
                    page.keyboard.press(action["key"])
                elif op == "wait":
                    time.sleep(action.get("ms", 1000) / 1000)
                elif op == "snapshot":
                    pass
                else:
                    print(f"unknown op: {op}")
                    continue
                action["ok"] = True
            except Exception as e:
                action["ok"] = False
                action["error"] = str(e)[:200]

            action["duration_ms"] = round((time.time() - t0) * 1000)
            action["screenshot_after"] = _screenshot_b64(page)
            write_event(action)

            if stop_after and action.get("n", 0) >= stop_after:
                break
    finally:
        fh.close()
        page.close()
        browser.close()
        p.stop()
    print(f"Saved {path}")


def replay(trace_file, dry_run=False):
    """Воспроизвести траекторию из JSONL.

    Первая строка — meta с profile. Остальные — действия.
    """
    trace_file = Path(trace_file)
    lines = trace_file.read_text(encoding="utf-8").splitlines()
    if not lines:
        print("empty trace")
        return 1

    meta = json.loads(lines[0])
    profile = meta.get("profile", 1)
    p, browser = _connect(profile)
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.bring_to_front()

    results = []
    try:
        for raw in lines[1:]:
            action = json.loads(raw)
            if action.get("op") in ("meta", "network"):
                continue
            if dry_run:
                short = {k: v for k, v in action.items()
                         if k not in ("screenshot_before", "screenshot_after")}
                print(f"[dry] {action.get('op')}: {short}")
                continue
            t0 = time.time()
            try:
                op = action["op"]
                if op == "navigate":
                    page.goto(action["url"], timeout=60000)
                elif op == "click":
                    if "x" in action and "y" in action:
                        page.mouse.click(action["x"], action["y"])
                    else:
                        page.click(action["selector"], timeout=10000)
                elif op == "fill":
                    page.fill(action["selector"], action["text"], timeout=10000)
                elif op == "press":
                    page.keyboard.press(action["key"])
                elif op == "wait":
                    time.sleep(action.get("ms", 1000) / 1000)
                results.append({"op": op, "ok": True,
                                "ms": round((time.time() - t0) * 1000)})
            except Exception as e:
                results.append({"op": action.get("op"), "ok": False,
                                "error": str(e)[:200]})
                print(f"FAIL {action}: {e}")
    finally:
        page.close()
        browser.close()
        p.stop()

    ok = sum(1 for r in results if r["ok"])
    print(json.dumps({"total": len(results), "ok": ok,
                      "failed": len(results) - ok}, ensure_ascii=False))
    return 0


def playwright_trace(profile, name, url=None):
    """Записать Playwright trace (.zip) для одной сессии.

    Удобно для ручного разбора в trace.playwright.dev.
    """
    p, browser = _connect(profile)
    ctx = browser.contexts[0]
    trace_path = TRACE_DIR / f"{name}.playwright.zip"
    ctx.tracing.start(screenshots=True, snapshots=True, sources=False)
    page = ctx.new_page()
    page.bring_to_front()
    try:
        if url:
            page.goto(url, timeout=60000)
        print(f"Playwright trace recording to {trace_path}")
        print("Press Enter to stop...")
        input()
    finally:
        ctx.tracing.stop(path=str(trace_path))
        page.close()
        browser.close()
        p.stop()
    print(f"Saved {trace_path}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record")
    r.add_argument("--profile", type=int, default=1)
    r.add_argument("--name", required=True)

    rp = sub.add_parser("replay")
    rp.add_argument("trace_file")
    rp.add_argument("--dry-run", action="store_true")

    pt = sub.add_parser("playwright-trace")
    pt.add_argument("--profile", type=int, default=1)
    pt.add_argument("--name", required=True)
    pt.add_argument("--url", default=None)

    a = ap.parse_args()
    if a.cmd == "record":
        record(a.profile, a.name)
    elif a.cmd == "replay":
        return replay(a.trace_file, a.dry_run)
    elif a.cmd == "playwright-trace":
        playwright_trace(a.profile, a.name, a.url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
