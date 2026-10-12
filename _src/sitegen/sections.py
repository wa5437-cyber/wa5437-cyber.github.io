"""구역(section) 렌더러. 페이지 JSON 의 sections 목록을 HTML 로 바꾼다. 모든 문자열은 kit.esc 를 거친다."""
from . import kit
from .kit import esc


def _wrap(inner):
    return f'<section class="band"><div class="wrap">{inner}</div></section>'


def _h2(sec):
    return f'<h2>{esc(sec["title"])}</h2>' if sec.get("title") else ""


def _prose(sec, lang, ctx):
    paras = "".join(f"<p>{esc(p)}</p>" for p in sec.get("paragraphs", []))
    return _wrap(_h2(sec) + paras)


def _list(sec, lang, ctx):
    items = "".join(f"<li>{esc(i)}</li>" for i in sec["items"])
    return _wrap(_h2(sec) + f'<ul class="bullets">{items}</ul>')


def _cards(sec, lang, ctx):
    cards = "".join(f'<div class="card"><h3>{esc(i["title"])}</h3><p>{esc(i["text"])}</p></div>'
                    for i in sec["items"])
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


def _works(sec, lang, ctx):
    career = ctx.get("career")
    works = (career or {}).get("works")
    if not works:
        return ""
    rows = ""
    for w in works:
        cells = [w] if isinstance(w, str) else [w[k] for k in ("year", "title", "role") if w.get(k)]
        rows += "<tr>" + "".join(f"<td>{esc(x)}</td>" for x in cells) + "</tr>"
    note = f'<p class="addr">{esc(sec["note"])}</p>' if sec.get("note") else ""
    return _wrap(_h2(sec) + f'<table class="works"><tbody>{rows}</tbody></table>{note}')


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
