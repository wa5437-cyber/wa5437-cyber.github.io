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
    return (strip(h1.group(1)) if h1 else slug, short(strip(lede.group(1))) if lede else "")


def alts_for(path_ko, langs=("ko", "en")):
    return {l: url(l, path_ko) for l in langs}


def app_href(lang, app):
    """상세 페이지가 있으면 그 주소, 없으면 앱 목록(깨진 링크 방지)."""
    return url(lang, "/apps/" + app["slug"] + "/") if app.get("detail") else url(lang, "/apps/")


def json_ld(lang):
    """홈의 구조화 데이터(Organization + WebSite). 값은 json.dumps 로만 만든다."""
    data = [
        {"@context": "https://schema.org", "@type": "Organization", "name": kit.SITE["brand"],
         "url": kit.BASE + "/", "logo": kit.BASE + "/og-image.png"},
        {"@context": "https://schema.org", "@type": "WebSite", "name": kit.SITE["brand"],
         "url": kit.BASE + "/", "inLanguage": lang},
    ]
    text = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return '<script type="application/ld+json">' + text + "</script>"


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
        f'<h3>{esc(apps[s]["name"][lang])}</h3><p>{esc(short(apps[s]["tagline"][lang]))}</p></a>'
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
                          extra_head=(HASH_KEEP if lang == "ko" else "") + json_ld(lang))


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


CAMPAIGN = "?pt=129167489&amp;ct=homepage&amp;mt=8"


def short(s, n=110):
    """n 자를 넘으면 n 자 안의 마지막 공백에서 자르고(공백이 없으면 그냥 n 자), 끝 문장부호를 떼고 … 를 붙인다."""
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    # 다음 글자가 공백이면 cut 이 이미 낱말 경계에서 끝난 것이다.
    if s[n] != " " and " " in cut:
        cut = cut[:cut.rindex(" ")]
    return cut.rstrip(" ,.;:!?·-—") + "…"


def store_buttons(app, lang):
    out = [f'<a class="btn primary" href="{esc(app["appstore"])}{CAMPAIGN}" target="_blank" rel="noopener">App Store</a>']
    if app.get("play"):
        out.append(f'<a class="btn" href="{esc(app["play"])}" target="_blank" rel="noopener">Google Play</a>')
    return "".join(out)


def apps_index(lang):
    d = load("apps.json")
    cards = ""
    for a in d["apps"]:
        link = ""
        if a.get("detail"):
            link = f'<a class="more" href="{esc(url(lang, "/apps/" + a["slug"] + "/"))}">{"자세히 보기" if lang == "ko" else "Details"} →</a>'
        pill = f'<span class="pill">{esc(a["badge"][lang])}</span>' if a["badge"][lang] else ""
        cards += (f'<div class="card">{pill}'
                  f'<h3>{esc(a["name"][lang])}</h3><p>{esc(short(a["tagline"][lang]))}</p>'
                  f'<div class="row">{store_buttons(a, lang)}</div>{link}</div>')
    title = "앱 | ML Music Studio" if lang == "ko" else "Apps | ML Music Studio"
    h1 = "앱" if lang == "ko" else "Apps"
    sub = ("사운드 엔지니어가 현장에서 쓰려고 만든 앱입니다." if lang == "ko"
           else "Apps built by a sound engineer for real-world use.")
    body = (f'<section class="hero"><div class="wrap"><h1>{h1}</h1><p class="sub">{sub}</p></div></section>'
            f'<section class="band"><div class="wrap"><div class="cards c3">{cards}</div></div></section>')
    path = url(lang, "/apps/")
    return path, kit.page(lang, path, title, sub, body, alts_for("/apps/"))


def app_page(lang, slug):
    d = load("apps.json")
    app = next(a for a in d["apps"] if a["slug"] == slug)
    det = d["details"][slug]
    img_dir = f"/img/apps/{slug}/"
    bullets = "".join(f"<li>{esc(b)}</li>" for b in det["bullets"][lang])
    facts = "".join(f"<li>{esc(f)}</li>" for f in det["facts"][lang])
    blocks = ""
    for i, b in enumerate(det["blocks"]):
        blocks += (f'<div class="alt{" rev" if i % 2 else ""}"><div class="alt-img">'
                   f'<img class="shot" src="{img_dir}{esc(b["img"])}" alt="{esc(b["alt"][lang])}" loading="lazy"></div>'
                   f'<div><h3>{esc(b["title"][lang])}</h3><p>{esc(b["text"][lang])}</p></div></div>')
    steps = "".join(f'<li><strong>{esc(s["t"])}</strong><br>{esc(s["d"])}</li>' for s in det["steps"][lang])
    howto = "사용법" if lang == "ko" else "How to use"
    guides = ""
    for g in det.get("related", []):
        info = guide_title(g)
        if info:
            guides += f'<li><a href="/guides/{esc(g)}.html">{esc(info[0])}</a></li>'
    rel = (f'<section class="band"><div class="wrap"><h2>{"관련 가이드" if lang == "ko" else "Related guides (Korean)"}</h2>'
           f'<ul class="bullets">{guides}</ul></div></section>') if guides else ""
    privacy = (f'<p><a href="/policy.html#policy">{"개인정보처리방침" if lang == "ko" else "Privacy policy (Korean)"}</a></p>')
    body = (
        f'<section class="hero"><div class="wrap"><div class="grid"><div>'
        f'<span class="pill">{esc(det["platforms"][lang])}</span>'
        f'<h1>{esc(app["name"][lang])}</h1><p class="sub">{esc(det["lead"][lang] if det.get("lead") else short(app["tagline"][lang], 160))}</p>'
        f'<ul class="bullets">{bullets}</ul>'
        f'<div class="row">{store_buttons(app, lang)}<span class="pill" style="align-self:center">{esc(det["price"][lang])}</span></div>'
        f'</div><div><img class="shot" src="{img_dir}01_home.jpg" alt="{esc(app["name"][lang])}"></div></div></div></section>'
        f'<section class="band"><div class="wrap">{blocks}</div></section>'
        f'<section class="band"><div class="wrap"><h2>{howto}</h2><ol class="steps">{steps}</ol></div></section>'
        f'<section class="band"><div class="wrap"><ul class="facts">{facts}</ul>{privacy}</div></section>{rel}')
    path = url(lang, f"/apps/{slug}/")
    title = f'{app["name"][lang]} | ML Music Studio'
    return path, kit.page(lang, path, title, short(app["tagline"][lang], 150), body, alts_for(f"/apps/{slug}/"))


def update_sitemap(root, new_paths):
    f = pathlib.Path(root) / "sitemap.xml"
    if not f.exists():          # 임시 폴더 테스트 등
        return
    text = f.read_text(encoding="utf-8")
    add = ""
    for p in dict.fromkeys(new_paths):
        loc = f"<loc>{kit.BASE}{p}</loc>"
        if loc not in text:
            add += f"<url>{loc}</url>\n"
    if add:
        text = text.replace("</urlset>", add + "</urlset>")
        f.write_text(text, encoding="utf-8")


def build_all(root):
    root = pathlib.Path(root)
    d = load("apps.json")
    for lang in ("ko", "en"):
        for fn in (home, tools, apps_index):
            path, html = fn(lang)
            kit.write(root, path, html)
        for a in d["apps"]:
            if a.get("detail"):
                path, html = app_page(lang, a["slug"])
                kit.write(root, path, html)
    made = []
    for lang in ("ko", "en"):
        made += [url(lang, "/"), url(lang, "/tools/"), url(lang, "/apps/")]
        made += [url(lang, "/apps/" + a["slug"] + "/") for a in d["apps"] if a.get("detail")]
    update_sitemap(root, made)
