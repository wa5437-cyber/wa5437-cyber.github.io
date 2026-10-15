"""구역(section) 렌더러. 페이지 JSON 의 sections 목록을 HTML 로 바꾼다. 모든 문자열은 kit.esc 를 거친다."""
from . import kit
from .kit import esc


def _wrap(inner, sec=None):
    """구역 하나. 구역에 "tone": "dark" 가 있으면 어두운 띠로 그린다."""
    dark = " dark" if sec and sec.get("tone") == "dark" else ""
    return f'<section class="band{dark}"><div class="wrap">{inner}</div></section>'


def _h2(sec):
    return f'<h2>{esc(sec["title"])}</h2>' if sec.get("title") else ""


def _prose(sec, lang, ctx):
    paras = "".join(f"<p>{esc(p)}</p>" for p in sec.get("paragraphs", []))
    links = "".join(f'<p><a href="{esc(l["href"])}" rel="noopener">{esc(l["text"])}</a></p>'
                    for l in sec.get("links", []))
    return _wrap(_h2(sec) + paras + links, sec)


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
    cols = "c4" if len(sec["items"]) == 4 else "c3"          # 4개는 2×2 / 한 줄 4칸(마지막 칸만 외톨이가 되지 않게)
    return _wrap(_h2(sec) + f'<div class="cards {cols}">{cards}</div>', sec)


def _steps(sec, lang, ctx):
    items = "".join(f'<li><strong>{esc(i["t"])}</strong><br>{esc(i["d"])}</li>' for i in sec["items"])
    return _wrap(_h2(sec) + f'<ol class="steps">{items}</ol>', sec)


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
    return _wrap(_h2(sec) + text + row + addr, sec)


def _photos(sec, lang, ctx):
    shown = [i for i in sec["items"] if ctx["img_exists"](i["src"])]
    if not shown:
        return ""
    imgs = "".join(f'<img class="shot {kit.shape(kit.img_size(i["src"]))}" src="{esc(i["src"])}" alt="{esc(i["alt"])}"'
                   f'{kit.img_attrs(i["src"])} loading="lazy">' for i in shown)
    return _wrap(_h2(sec) + f'<div class="shots">{imgs}</div>')


WORKS_UI = {
    "ko": {"cols": ("연도", "아티스트", "작품", "역할"), "church": "교회·찬양"},
    "en": {"cols": ("Year", "Artist", "Work", "Role"), "church": "Worship",
           # 역할: 전체 문구가 여기 있으면 그대로, 아니면 낱말별로 옮겨 ", " 로 잇는다. 모르는 낱말은 한글 그대로(lang="ko").
           "role_phrases": {"음악믹싱": "Score mixing", "음악 믹싱": "Score mixing", "믹싱 스튜디오": "Mixing (studio)"},
           "role_words": {"마스터링": "Mastering", "믹싱": "Mixing", "녹음": "Recording", "레코딩": "Recording"},
           "albums": {"싱글": "Single", "EP 첫 번째": "EP no.1", "EP 두 번째": "EP no.2"}},
}


def _role(ui, role):
    """역할 칸. ko 는 그대로, en 은 위 표로 옮긴다."""
    if role is None:
        return ""
    if "role_words" not in ui:
        return esc(role)
    if role in ui["role_phrases"]:
        return esc(ui["role_phrases"][role])
    return ", ".join(esc(ui["role_words"][w]) if w in ui["role_words"] else kit.esc_mixed(w) for w in role.split())


def works_table(works, lang, labelledby=None):
    """career.json 의 works 목록을 표로. 영어 표는 한글 이름·곡명을 lang="ko" 로 표시한다."""
    ui = WORKS_UI[kit.chrome(lang)]
    en = "role_words" in ui                       # 영어 표: 한글 이름·곡명은 lang="ko" 로 표시
    text = kit.esc_mixed if en else esc
    keys = ("year", "artist", "title", "role")
    head = "".join(f"<th>{esc(c)}</th>" for c in ui["cols"])
    rows = ""
    for w in works:
        album = w.get("album")
        album_html = text(ui.get("albums", {}).get(album, album)) if album else ""
        cells = ""
        for key, label in zip(keys, ui["cols"]):
            if key == "role":
                val = _role(ui, w.get(key))
            else:
                val = "" if w.get(key) is None else text(w[key])
            if key == "title":
                title = w.get("title")
                if title and title in (w.get("artist") or ""):   # 영화·뮤지컬처럼 작품명이 아티스트 칸에 이미 있으면 되풀이하지 않는다
                    val = ""
                    if not album:
                        val = "—"
                if album:                                       # 곡명 다음에 작은 앨범/구분, 곡명이 없으면 앨범이 곧 작품명
                    if val:
                        val += f' <span class="album">{album_html}</span>'
                    else:
                        val = album_html
            if key == "artist" and w.get("church"):
                val += f' <span class="pill">{esc(ui["church"])}</span>'
            cells += f'<td data-label="{esc(label)}">{val}</td>'
        rows += f"<tr>{cells}</tr>"
    labelled = f' aria-labelledby="{labelledby}"' if labelledby else ""
    return f'<table class="works"{labelled}><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'


def _works(sec, lang, ctx):
    works = (ctx.get("career") or {}).get("works")
    if not works:
        return ""
    note = f'<p class="note">{esc(sec["note"])}</p>' if sec.get("note") else ""
    h2 = f'<h2 id="works-title">{esc(sec["title"])}</h2>' if sec.get("title") else ""
    return _wrap(h2 + works_table(works, lang, "works-title" if sec.get("title") else None) + note)


# --- 작업(포스터·커버) ---

def category_label(key, lang, ctx):
    """포스터 분야(음반·영화…)의 그 언어 이름. 모르는 분야는 그대로."""
    for c in (ctx.get("work") or {}).get("categories", []):
        if c["key"] == key:
            return c.get(kit.chrome(lang)) or key
    return key


def poster_alt(p, lang, ctx):
    """대체 글: "아티스트 — 제목". 아티스트가 없으면 제목만, 제목이 없으면 "아티스트 — 분야"."""
    a, t = p.get("artist"), p.get("title")
    if a and t:
        return f"{a} — {t}"
    if t:
        return t
    return f"{a} — {category_label(p['category'], lang, ctx)}"


def poster_figure(p, lang, ctx, show_cat=False, anchor=None):
    """정사각 커버 하나 + 아래 이름. 이미지는 늦게 읽고 width·height 를 붙인다."""
    text = kit.esc_mixed if kit.chrome(lang) != "ko" else esc
    a, t = p.get("artist"), p.get("title")
    lines = ""
    if a:
        lines += f"<strong>{text(a)}</strong>"
    if t:
        lines += f"<strong>{text(t)}</strong>" if not a else f"<span>{text(t)}</span>"
    if show_cat or not t:
        lines += f'<span class="cat">{esc(category_label(p["category"], lang, ctx))}</span>'
    ident = f' id="{esc(anchor)}"' if anchor else ""
    return (f'<figure class="cover"{ident}><img src="{esc(p["img"])}" alt="{esc(poster_alt(p, lang, ctx))}"'
            f'{kit.img_attrs(p["img"])} loading="lazy"><figcaption>{lines}</figcaption></figure>')


def cover_cols(n):
    """띠로 보여 줄 커버 수에 맞는 넓은 화면 칸 수(마지막 줄이 비지 않게)."""
    for cols in (5, 4, 6, 3):
        if n % cols == 0:
            return cols
    return 4


def cover_strip(items, lang, ctx):
    figs = "".join(poster_figure(p, lang, ctx) for p in items)
    return f'<div class="covers strip-{cover_cols(len(items))}">{figs}</div>'


def _posters(sec, lang, ctx):
    by_img = {p["img"]: p for p in ctx["posters"]}
    items = [by_img[src] for src in sec["items"]]
    more = sec.get("more")
    link = f'<a class="more" href="{esc(more["href"])}">{esc(more["text"])} →</a>' if more else ""
    head = f'<div class="band-head"><h2>{esc(sec["title"])}</h2>{link}</div>'
    return _wrap(head + cover_strip(items, lang, ctx), sec)


def _gallery(sec, lang, ctx):
    figs = ""
    for i in sec["items"]:
        if not ctx["img_exists"](i["src"]):
            continue
        cls = "pic wide" if i.get("wide") else "pic"
        figs += (f'<figure class="{cls}"><img src="{esc(i["src"])}" alt="{esc(i["caption"])}"'
                 f'{kit.img_attrs(i["src"])} loading="lazy"><figcaption>{esc(i["caption"])}</figcaption></figure>')
    if not figs:
        return ""
    return _wrap(_h2(sec) + f'<div class="gallery">{figs}</div>', sec)


def _gear(sec, lang, ctx):
    items = "".join(f"<li>{esc(i)}</li>" for i in ctx["gear"][kit.chrome(lang)])
    note = f'<p class="note">{esc(sec["note"])}</p>' if sec.get("note") else ""
    return _wrap(_h2(sec) + f'<ul class="gear">{items}</ul>{note}', sec)


def present_categories(ctx):
    """포스터에 실제로 있는 분야만, work.json 의 순서대로."""
    have = {p["category"] for p in ctx["posters"]}
    return [c for c in ctx["work"]["categories"] if c["key"] in have]


def _chips(sec, lang, ctx):
    k = kit.chrome(lang)
    items = "".join(f"<li>{esc(c[k])}</li>" for c in present_categories(ctx))
    return _wrap(_h2(sec) + f'<ul class="chips">{items}</ul>', sec)


def _facts(sec, lang, ctx):
    items = "".join(f"<li>{esc(i)}</li>" for i in sec["items"])
    return _wrap(f'<ul class="facts">{items}</ul>')


RENDERERS = {"prose": _prose, "list": _list, "cards": _cards, "steps": _steps,
             "contact": _contact, "photos": _photos, "works": _works, "facts": _facts,
             "posters": _posters, "gallery": _gallery, "gear": _gear, "chips": _chips}


def render(sections, lang, ctx):
    out = []
    for sec in sections:
        fn = RENDERERS.get(sec.get("type"))
        if fn is None:
            raise ValueError(f'unknown section type: {sec.get("type")!r}')
        out.append(fn(sec, lang, ctx))
    return "".join(out)
