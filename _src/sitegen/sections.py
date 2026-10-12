"""구역(section) 렌더러. 페이지 JSON 의 sections 목록을 HTML 로 바꾼다. 모든 문자열은 kit.esc 를 거친다."""
from . import kit
from .kit import esc


def _wrap(inner):
    return f'<section class="band"><div class="wrap">{inner}</div></section>'


def _h2(sec):
    return f'<h2>{esc(sec["title"])}</h2>' if sec.get("title") else ""


def _prose(sec, lang, ctx):
    paras = "".join(f"<p>{esc(p)}</p>" for p in sec.get("paragraphs", []))
    links = "".join(f'<p><a href="{esc(l["href"])}" rel="noopener">{esc(l["text"])}</a></p>'
                    for l in sec.get("links", []))
    return _wrap(_h2(sec) + paras + links)


def _list(sec, lang, ctx):
    items = "".join(f"<li>{esc(i)}</li>" for i in sec["items"])
    return _wrap(_h2(sec) + f'<ul class="bullets">{items}</ul>')


def _cards(sec, lang, ctx):
    def card(i):
        inner = f'<h3>{esc(i["title"])}</h3><p>{esc(i["text"])}</p>'
        if i.get("href"):
            return f'<a class="card" href="{esc(i["href"])}">{inner}</a>'
        return f'<div class="card">{inner}</div>'
    cards = "".join(card(i) for i in sec["items"])
    return _wrap(_h2(sec) + f'<div class="cards c3">{cards}</div>')


def _steps(sec, lang, ctx):
    items = "".join(f'<li><strong>{esc(i["t"])}</strong><br>{esc(i["d"])}</li>' for i in sec["items"])
    return _wrap(_h2(sec) + f'<ol class="steps">{items}</ol>')


def _contact(sec, lang, ctx):
    c = ctx["contact"]
    k = kit.chrome(lang)
    text = f'<p>{esc(sec["text"])}</p>' if sec.get("text") else ""
    row = (f'<div class="row"><a class="btn primary" href="{esc(c["kakao"])}" rel="noopener">'
           f'{esc(kit.t("chat", k))}</a>'
           f'<a class="btn" href="mailto:{esc(c["email"])}">{esc(c["email"])}</a></div>')
    addr = ""
    a = c.get("address")
    if a:
        a = a.get(k) or a.get("ko") if isinstance(a, dict) else a
        link = c.get("map")
        inner = f'<a href="{esc(link)}" rel="noopener">{esc(a)}</a>' if link else esc(a)
        addr = f'<p class="addr">{inner}</p>'
    return _wrap(_h2(sec) + text + row + addr)


def _photos(sec, lang, ctx):
    shown = [i for i in sec["items"] if ctx["img_exists"](i["src"])]
    if not shown:
        return ""
    imgs = "".join(f'<img class="shot" src="{esc(i["src"])}" alt="{esc(i["alt"])}" loading="lazy">'
                   for i in shown)
    return _wrap(_h2(sec) + f'<div class="shots">{imgs}</div>')


WORKS_UI = {
    "ko": {"cols": ("연도", "아티스트", "작품", "역할"), "church": "교회·찬양"},
    "en": {"cols": ("Year", "Artist", "Work", "Role"), "church": "Worship"},
}


def _works(sec, lang, ctx):
    works = (ctx.get("career") or {}).get("works")
    if not works:
        return ""
    ui = WORKS_UI[kit.chrome(lang)]
    keys = ("year", "artist", "title", "role")
    head = "".join(f"<th>{esc(c)}</th>" for c in ui["cols"])
    rows = ""
    for w in works:
        cells = ""
        for key, label in zip(keys, ui["cols"]):
            val = "" if w.get(key) is None else esc(w[key])
            if key == "title" and w.get("album"):      # 곡명 다음에 앨범/구분(없으면 앨범만)
                album = f'<span class="album">{esc(w["album"])}</span>'
                val = f"{val} {album}" if val else album
            if key == "artist" and w.get("church"):
                val += f' <span class="pill">{esc(ui["church"])}</span>'
            cells += f'<td data-label="{esc(label)}">{val}</td>'
        rows += f"<tr>{cells}</tr>"
    note = f'<p class="note">{esc(sec["note"])}</p>' if sec.get("note") else ""
    cap = f'<caption>{esc(sec["title"])}</caption>' if sec.get("title") else ""
    return _wrap(_h2(sec) + f'<table class="works">{cap}<thead><tr>{head}</tr></thead>'
                 f'<tbody>{rows}</tbody></table>{note}')


def _facts(sec, lang, ctx):
    items = "".join(f"<li>{esc(i)}</li>" for i in sec["items"])
    return _wrap(f'<ul class="facts">{items}</ul>')


RENDERERS = {"prose": _prose, "list": _list, "cards": _cards, "steps": _steps,
             "contact": _contact, "photos": _photos, "works": _works, "facts": _facts}


def render(sections, lang, ctx):
    out = []
    for sec in sections:
        fn = RENDERERS.get(sec.get("type"))
        if fn is None:
            raise ValueError(f'unknown section type: {sec.get("type")!r}')
        out.append(fn(sec, lang, ctx))
    return "".join(out)
