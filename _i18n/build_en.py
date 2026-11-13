#!/usr/bin/env python3
"""Збирає англійські сторінки за словником en.json:
  index.html   → en.html
  privacy.html → privacy-en.html

Запуск із папки сайту:  python3 _i18n/build_en.py
Після будь-якої правки index.html або privacy.html скрипт треба запустити знову.
Якщо на сторінці з’явився текст без перекладу, скрипт виведе його й не запише жодної сторінки.

Словник:
  raw      — точні заміни у вихідному HTML лендингу до перекладу (атрибут lang, перемикач, посилання, склеєні рядки JS);
  raw_privacy — те саме для сторінки політики;
  text     — переклад тексту: ключ записано без &nbsp; і переносів, як його бачить читач;
  patterns — шаблони для однотипних підписів з назвою бренду (регулярний вираз → заміна).
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = [("index.html", "en.html", "raw"), ("privacy.html", "privacy-en.html", "raw_privacy")]
DICT = Path(__file__).resolve().parent / "en.json"

CYR = re.compile(r"[А-Яа-яІіЇїЄєҐґ]")
ATTRS = ("aria-label", "placeholder", "alt", "title", "data-tip", "content", "value")


def norm(s):
    s = html.unescape(s).replace("\xa0", " ").replace("\xad", "")
    return " ".join(s.split())


def build(src_name, raw, text, patterns, missing):
    src = (ROOT / src_name).read_text(encoding="utf-8")
    for old, new in raw:
        if old not in src:
            sys.exit(f"raw: не знайдено в {src_name}:\n  {old}")
        src = src.replace(old, new)

    def tr(raw, escape):
        key = norm(raw)
        if not CYR.search(key):
            return raw
        en = text.get(key)
        if en is None:
            for pat, repl in patterns:
                if pat.fullmatch(key):
                    en = pat.sub(repl, key)
                    break
        if en is None:
            missing.append(key)
            return raw
        lead = raw[: len(raw) - len(raw.lstrip())]
        tail = raw[len(raw.rstrip()):]
        return lead + escape(en) + tail

    def html_part(part):
        part = re.sub(r"<!--.*?-->", lambda m: m.group(0).replace(">", "\0"), part, flags=re.S)
        part = re.sub(r">([^<]+)<", lambda m: ">" + tr(m.group(1), lambda t: html.escape(t, quote=False)) + "<", part)
        attr_re = r'\b(%s)="([^"]*)"' % "|".join(ATTRS)
        part = re.sub(attr_re, lambda m: f'{m.group(1)}="{tr(m.group(2), html.escape)}"', part)
        return part.replace("\0", ">")

    def js_part(part):
        def lit(m):
            q, body = m.group(1), m.group(2)
            new = tr(body, lambda t: t.replace("\\", "\\\\").replace(q, "\\" + q))
            return q + new + q
        return re.sub(r"(['`])((?:\\.|(?!\1).)*?)\1", lit, part)

    out = []
    for chunk in re.split(r"(<script\b.*?</script>|<style\b.*?</style>)", src, flags=re.S):
        if chunk.startswith("<script"):
            out.append(js_part(chunk))
        elif chunk.startswith("<style"):
            out.append(chunk)
        else:
            out.append(html_part(chunk))
    return "".join(out)


def main():
    d = json.loads(DICT.read_text(encoding="utf-8"))
    text = {norm(k): v for k, v in d["text"].items()}
    patterns = [(re.compile(p), r) for p, r in d.get("patterns", [])]
    missing = []
    built = [(out, build(src, d[raw], text, patterns, missing)) for src, out, raw in PAGES]
    if missing:
        print("Немає перекладу для:", *sorted(set(missing)), sep="\n  ")
        sys.exit(1)
    for out, html_text in built:
        (ROOT / out).write_text(html_text, encoding="utf-8")
        print(f"Готово: {out}")


if __name__ == "__main__":
    main()
