#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SnapSage: локальное зрение для оркестратора (Этап 1, тема 5).

Операции:
  locate   — «найди элемент»: вход PNG + цель, выход JSON {"xy":[x,y]}
  describe — «что на экране»: вход PNG + вопрос, выход JSON {"state":"..."}

Использование:
  python snap.py locate <image.png> "<цель, англ>" [--model M] [--raw]
  python snap.py describe <image.png> "<вопрос>" [--model M]

Контракт вывода (экономи-док §9.1): оркестратор никогда не видит
изображение — только готовую строку. Модель EN-only: цели и вопросы
подавать на английском.
"""
import argparse
import base64
import json
import re
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import urllib.request

OLLAMA = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "hf.co/bartowski/UI-TARS-2B-SFT-GGUF:Q4_K_M"

LOCATE_TMPL = (
    "Locate the element: {target}. "
    "Answer with a single action in the exact form click(x, y), where "
    "x and y are integers from 0 to 1000 normalized to the image size."
)
DESCRIBE_TMPL = (
    "Describe the screen state relevant to this question in one short "
    "sentence (max 30 words). Question: {q}\n"
    'Answer as JSON {{"state": "..."}}.'
)


def call_model(model, prompt, image_b64, num_predict):
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        # grammar-режим: движок генерирует только валидный JSON
        # (лечит битый синтаксис/выдуманные ключи у мелких моделей)
        "format": "json",
        "options": {"temperature": 0, "num_predict": num_predict},
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data.get("response", "").strip()


def parse_locate(text):
    m = re.search(r"click\(\s*(\d{1,4})\s*[,;]\s*(\d{1,4})\s*\)", text)
    if not m:
        m = re.search(r"\[?\s*(\d{1,4})\s*[,;]\s*(\d{1,4})\s*\]?", text)
    if m:
        return {"xy": [int(m.group(1)), int(m.group(2))], "conf": None,
                "raw": text[:120]}
    return {"xy": None, "conf": None, "raw": text[:200]}


def parse_describe(text):
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            return {"state": str(d.get("state", ""))[:300], "raw": text[:120]}
        except json.JSONDecodeError:
            pass
    return {"state": text[:300], "raw": text[:120]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("op", choices=["locate", "describe"])
    ap.add_argument("image")
    ap.add_argument("target")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--raw", action="store_true")
    a = ap.parse_args()

    with open(a.image, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    if a.op == "locate":
        prompt = LOCATE_TMPL.format(target=a.target)
        out = call_model(a.model, prompt, b64, 48)
        res = parse_locate(out)
    else:
        prompt = DESCRIBE_TMPL.format(q=a.target)
        out = call_model(a.model, prompt, b64, 96)
        res = parse_describe(out)

    res["model"] = a.model
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
