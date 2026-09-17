#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""recipe_runner.py — исполнитель yaml-рецептов для локального оркестратора.

Использование:
  python scripts/recipe_runner.py recipes/qwen_coder_hello.yaml

Каждый шаг выполняется через CDP (Playwright); GUI-Owl — для vision-проверок
и locate, когда DOM-селектор не задан или не работает.
"""
import argparse
import json
import re
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

sys.path.insert(0, str(Path(__file__).parent))
import owl_client  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_PORT = 9222
LOG_DIR = Path(r"D:\ai-hub\logs\recipe_runs")
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _log(recipe_name, event, **kwargs):
    entry = {"t": _now(), "recipe": recipe_name, "event": event, **kwargs}
    print(json.dumps(entry, ensure_ascii=False))
    return entry


def _report_path(recipe_name):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return LOG_DIR / f"{recipe_name}_{ts}.json"


def _connect(profile):
    port = BASE_PORT + profile - 1
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    return p, browser


def _cdp_alive(port):
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/version", timeout=3) as r:
            return json.loads(r.read().decode("utf-8")).get("Browser", "")
    except Exception:
        return ""


def ensure_browser(profile, recipe_name=""):
    """Шаг 0: проверить CDP-порт, при необходимости запустить Chrome.

    Возвращает (ok, info). info содержит версию браузера и список вкладок.
    """
    port = BASE_PORT + profile - 1
    ver = _cdp_alive(port)
    started = False
    if not ver:
        _log(recipe_name, "browser_start", profile=profile, port=port)
        launcher = Path(__file__).parent / "chrome-profile-launcher.py"
        subprocess.run([sys.executable, str(launcher), "start", str(profile)],
                       capture_output=True, timeout=120)
        for _ in range(30):
            ver = _cdp_alive(port)
            if ver:
                started = True
                break
            time.sleep(1)
        if not ver:
            return False, {"error": f"CDP порт {port} не ожил после запуска"}
    # собрать список вкладок
    tabs = []
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/list", timeout=5) as r:
            for t in json.loads(r.read().decode("utf-8")):
                if t.get("type") == "page":
                    tabs.append({"title": t.get("title", ""), "url": t.get("url", "")})
    except Exception:
        pass
    info = {"browser": ver, "started": started, "tabs": tabs}
    _log(recipe_name, "browser_ready", profile=profile, **info)
    return True, info


def _tab_activity(page, interval=2.0):
    """Сравнить innerText сейчас и через interval секунд.

    Возвращает (active, delta). active=True — текст меняется (вкладка «живая»).
    """
    try:
        t1 = page.evaluate("document.body.innerText.length||0")
        time.sleep(interval)
        t2 = page.evaluate("document.body.innerText.length||0")
        return (t1 != t2), t2 - t1
    except Exception:
        return False, 0


REGISTRY_PATH = LOG_DIR / "tabs_registry.json"


def load_registry():
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"tabs": []}


def save_registry(reg):
    REGISTRY_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=2),
                             encoding="utf-8")


def register_tab(url, meta):
    reg = load_registry()
    rec = {
        "url": url,
        "task": meta.get("task", ""),
        "branch": meta.get("branch", ""),
        "stream": meta.get("stream", ""),
        "profile": meta.get("profile", 1),
        "created_at": _now(),
        "expect_response_after": meta.get("expect_response_after", ""),
        "status": "open",
        "closed_at": None,
    }
    reg["tabs"].append(rec)
    save_registry(reg)
    return rec


def close_tab_record(url):
    reg = load_registry()
    changed = False
    for rec in reg.get("tabs", []):
        if rec.get("url") == url and rec.get("status") == "open":
            rec["status"] = "closed"
            rec["closed_at"] = _now()
            changed = True
    if changed:
        save_registry(reg)


def registry_report(inventory):
    """Сверить инвентаризацию с реестром. Вернуть строки отчёта."""
    reg = load_registry()
    open_records = [r for r in reg.get("tabs", []) if r.get("status") == "open"]
    open_urls = {r.get("url") for r in open_records}
    lines = []
    for prof in inventory.get("profiles", []):
        p = prof.get("profile")
        for tab in prof.get("tabs", []):
            url = tab.get("url", "")
            rec = next((r for r in open_records if r.get("url") == url), None)
            if rec:
                lines.append(
                    f"p{p}: {url} — задача «{rec.get('task', '')}», "
                    f"ветка {rec.get('branch', '')}, "
                    f"ждать ответ не ранее {rec.get('expect_response_after', '')}")
            else:
                lines.append(f"p{p}: {url} — задача неизвестна (нет записи)")
    # записи в реестре, но вкладка уже закрыта
    live_urls = set()
    for prof in inventory.get("profiles", []):
        for tab in prof.get("tabs", []):
            live_urls.add(tab.get("url", ""))
    for rec in open_records:
        if rec.get("url") not in live_urls:
            lines.append(f"запись висячая: {rec.get('url')} — задача «{rec.get('task', '')}»")
    return lines


def inventory_profiles(max_profile=10, recipe_name="", check_activity=False):
    """Собрать полную инвентаризацию живых Chrome-профилей.

    Для каждого живого порта: версия браузера, вкладки (title, url, status,
    visibility), активная вкладка, опционально детект занятости.
    """
    inventory = {"generated_at": _now(), "profiles": []}
    for profile in range(1, max_profile + 1):
        port = BASE_PORT + profile - 1
        ver = _cdp_alive(port)
        if not ver:
            continue
        prof = {"profile": profile, "port": port, "browser": ver, "tabs": []}
        try:
            p, browser = _connect(profile)
            try:
                ctx = browser.contexts[0]
                for page in ctx.pages:
                    if page.is_closed():
                        continue
                    tab = {
                        "url": page.url,
                        "title": page.title(),
                        "status": "loading",
                        "visible": False,
                    }
                    try:
                        tab["status"] = page.evaluate("document.readyState")
                        tab["visible"] = page.evaluate(
                            "document.visibilityState === 'visible'")
                        if check_activity and tab["visible"]:
                            active, delta = _tab_activity(page, interval=2.0)
                            tab["active"] = active
                            tab["text_delta"] = delta
                    except Exception:
                        pass
                    prof["tabs"].append(tab)
            finally:
                browser.close()
                p.stop()
        except Exception as e:
            prof["error"] = str(e)[:120]
        inventory["profiles"].append(prof)
    path = LOG_DIR / f"{recipe_name or 'inventory'}_env.json"
    path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    _log(recipe_name, "inventory_saved", path=str(path),
         profiles=len(inventory["profiles"]))
    return inventory


def _get_page(browser, prefer_url=None):
    """Вернуть (page, created). Существующие вкладки не закрываем.

    Сначала ищем точное совпадение URL (главная страница), потом
    вхождение host (глубокие пути, например /c/<uuid>).
    """
    ctx = browser.contexts[0]
    if prefer_url:
        norm = prefer_url.rstrip("/")
        for page in ctx.pages:
            if page.url.rstrip("/") == norm and not page.is_closed():
                page.bring_to_front()
                return page, False
        # host-match только для deep-link (URL с путём); иначе — новая вкладка
        from urllib.parse import urlparse
        has_path = urlparse(prefer_url).path not in ("", "/")
        if has_path:
            target_host = prefer_url.split("//")[-1].split("/")[0]
            for page in ctx.pages:
                if target_host in page.url and not page.is_closed():
                    page.bring_to_front()
                    return page, False
    page = ctx.new_page()
    page.bring_to_front()
    return page, True


def _screenshot_bytes(page):
    return page.screenshot()


def _vision_locate(page, label):
    data = _screenshot_bytes(page)
    return owl_client.locate(data, label)


def _vision_describe(page, question):
    data = _screenshot_bytes(page)
    return owl_client.describe(data, question)


def _click(page, step):
    sel = step.get("selector")
    label = step.get("label")
    if sel:
        try:
            page.click(sel, timeout=10000)
            return True, f"dom_click {sel}"
        except Exception as e:
            if not label:
                return False, f"selector failed and no vision label: {e}"
    if label:
        xy = _vision_locate(page, label)
        if xy:
            page.mouse.click(xy[0], xy[1])
            return True, f"vision_click {label} at {xy}"
        return False, f"vision locate failed for: {label}"
    return False, "no selector or label"


def _fill(page, step):
    sel = step["selector"]
    text = step["text"]
    try:
        page.fill(sel, text, timeout=10000)
        return True, f"filled {sel}"
    except Exception as e:
        return False, f"fill failed: {e}"


SEND_BTN = ".code-agent-input-send"


def _press_send(page, sel):
    """Отправить: клик по кнопке .code-agent-input-send, fallback Enter.

    Кнопка кликабельна только при наличии текста; человеческий Enter
    и CDP-Enter работают нестабильно — кнопка надёжнее (2026-09-17).
    """
    try:
        btn = page.locator(f"{SEND_BTN}:not(.code-agent-input-send-disable)")
        if btn.count() > 0:
            btn.first.click(timeout=3000)
            return True, "click send button"
    except Exception:
        pass
    try:
        page.keyboard.press("Enter")
        return True, "press Enter"
    except Exception as e:
        return False, f"send failed: {e}"


def _verify_sent_vision(page):
    """Проверка зрением: поле ввода опустело после отправки?

    Грабла 2026-09-17: клик кнопки «срабатывал», но текст оставался
    в поле. Визуальная проверка обязательна до достижения стабильности.
    """
    try:
        png = page.screenshot()
        ans = owl_client.describe(
            png, "Is the chat input textarea at the bottom of the screen "
                 "empty now? Answer yes or no.").lower()
        return "yes" in ans
    except Exception:
        return True  # при ошибке зрения не блокируем отправку


def _submit_with_retry(page, step, recipe, state):
    """Отправка с ретраями: ждём редиректа wait_path, при неудаче — повтор.

    Текст для повторного ввода берётся из text_key (state) или text.
    verify_vision: true — после клика проверять зрением, что поле пустое.
    """
    sel = step["selector"]
    key = step.get("text_key", "")
    text = step.get("text") or state.get(key) or recipe.get(key) or ""
    text = _expand(text or "", recipe, state)
    attempts = step.get("attempts", 3)
    timeout = step.get("timeout", 30)
    wait_path = step.get("wait_path", "/c/")
    verify = step.get("verify_vision", True)
    for attempt in range(1, attempts + 1):
        ok, note = _press_send(page, sel)
        if not ok:
            return False, note
        if verify:
            page.wait_for_timeout(1500)
            if not _verify_sent_vision(page):
                # текст остался в поле — доклик кнопки (до 2 раз)
                resent = False
                for _ in range(2):
                    ok2, _ = _press_send(page, sel)
                    page.wait_for_timeout(1500)
                    if _verify_sent_vision(page):
                        resent = True
                        break
                if not resent:
                    return False, (f"попытка {attempt}: текст остался в поле "
                                   "после повторных кликов (vision)")
                note += " + vision-resent"
        t0 = time.time()
        while time.time() - t0 < timeout:
            if wait_path in page.url:
                return True, f"submit ok (попытка {attempt}, {note})"
            time.sleep(0.5)
        if attempt < attempts:
            try:
                page.fill(sel, text, timeout=10000)
                page.click(sel, timeout=5000)
            except Exception:
                pass
    return False, f"редирект в {wait_path} не случился за {attempts} попыток"


def _wait_for_text(page, step):
    text = step["text"]
    timeout = step.get("timeout", 30000)
    poll = step.get("poll_interval", 2000)
    use_vision = step.get("verify_with_vision", False)
    t0 = time.time()
    last_len = -1
    stable = 0
    while (time.time() - t0) * 1000 < timeout:
        body = (page.evaluate("document.body.innerText||''") or "").lower()
        found = text.lower() in body
        if found:
            if use_vision:
                ans = _vision_describe(page, f"Does the screen show the text '{text}'? Answer yes or no.").lower()
                if "yes" not in ans:
                    time.sleep(poll / 1000)
                    continue
            return True, f"text '{text}' found"
        # детект стабильности тоже полезен
        cur_len = len(body)
        if cur_len == last_len:
            stable += 1
        else:
            stable = 0
        last_len = cur_len
        time.sleep(poll / 1000)
    return False, f"text '{text}' not found in {timeout}ms"


def _extract(page, step):
    sel = step.get("selector")
    q = step.get("vision_question")
    key = step.get("output_key")
    val = None
    if sel:
        try:
            val = page.eval_on_selector(sel, "el => el.innerText")
        except Exception as e:
            return False, f"extract selector failed: {e}", None
    elif q:
        val = _vision_describe(page, q)
    else:
        return False, "no selector or vision_question", None
    return True, f"extracted {key}", val


def _anomaly_check(page, step):
    q = step["vision_question"]
    expected = step.get("expected", "")
    ans = _vision_describe(page, q).lower()
    ok = expected.lower() in ans
    return ok, f"anomaly_check expected={expected} got={ans}", ans


def _click_text(page, text):
    """Клик по видимому элементу, содержащему точный текст."""
    try:
        loc = page.get_by_text(text, exact=True).first
        loc.click(timeout=5000)
        return True, f"click_text '{text}'"
    except Exception as e1:
        try:
            loc = page.get_by_text(text).first
            loc.click(timeout=5000)
            return True, f"click_text (partial) '{text}'"
        except Exception as e2:
            return False, f"click_text '{text}' failed: {e2}"


def _check_absent(page, text):
    """Проверить, что текста НЕТ в видимом DOM.

    Возвращает (ok, note). ok=True — текст отсутствует (шаг пройден).
    """
    try:
        loc = page.locator(f"text={text}")
        visible_count = 0
        for i in range(min(loc.count(), 20)):
            try:
                if loc.nth(i).is_visible():
                    visible_count += 1
            except Exception:
                pass
        if visible_count == 0:
            return True, f"'{text}' absent in DOM"
        return False, f"'{text}' present in DOM ({visible_count} visible elements)"
    except Exception as e:
        return False, f"check_absent error: {e}"


BASH = r"C:\Program Files\Git\bin\bash.exe"


def _extract_dom(page, step):
    """Извлечь innerText блока по селектору → state[output_key]."""
    sel = step["selector"]
    try:
        val = page.eval_on_selector(sel, "el => el.innerText")
        return True, f"extracted dom {sel} ({len(val)} chars)", val
    except Exception as e:
        return False, f"extract_dom {sel} failed: {e}", None


def _extract_files(page, step):
    """Парсинг .code-tool-record-item → [{name, add, del}] в state."""
    sel = step.get("selector", ".code-tool-record-item")
    try:
        items = page.eval_on_selector_all(sel, """
            els => els.map(el => ({
                name: el.querySelector('.code-tool-record-item__name')?.textContent.trim() || '',
                add: el.querySelector('.code-tool-record-item__add')?.textContent.trim() || '',
                del: el.querySelector('.code-tool-record-item__del')?.textContent.trim() || '',
            })).filter(f => f.name)
        """)
        return True, f"extracted {len(items)} files", items
    except Exception as e:
        return False, f"extract_files failed: {e}", None


def _write_answer(recipe, state, name):
    """Собрать markdown-ответ субагента в LOG_DIR."""
    lines = [
        f"# Ответ субагента: {recipe.get('task', name)}",
        "",
        f"- Рецепт: `{name}` · поток: {recipe.get('stream', '')}",
        f"- Репозиторий: `{recipe.get('repo', '')}` · ветка: `{state.get('branch', '')}`",
        f"- Чат: {state.get('chat_url') or state.get('chat_url_now', '')}",
        f"- PR: {state.get('pr_url', '(не извлечён)')}",
        "",
        "## Изменённые файлы",
        "",
    ]
    for f in state.get("files", []):
        lines.append(f"- `{f['name']}` ({f['add']} / {f['del']})")
    lines += ["", "## Отчёт Coder", "", state.get("report", "(нет)"), ""]
    if state.get("run_log"):
        lines += ["", "## Лог выполнения", "", "```", state["run_log"], "```", ""]
    out = LOG_DIR / f"{name}_answer.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _count_answers(page, step):
    """Посчитать число блоков ответов → state[output_key]."""
    sel = step.get("selector", ".chat-response-message")
    try:
        n = page.evaluate(f"document.querySelectorAll('{sel}').length")
        return True, f"counted {n} answers", n
    except Exception as e:
        return False, f"count_answers failed: {e}", None


def _wait_new_answer(page, step, state):
    """Ждать НОВЫЙ ответ агента (по числу блоков), а не старый текст.

    Параметры: base_selector (блоки ответов), head_selector (статус внутри),
    timeout, poll_interval, fail_if_contains (текст служебной ошибки, напр.
    лимит токенов — при появлении: эскалация).
    """
    base = step.get("base_selector", ".chat-response-message")
    head_sel = step.get("head_selector", ".response-message-head")
    timeout = step.get("timeout", 300000)
    poll = step.get("poll_interval", 3000)
    fail_texts = step.get("fail_if_contains", [])
    if isinstance(fail_texts, str):
        fail_texts = [fail_texts]
    n_before_key = step.get("n_before_key")
    if n_before_key:
        n_before = int(state.get(n_before_key, 0))
    else:
        try:
            n_before = page.evaluate(
                f"document.querySelectorAll('{base}').length")
        except Exception:
            n_before = 0
    t0 = time.time()
    while (time.time() - t0) * 1000 < timeout:
        body = page.evaluate("document.body.innerText||''") or ""
        for ft in fail_texts:
            if ft in body:
                return False, f"случился сценарий отказа: найден текст '{ft}'"
        try:
            n = page.evaluate(
                f"document.querySelectorAll('{base}').length")
        except Exception:
            n = n_before
        if n > n_before:
            ok = page.evaluate(f"""
              (() => {{
                const els = document.querySelectorAll('{head_sel}');
                if (!els.length) return false;
                const last = els[els.length-1];
                return /завершена/i.test(last.innerText||'');
              }})()
            """)
            if ok:
                return True, f"новый ответ №{n} завершён"
        time.sleep(poll / 1000)
    return False, f"новый ответ не появился за {timeout}мс"


def _click_first_existing(page, step, recipe, state):
    """Кликнуть первую найденную кнопку из списка texts.

    Шапка чата грузится медленно (большие логи) — ждём появления
    любой из кнопок до step.wait_timeout (по умолчанию 60 с).
    """
    texts = [_expand(t, recipe, state) for t in step.get("texts", [])]
    wait_timeout = step.get("wait_timeout", 60)
    t0 = time.time()
    while True:
        for t in texts:
            ok, note = _click_text(page, t)
            if ok:
                return True, f"clicked '{t}'"
        if time.time() - t0 > wait_timeout:
            break
        time.sleep(1.5)
    return False, "ни одна из кнопок не найдена за " + \
        f"{wait_timeout}с: " + ", ".join(texts)


def _run_shell(step):
    """Выполнить shell-команду через Git Bash, stdout → state[output_key]."""
    cmd = step.get("command", "")
    try:
        r = subprocess.run([BASH, "-c", cmd], capture_output=True,
                           timeout=step.get("timeout", 60), text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return False, f"shell exit {r.returncode}: {r.stderr.strip()[:200]}", None
        out = r.stdout.strip()
        return True, f"shell ok ({len(out)} chars)", out
    except Exception as e:
        return False, f"shell error: {e}", None


def _check_filled(page, step):
    """Проверить, что поле заполнено (длина ≥ min_len). Нейтрально к тексту."""
    sel = step["selector"]
    min_len = step.get("min_len", 20)
    try:
        val = page.eval_on_selector(
            sel, "el => el.value ?? el.textContent ?? ''") or ""
        n = len(val.strip())
        if n >= min_len:
            return True, f"field filled ({n} chars)"
        return False, f"field too short ({n} < {min_len})"
    except Exception as e:
        return False, f"check_filled error: {e}"


def _check_contains(page, step):
    """Проверить, что value/innerText элемента содержит текст."""
    sel = step["selector"]
    text = step.get("text", "")
    try:
        val = page.eval_on_selector(
            sel, "el => el.value ?? el.textContent ?? ''")
        if text in val:
            return True, f"'{text}' found in {sel}"
        return False, f"'{text}' NOT found in {sel}"
    except Exception as e:
        return False, f"check_contains error: {e}"


def _expand(value, recipe, state):
    """Подставить {{key}} из полей рецепта и переменных state."""
    if not isinstance(value, str):
        return value
    def repl(m):
        key = m.group(1).strip()
        if key in state:
            return str(state[key])
        return str(recipe.get(key, m.group(0)))
    return re.sub(r"\{\{(.+?)\}\}", repl, value)


def run_recipe(path, dry_run=False, only_step=None, overrides=None):
    recipe = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if overrides:
        recipe.update(overrides)
    name = recipe["name"]
    try:
        profile = int(recipe.get("profile", 1))
    except (TypeError, ValueError):
        profile = 1
    # save_to_file: просим агента сохранить полный результат в файл репо
    # (большие артефакты чат сжимает — файл через gh api даёт полный текст)
    sf = (recipe.get("save_to_file") or "").strip()
    if sf:
        add = (f"\n\nВАЖНО: полный результат (без сжатия) сохрани в файл "
               f"{sf} в корне репозитория и включи его в коммит "
               f"(git add && git commit).")
        for k in ("task_text", "followup"):
            if recipe.get(k):
                recipe[k] = recipe[k].rstrip() + add
    steps = recipe.get("steps", [])
    state = {}
    log = []
    report = {
        "recipe": name,
        "started_at": _now(),
        "status": "running",
        "steps": [],
        "state": state,
    }

    def append(step_id, ok, note, value=None, error=None):
        item = {"t": _now(), "step": step_id, "ok": ok, "note": note}
        if value is not None:
            item["value"] = value
        if error:
            item["error"] = error
        report["steps"].append(item)
        log.append(_log(name, "step", **item))

    p, browser = None, None
    page, page_created = None, False
    try:
        if not dry_run:
            # Шаг 0: инвентаризация среды + сверка с реестром
            inventory = inventory_profiles(recipe_name=name)
            report["inventory"] = inventory
            for line in registry_report(inventory):
                _log(name, "env", note=line)
            ok, info = ensure_browser(profile, name)
            if not ok:
                report["status"] = "failed"
                report["error"] = info.get("error", "browser not ready")
                report["browser"] = info
                return 1
            report["browser"] = info
            p, browser = _connect(profile)
            # предпочитаем вкладку первого navigate
            first_url = next((s["url"] for s in steps
                              if s.get("action") == "navigate"), None)
            page, page_created = _get_page(browser, prefer_url=first_url)
            tab_registered = False
            tab_meta = {
                "task": recipe.get("task", ""),
                "branch": recipe.get("branch", ""),
                "stream": recipe.get("stream", ""),
                "profile": profile,
                "expect_response_after": recipe.get("expect_response_after", ""),
            }
        else:
            page, page_created = None, False
            tab_registered = False
            tab_meta = {}

        for step in steps:
            sid = step.get("id", "unnamed")
            if only_step and sid != only_step:
                continue
            only_if = step.get("only_if")
            if only_if and not recipe.get(only_if):
                continue  # шаг опционален, поле рецепта не задано
            action = step.get("action")
            optional = step.get("optional", False)
            # подстановка {{key}} в строковых полях шага
            step = {k: _expand(v, recipe, state) if isinstance(v, str) else v
                    for k, v in step.items()}
            try:
                if dry_run:
                    append(sid, True, f"[dry] {action}")
                    continue

                if action == "navigate":
                    page.goto(step["url"], timeout=60000, wait_until="domcontentloaded")
                    append(sid, True, f"navigated to {step['url']}")
                    if page_created and not tab_registered:
                        register_tab(page.url, tab_meta)
                        tab_registered = True
                        _log(name, "tab_registered", url=page.url)
                elif action == "fill":
                    ok, note = _fill(page, step)
                    save_key = step.get("save_text_key")
                    if ok and save_key:
                        state[save_key] = step["text"]
                    append(sid, ok, note, error=None if ok else note)
                    if not ok and not optional:
                        raise RuntimeError(note)
                elif action == "press":
                    page.keyboard.press(step["key"])
                    append(sid, True, f"pressed {step['key']}")
                elif action == "submit_with_retry":
                    ok, note = _submit_with_retry(page, step, recipe, state)
                    append(sid, ok, note, error=None if ok else note)
                    if not ok:
                        raise RuntimeError(note)
                elif action == "click":
                    ok, note = _click(page, step)
                    append(sid, ok, note, error=None if ok else note)
                    if not ok and not optional:
                        raise RuntimeError(note)
                elif action == "click_text":
                    target = _expand(step.get("text", ""), recipe, state)
                    ok, note = _click_text(page, target)
                    append(sid, ok, note, error=None if ok else note)
                    if not ok and not optional:
                        raise RuntimeError(note)
                elif action == "check_filled":
                    ok, note = _check_filled(page, step)
                    append(sid, ok, note, error=None if ok else note)
                    if not ok and not optional:
                        raise RuntimeError(note)
                elif action == "check_contains":
                    ok, note = _check_contains(page, step)
                    append(sid, ok, note, error=None if ok else note)
                    if not ok and not optional:
                        raise RuntimeError(note)
                elif action == "check_absent":
                    target = _expand(step.get("text", ""), recipe, state)
                    ok, note = _check_absent(page, target)
                    append(sid, ok, note, error=None if ok else note)
                    if not ok and not optional:
                        raise RuntimeError(note)
                elif action == "wait":
                    time.sleep(step.get("ms", 1000) / 1000)
                    append(sid, True, "waited")
                elif action == "wait_for_element":
                    page.wait_for_selector(step["selector"], timeout=step.get("timeout", 10000))
                    append(sid, True, f"element {step['selector']} present")
                elif action == "wait_for_text":
                    ok, note = _wait_for_text(page, step)
                    append(sid, ok, note, error=None if ok else note)
                    if not ok:
                        raise RuntimeError(note)
                elif action == "extract":
                    ok, note, val = _extract(page, step)
                    key = step.get("output_key")
                    if ok and key:
                        state[key] = val
                    append(sid, ok, note, value=val, error=None if ok else note)
                    if not ok:
                        raise RuntimeError(note)
                elif action == "count_answers":
                    ok, note, val = _count_answers(page, step)
                    if ok:
                        state[step.get("output_key", "n_answers")] = val
                    append(sid, ok, note, value=val, error=None if ok else note)
                    if not ok:
                        raise RuntimeError(note)
                elif action == "wait_new_answer":
                    ok, note = _wait_new_answer(page, step, state)
                    append(sid, ok, note, error=None if ok else note)
                    if not ok:
                        raise RuntimeError(note)
                elif action == "click_first_existing":
                    ok, note = _click_first_existing(page, step, recipe, state)
                    append(sid, ok, note, error=None if ok else note)
                    if not ok:
                        raise RuntimeError(note)
                elif action == "extract_dom":
                    ok, note, val = _extract_dom(page, step)
                    key = step.get("output_key")
                    if ok and key:
                        state[key] = val
                    append(sid, ok, note, value=(val[:100] if isinstance(val, str) else val),
                           error=None if ok else note)
                    if not ok:
                        raise RuntimeError(note)
                elif action == "extract_files":
                    ok, note, val = _extract_files(page, step)
                    if ok:
                        state[step.get("output_key", "files")] = val
                    append(sid, ok, note, value=val, error=None if ok else note)
                    if not ok:
                        raise RuntimeError(note)
                elif action == "shell":
                    cmd = _expand(step.get("command", ""), recipe, state)
                    ok, note, val = _run_shell({**step, "command": cmd})
                    key = step.get("output_key")
                    if ok and key:
                        state[key] = val
                    append(sid, ok, note, value=val, error=None if ok else note)
                    if not ok:
                        raise RuntimeError(note)
                elif action == "save_url":
                    key = step.get("output_key", "url")
                    wait_part = step.get("wait_contains")
                    if wait_part:
                        t0 = time.time()
                        while wait_part not in page.url:
                            if time.time() - t0 > step.get("timeout", 30):
                                raise RuntimeError(
                                    f"url не содержит '{wait_part}' за {step.get('timeout', 30)}с")
                            time.sleep(0.5)
                    state[key] = page.url
                    append(sid, True, f"saved url → {key}", value=page.url)
                elif action == "anomaly_check":
                    ok, note, ans = _anomaly_check(page, step)
                    append(sid, ok, note, value=ans, error=None if ok else note)
                    if not ok and not optional:
                        raise RuntimeError(note)
                else:
                    append(sid, False, f"unknown action: {action}")
                    raise RuntimeError(f"unknown action: {action}")
            except Exception as e:
                tb = traceback.format_exc()
                append(sid, False, str(e), error=tb)
                report["status"] = "failed"
                report["error"] = str(e)
                report["traceback"] = tb
                break
        else:
            report["status"] = "done"
            try:
                ans = _write_answer(recipe, state, name)
                report["answer_file"] = str(ans)
                _log(name, "answer_saved", path=str(ans))
            except Exception as e:
                _log(name, "answer_save_failed", error=str(e)[:120])
    except Exception as e:
        tb = traceback.format_exc()
        report["status"] = "failed"
        report["error"] = str(e)
        report["traceback"] = tb
    finally:
        report["finished_at"] = _now()
        out = _report_path(name)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if page_created and page and not page.is_closed():
            try:
                url = page.url
                page.close()
                close_tab_record(url)
            except Exception:
                pass
        if browser:
            browser.close()
        if p:
            p.stop()
        _log(name, "report_saved", path=str(out), status=report["status"])
    return 0 if report["status"] == "done" else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recipe", nargs="?", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--step", default=None,
                    help="выполнить только один шаг по id (микрошаг)")
    ap.add_argument("--inventory", action="store_true",
                    help="только собрать инвентаризацию профилей")
    ap.add_argument("--activity", action="store_true",
                    help="при инвентаризации проверять активность вкладок")
    ap.add_argument("--set", dest="sets", action="append", default=[],
                    metavar="KEY=VALUE",
                    help="переопределить поле рецепта (можно несколько)")
    a = ap.parse_args()
    if a.inventory:
        inv = inventory_profiles(recipe_name="standalone",
                                 check_activity=a.activity)
        print(json.dumps(inv, ensure_ascii=False, indent=2))
        return 0
    if not a.recipe:
        ap.error("укажите файл рецепта или --inventory")
    overrides = {}
    for kv in a.sets:
        if "=" in kv:
            k, v = kv.split("=", 1)
            overrides[k] = v
    return run_recipe(a.recipe, dry_run=a.dry_run, only_step=a.step,
                      overrides=overrides or None)


if __name__ == "__main__":
    sys.exit(main())
