#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2-MD → HTML copy page для редактора «Статья» (lane L2).

Детерминированно материализует то, что Markdown выразить не может:
  • воздух — один пустой блок `<p>&#8203;</p>` строго ПЕРЕД заголовком;
  • каждый пункт списка (`• ` / `1. `) — отдельный абзац;
  • цитата — `<blockquote>`, подпись — `<cite>` последней строкой внутри блока;
  • хэштеги — отдельный абзац.

    python3 render_l2_copy_page.py статья.md -o copy.html
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

# Подпись цитаты: обычная строка «— Автор, «Труд»»; курсивная форма — только
# ради совместимости со старыми материалами.
ATTRIBUTION_RE = re.compile(r"^(?:\*— .+\*|— .+)$")

# Воздух перед заголовком — пустой абзац. Именно U+00A0, а не U+200B: нулевой
# пробел редактор «Статья» выбрасывает как пустой текст, и воздух исчезает при
# вставке. Неразрывный пробел переживает разбор HTML и даёт ровно одну пустую строку.
AIR = "<p>\u00a0</p>"


def inline(text: str) -> str:
    """Жирный и курсив в статье разрешены (решение оператора 2026-10-22).

    `**x**` → <b>x</b>, `*x*` → <i>x</i>; остальное экранируется как есть.
    Порядок важен: сначала экранирование, потом разметка — иначе разметка
    внутри текста может быть испорчена спецсимволами.
    """
    out = html.escape(text, quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", out)


def plain(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", text)


def parse_blocks(md: str):
    blocks, cur = [], []
    for line in md.replace("\r\n", "\n").split("\n"):
        if line.strip():
            cur.append(line.rstrip())
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    return blocks


def render(md: str):
    blocks = parse_blocks(md)
    plain_blocks: list[str] = []
    # (вид, html): воздух расставляется вторым проходом, когда уже известно,
    # что стоит до блока и после него.
    items: list[tuple[str, str]] = []
    stats = {"headings": 0, "quotes": 0, "items": 0, "air": 0}

    def flush_text(buf: list[str]):
        if not buf:
            return
        text = "\n".join(buf)
        stripped = text.strip()
        kind = "connector" if stripped.endswith(":") and len(stripped) <= 120 else "paragraph"
        items.append((kind, f"<p>{inline(text)}</p>"))
        plain_blocks.append(plain(text))
        buf.clear()

    for block in blocks:
        head = block[0]

        if re.match(r"^#\s", head):
            title = head[2:].strip()
            items.append(("heading", f"<h1>{inline(title)}</h1>"))
            plain_blocks.append(plain(title))
            stats["headings"] += 1
            continue

        if re.match(r"^##\s", head):
            title = head[3:].strip()
            items.append(("heading", f"<h2>{inline(title)}</h2>"))
            plain_blocks.append(plain(title))
            stats["headings"] += 1
            continue

        if head.startswith("• ") or re.match(r"^\d+\. ", head):
            for line in block:
                if line.startswith("• ") or re.match(r"^\d+\. ", line):
                    items.append(("item", f"<p>{inline(line)}</p>"))
                    plain_blocks.append(plain(line))
                    stats["items"] += 1
            continue

        # смешанный блок: текст, цитата, подпись
        buf: list[str] = []
        i = 0
        while i < len(block):
            line = block[i]
            if line.startswith(">"):
                flush_text(buf)
                quote_lines = []
                while i < len(block) and block[i].startswith(">"):
                    quote_lines.append(block[i].lstrip("> ").strip())
                    i += 1
                # L2: подпись — последняя строка блока, внутрь <blockquote>:
                # отдельный абзац под цитатой получает блочный отступ и даёт воздух
                attr = ""
                if quote_lines and ATTRIBUTION_RE.match(quote_lines[-1]):
                    attr = plain(quote_lines.pop()).strip()
                elif i < len(block) and ATTRIBUTION_RE.match(block[i].strip()):
                    # совместимость со старой формой: подпись отдельным абзацем
                    attr = plain(block[i]).strip()
                    i += 1
                inner = "<br>".join(inline(q) for q in quote_lines)
                if attr:
                    inner += ("<br>" if inner else "") + f"<cite>{inline(attr)}</cite>"
                items.append(("quote", "<blockquote>" + inner + "</blockquote>"))
                plain_blocks.append(
                    "\n".join([plain(q) for q in quote_lines] + ([plain(attr)] if attr else [])).strip()
                )
                stats["quotes"] += 1
                continue
            if ATTRIBUTION_RE.match(line.strip()):
                flush_text(buf)
                attr = plain(line).strip()
                items.append(("attribution", f"<p>{inline(attr)}</p>"))
                plain_blocks.append(plain(attr))
                i += 1
                continue
            buf.append(line)
            i += 1
        flush_text(buf)

    out: list[str] = []
    for index, (kind, markup) in enumerate(items):
        previous = items[index - 1][0] if index else ""
        air = False
        if kind == "heading":
            air = index > 0
        elif kind == "quote":
            # воздух сверху цитаты; исключения — сразу после заголовка
            # (после заголовка воздуха нет) и после короткой связки с двоеточием
            air = previous not in ("", "heading", "connector")
        elif previous == "quote":
            # воздух снизу цитаты; перед заголовком его поставит сам заголовок
            air = kind != "heading"
        if air:
            out.append(AIR)
            stats["air"] += 1
        out.append(markup)

    return "\n".join(out), "\n\n".join(plain_blocks) + "\n", stats


TPL = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Копировать статью в «Статью»</title>
<style>
  :root{--bg:#0e1621;--card:#17212b;--text:#e9edf1;--muted:#8698a8;--accent:#3390ec;--border:#243447;--ok:#3ecf8e}
  *{box-sizing:border-box;-webkit-tap-highlight-color:rgba(51,144,236,.15)}
  html,body{margin:0}
  body{background:var(--bg);color:var(--text);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
    padding:14px 12px calc(30px + env(safe-area-inset-bottom));-webkit-text-size-adjust:100%}
  h1.page{font-size:19px;margin:0 0 4px}
  .sub{color:var(--muted);font-size:13px;margin:0 0 14px}
  .btn{display:flex;align-items:center;justify-content:center;width:100%;font:inherit;font-size:17px;font-weight:600;
    border:0;border-radius:14px;padding:16px 14px;background:var(--accent);color:#fff;cursor:pointer;
    -webkit-user-select:none;user-select:none;touch-action:manipulation;margin:0 0 10px}
  .btn:active{filter:brightness(.92)}
  .btn.secondary{background:#202b36;border:1px solid var(--border);color:var(--text);font-size:15px;font-weight:500;padding:13px 12px}
  .status{min-height:40px;font-size:14px;margin:2px 2px 10px;color:var(--muted)}
  .status.ok{color:var(--ok)}
  .article{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:14px;margin:12px 0;
    -webkit-user-select:text;user-select:text}
  .article h1{font-size:21px;line-height:1.25;margin:0 0 12px}
  .article h2{font-size:17.5px;line-height:1.3;margin:18px 0 8px}
  .article p{margin:0 0 13px}
  .article blockquote{margin:0 0 4px;padding:6px 12px;border-left:3px solid var(--accent);color:#d7e2ec}
  .article blockquote cite{font-style:normal;opacity:.85}
  .foot{color:var(--muted);font-size:12.5px;line-height:1.55;margin-top:16px;border-top:1px solid var(--border);padding-top:14px}
</style>
</head>
<body>
<h1 class="page">Копировать статью</h1>
<p class="sub">__CHARS__ знаков · воздух перед заголовками · каждый пункт отдельным блоком</p>
<button class="btn" id="copy">Скопировать с форматированием</button>
<div class="status" id="status"></div>
<button class="btn secondary" id="select">Выделить статью целиком</button>
<div class="article" id="article">__ARTICLE__</div>
<div class="foot">Вставка: Telegram → канал → 📎 → «Статья» → долгое нажатие → «Вставить».
Если система не дала положить HTML в буфер — «Выделить статью целиком» и «Копировать» в меню Android.</div>
<script>
var RICH = __RICH_JSON__;
var PLAIN = __PLAIN_JSON__;
var statusEl = document.getElementById('status');
var article = document.getElementById('article');
function say(m, ok){ statusEl.textContent = m; statusEl.className = 'status' + (ok ? ' ok' : ''); }
function selectArticle(){
  var r = document.createRange(); r.selectNodeContents(article);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
}
document.getElementById('copy').addEventListener('click', async function(){
  try{
    if (navigator.clipboard && window.ClipboardItem && navigator.clipboard.write){
      await navigator.clipboard.write([new ClipboardItem({
        'text/html': new Blob([RICH], {type:'text/html'}),
        'text/plain': new Blob([PLAIN], {type:'text/plain'})
      })]);
      say('Скопировано с оформлением. Вставляйте в «Статью».', true);
      return;
    }
    throw new Error('no ClipboardItem');
  }catch(e){
    selectArticle();
    say('Система не дала HTML в буфер. Статья выделена — нажмите «Копировать» в меню Android.', true);
  }
});
document.getElementById('select').addEventListener('click', function(){
  selectArticle(); say('Статья выделена. В меню Android нажмите «Копировать».', true);
});
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=Path("copy.html"))
    args = ap.parse_args()

    md = args.source.read_text(encoding="utf-8")
    rich, plain, stats = render(md)
    chars = len(plain)

    assert "\u2060" not in md, "в L2-источнике найден U+2060"
    assert "\u200b" not in md, "в L2-источнике найден U+200B"
    assert chars <= 32768, f"статья длиннее лимита: {chars}"

    page = (
        TPL.replace("__ARTICLE__", rich)
        .replace("__RICH_JSON__", json.dumps(rich, ensure_ascii=False))
        .replace("__PLAIN_JSON__", json.dumps(plain, ensure_ascii=False))
        .replace("__CHARS__", f"{chars:,}".replace(",", " "))
    )
    args.output.write_text(page, encoding="utf-8")

    print(f"{args.source} → {args.output}")
    print(
        f"символов {chars} / 32768 · заголовков {stats['headings']} · цитат {stats['quotes']} · "
        f"пунктов {stats['items']} · воздушных блоков {stats['air']}"
    )


if __name__ == "__main__":
    main()
