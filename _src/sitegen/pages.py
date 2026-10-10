import json
import pathlib
import re

from . import kit
from .kit import esc, url

SRC = pathlib.Path(__file__).resolve().parents[1]
ROOT = SRC.parent


def load(name):
    return json.loads((SRC / "content" / name).read_text(encoding="utf-8"))


HASH_KEEP = ("<script>if(/^#(policy|privacy)$/.test(location.hash))"
             "location.replace('/policy.html'+location.hash);</script>")


def guide_title(slug):
    """guides/<slug>.html 의 <h1>·첫 문단에서 제목과 한 줄 소개를 읽는다."""
    f = ROOT / "guides" / f"{slug}.html"
    if not f.exists():
        return None
    text = f.read_text(encoding="utf-8")
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S)
    lede = re.search(r'<p class="lede">(.*?)</p>', text, re.S)
    strip = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()
    return (strip(h1.group(1)) if h1 else slug, strip(lede.group(1))[:110] if lede else "")


def alts_for(path_ko, langs=("ko", "en")):
    return {l: url(l, path_ko) for l in langs}


def app_href(lang, app):
    """상세 페이지가 있으면 그 주소, 없으면 앱 목록(깨진 링크 방지)."""
    return url(lang, "/apps/" + app["slug"] + "/") if app.get("detail") else url(lang, "/apps/")


def home(lang):
    h = load("home.json")
    c = h[lang]
    apps = {a["slug"]: a for a in load("apps.json")["apps"]}
    cards = "".join(
        f'<a class="card" href="{esc(url(lang, x["href"]))}" style="text-decoration:none;color:inherit">'
        f'<h3>{esc(x["title"])}{(" <span class=pill>" + esc(x["badge"]) + "</span>") if x.get("badge") else ""}</h3>'
        f'<p>{esc(x["text"])}</p><span class="more">{esc(x["more"])} →</span></a>' for x in c["cards"])
    feat = "".join(
        f'<a class="card" href="{esc(app_href(lang, apps[s]))}" style="text-decoration:none;color:inherit">'
        f'<h3>{esc(apps[s]["name"][lang])}</h3><p>{esc(apps[s]["tagline"][lang])}</p></a>'
        for s in h["featured_apps"] if s in apps)
    guides = ""
    for slug in h["latest_guides"]:
        g = guide_title(slug)
        if g:
            guides += (f'<a class="card" href="/guides/{esc(slug)}.html" style="text-decoration:none;color:inherit">'
                       f'<h3>{esc(g[0])}</h3><p>{esc(g[1])}</p></a>')
    body = (
        f'<section class="hero"><div class="wrap"><div class="grid"><div>'
        f'<h1>{esc(c["h1"])}</h1><p class="sub">{esc(c["sub"])}</p>'
        f'<div class="row"><a class="btn primary" href="{esc(url(lang, "/apps/"))}">{esc(c["cta_apps"])}</a>'
        f'<a class="btn" href="{esc(url(lang, "/studio/"))}">{esc(c["cta_studio"])}</a></div></div>'
        f'<div class="cards" style="grid-template-columns:1fr">{feat}</div></div></div></section>'
        f'<section class="band"><div class="wrap"><div class="cards c3">{cards}</div></div></section>'
        f'<section class="band"><div class="wrap"><h2>{esc(c["tools_title"])}</h2>'
        f'<p class="sub">{esc(c["tools_text"])}</p>'
        f'<div class="row"><a class="btn" href="{esc(url(lang, "/tools/"))}">{esc(c["tools_more"])}</a></div></div></section>'
        + (f'<section class="band"><div class="wrap"><h2>{esc(c["guides_title"])}</h2><div class="cards c3">{guides}</div></div></section>' if guides else "")
        + f'<div class="wrap"><p class="trust">{esc(c["trust"])}</p></div>')
    path = url(lang, "/")
    return path, kit.page(lang, path, c["title"], c["description"], body, alts_for("/"),
                          extra_head=HASH_KEEP if lang == "ko" else "")


def tools(lang):
    c = load("tools.json")[lang]
    apps = {a["slug"]: a for a in load("apps.json")["apps"]}
    groups = ""
    for g in c["groups"]:
        items = ""
        for it in g["items"]:
            app = apps.get(it["app"])
            link = (f' <a class="more" href="{esc(app_href(lang, app))}">'
                    f'{esc(c["app_label"])}: {esc(app["name"][lang])} →</a>') if app else ""
            items += (f'<li><a href="{esc(it["href"])}">{esc(it["name"])}</a>'
                      f'<p>{esc(it["text"])}{link}</p></li>')
        groups += f'<section class="band"><div class="wrap"><h2>{esc(g["title"])}</h2><ul class="tool-list">{items}</ul></div></section>'
    body = (f'<section class="hero"><div class="wrap"><h1>{esc(c["h1"])}</h1>'
            f'<p class="sub">{esc(c["sub"])}</p></div></section>{groups}')
    path = url(lang, "/tools/")
    return path, kit.page(lang, path, c["title"], c["description"], body, alts_for("/tools/"))


def build_all(root):
    root = pathlib.Path(root)
    for lang in ("ko", "en"):
        for fn in (home, tools):
            path, html = fn(lang)
            kit.write(root, path, html)
