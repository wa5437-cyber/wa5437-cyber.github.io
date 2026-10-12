import json
import pathlib
import re

from . import kit, sections, strings
from .kit import esc, url

SRC = pathlib.Path(__file__).resolve().parents[1]
ROOT = SRC.parent


def load(name):
    return json.loads((SRC / "content" / name).read_text(encoding="utf-8"))


def load_app(slug):
    """content/apps/<slug>.json 을 읽는다. 파일이 없으면 None."""
    f = SRC / "content" / "apps" / f"{slug}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def has_detail(slug):
    app = load_app(slug)
    return bool(app and "detail" in app)


def pick_img(value, lang):
    """문자열이면 그대로, {"ko":…, "en":…} 이면 언어별 파일(없으면 en, 그다음 ko)."""
    if isinstance(value, str):
        return value
    return value.get(lang) or value.get("en") or value["ko"]


# 옛 홈(한국어)에 있던 쪽지(#anchor) 주소 -> 새 주소. 한국어 홈에서만 적용한다.
HASH_MAP = {
    "policy": "/policy.html#policy",
    "privacy": "/policy.html#privacy",
    "apps": "/apps/",
    "download": "/apps/",
    "tools": "/tools/",
    "guides": "/guides/",
}
HASH_KEEP = ("<script>var m=" + json.dumps(HASH_MAP, separators=(",", ":")) +
             ";var u=m[location.hash.slice(1)];"
             "if(typeof u=='string')location.replace(u);</script>")


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
    return url(lang, "/apps/" + app["slug"] + "/") if has_detail(app["slug"]) else url(lang, "/apps/")


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


def first_sentence(text):
    """첫 문장(마침표·물음표·느낌표 + 공백까지). 문장이 하나면 그대로."""
    m = re.match(r"(.+?[.?!])(\s|$)", text.strip())
    return m.group(1) if m else text.strip()


def app_shot(app, lang, img=None):
    """앱의 대표 화면(사이트 루트 기준 주소). img 를 주면 그 파일, 아니면 상세의 hero_img. 상세가 없으면 None."""
    data = load_app(app["slug"])
    det = (data or {}).get("detail")
    if not img and not det:
        return None
    return f'/img/apps/{app["slug"]}/{pick_img(img or det["hero_img"], lang)}'


def shot_img(src, alt, cls="", eager=False):
    """width·height 와 모양(phone/tablet/wide) 클래스를 붙인 <img>."""
    shape = kit.shape(kit.img_size(src))
    load = ' fetchpriority="high"' if eager else ' loading="lazy"'
    klass = f"{cls} {shape}".strip()
    return f'<img class="{klass}" src="{esc(src)}" alt="{esc(alt)}"{kit.img_attrs(src)}{load}>'


def app_card(app, lang, line, more):
    """제품 카드: 위는 화면 무대, 아래는 이름·한 줄·플랫폼."""
    src = app_shot(app, lang)
    stage = f'<div class="stage">{shot_img(src, "", "stage-img")}</div>' if src else ""
    det = (load_app(app["slug"]) or {}).get("detail") or {}
    plat = (det.get("platforms") or {}).get(lang) or app["badge"][lang]
    return (f'<a class="card product" href="{esc(app_href(lang, app))}">{stage}'
            f'<div class="product-body"><h3>{esc(app["name"][lang])}</h3><p>{esc(line)}</p>'
            f'<span class="platforms">{esc(plat)}</span><span class="more">{esc(more)} →</span></div></a>')


def home(lang):
    h = load("home.json")
    c = h[lang]
    all_apps = load("apps.json")["apps"]
    apps = {a["slug"]: a for a in all_apps}
    career = load("career.json")
    # 히어로: 실제 앱 화면 두 장(첫 장만 바로 읽는다)
    shots = ""
    for i, s in enumerate(h["hero_shots"]):
        app = apps[s["app"]]
        src = app_shot(app, lang, s.get("img"))
        alt = c["shot_alt"].format(name=app["name"][lang])
        shots += (f'<div class="device{" lead" if i == 0 else " back"}">'
                  f'{shot_img(src, alt, eager=(i == 0))}</div>')
    lines = c["h1"].split(", ", 1)
    h1 = (f'<span class="line">{esc(lines[0])},</span> <span class="line">{esc(lines[1])}</span>'
          if len(lines) == 2 else esc(c["h1"]))
    hero = (f'<section class="hero home-hero"><div class="wrap"><div class="grid">'
            f'<div class="hero-copy"><h1>{h1}</h1><p class="sub">{esc(c["sub"])}</p>'
            f'<div class="row"><a class="btn primary" href="{esc(url(lang, "/apps/"))}">{esc(c["cta_apps"])}</a>'
            f'<a class="btn" href="{esc(url(lang, "/studio/"))}">{esc(c["cta_studio"])}</a></div></div>'
            f'<div class="hero-stage">{shots}</div></div></div></section>')
    # 대표 앱 3
    def line(a):
        det = (load_app(a["slug"]) or {}).get("detail") or {}
        lead = (det.get("lead") or {}).get(lang)
        return first_sentence(lead) if lead else short(a["tagline"][lang], 80)
    feat = "".join(app_card(apps[s], lang, line(apps[s]), c["details"]) for s in h["featured_apps"] if s in apps)
    featured = (f'<section class="band"><div class="wrap"><div class="band-head"><h2>{esc(c["featured_title"])}</h2>'
                f'<a class="more" href="{esc(url(lang, "/apps/"))}">{esc(c["all_apps"])} ({len(all_apps)}) →</a></div>'
                f'<div class="cards c3">{feat}</div></div></section>')
    # 녹음실(어두운 띠)
    st = c["stats"]
    stats = "".join(f'<div class="stat"><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>' for value, label in (
        (career["total"], st["total"]), (career["roles"]["마스터링"], st["mastering"]),
        (career["roles"]["믹싱"], st["mixing"]), (career["roles"]["녹음"], st["recording"])))
    studio = (f'<section class="band dark"><div class="wrap split studio-band"><div>'
              f'<p class="kicker">{esc(c["studio_kicker"])}</p><h2>{esc(c["studio_title"])}</h2>'
              f'<p class="sub">{esc(c["studio_text"])}</p><p class="trust">{esc(c["trust"])}</p>'
              f'<div class="row"><a class="btn primary" href="{esc(url(lang, "/studio/"))}">{esc(c["cta_studio"])}</a></div></div>'
              f'<dl class="stats">{stats}</dl></div></section>')
    # 플러그인(얇은 띠)
    plugins = (f'<section class="strip"><div class="wrap strip-row"><span class="kicker">{esc(c["plugins_label"])}</span>'
               f'<a href="{esc(url(lang, "/plugins/"))}">{esc(c["plugins_text"])} →</a></div></section>')
    # 웹 도구(이름만) + 최신 가이드(제목 + 한 줄)
    names = {it["href"]: it["name"] for g in load("tools.json")[lang]["groups"] for it in g["items"]}
    tools = "".join(f'<li><a href="{esc(href)}">{esc(names[href])}</a></li>' for href in h["featured_tools"] if href in names)
    guides = ""
    for slug in h["latest_guides"]:
        g = guide_title(slug)
        if g:
            guides += (f'<li><a href="/guides/{esc(slug)}.html">{esc(g[0])}</a>'
                       f'<p>{esc(short(g[1], 70))}</p></li>')
    tools_col = (f'<div><h2>{esc(c["tools_title"])}</h2><ul class="link-list">{tools}</ul>'
                 f'<a class="more" href="{esc(url(lang, "/tools/"))}">{esc(c["tools_more"])} →</a></div>')
    guides_col = (f'<div><h2>{esc(c["guides_title"])}</h2><ul class="link-list guide-links">{guides}</ul>'
                  f'<a class="more" href="/guides/">{esc(c["guides_more"])} →</a></div>') if guides else ""
    more = f'<section class="band"><div class="wrap split">{tools_col}{guides_col}</div></section>'
    body = hero + featured + studio + plugins + more
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


SIMPLE_PAGES = ("plugins", "studio", "about", "contact", "privacy")


def load_page(name):
    """content/pages/<name>.json 을 읽는다. 파일이 없으면 None."""
    f = SRC / "content" / "pages" / f"{name}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def fill_facts(secs, career):
    """facts 구역의 항목 문자열 자리표시자({since} {total} {mastering} {mixing} {recording})를 career.json 으로 채운다.
    모르는 자리표시자는 KeyError 로 빌드를 멈춘다. 다른 구역은 그대로 둔다."""
    values = {"since": career["since"], "total": career["total"],
              "mastering": career["roles"]["마스터링"], "mixing": career["roles"]["믹싱"],
              "recording": career["roles"]["녹음"]}
    out = []
    for sec in secs:
        if sec.get("type") == "facts":
            sec = dict(sec, items=[i.format_map(values) for i in sec["items"]])
        out.append(sec)
    return out


def profile_ld(lang, profile):
    """소개 페이지의 ProfilePage 구조화 데이터. 페이지 JSON 의 최상위 "profile" 값으로 만든다."""
    person = {"@type": "Person", "name": profile["name"], "alternateName": profile["alternateName"],
              "jobTitle": profile["jobTitle"][lang], "url": kit.BASE + "/about/", "sameAs": profile["sameAs"]}
    data = {"@context": "https://schema.org", "@type": "ProfilePage", "mainEntity": person}
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def is_noindex(name):
    """페이지 JSON 최상위 "noindex": true -> 색인 제외(meta robots)·광고 없음·사이트맵에서 뺀다. 내용이 채워지면 지운다."""
    d = load_page(name)
    return bool(d and d.get("noindex"))


def simple_page(lang, name):
    """content/pages/<name>.json 의 hero + 구역들로 만든 단순 페이지."""
    data = load_page(name)
    c = data[lang]
    career = load("career.json")
    ctx = {"contact": kit.SITE["contact"], "career": career,
           "img_exists": lambda p: (ROOT / p.lstrip("/")).exists()}
    body = (f'<section class="hero"><div class="wrap"><h1>{esc(c["h1"])}</h1>'
            f'<p class="sub">{esc(c["sub"])}</p></div></section>'
            + sections.render(fill_facts(c["sections"], career), lang, ctx))
    path = url(lang, f"/{name}/")
    ld = profile_ld(lang, data["profile"]) if data.get("profile") else ""
    return path, kit.page(lang, path, c["title"], c["description"], body, alts_for(f"/{name}/"),
                          extra_head=ld, noindex=bool(data.get("noindex")))


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
        name = esc(a["name"][lang])
        src = app_shot(a, lang)
        stage = f'<div class="stage">{shot_img(src, "", "stage-img")}</div>' if src else ""
        if has_detail(a["slug"]):
            href = esc(url(lang, "/apps/" + a["slug"] + "/"))
            stage = f'<a class="stage-link" href="{href}" tabindex="-1" aria-hidden="true">{stage}</a>' if stage else ""
            title = f'<h3><a href="{href}">{name}</a></h3>'
            link = f'<a class="more" href="{href}">{esc(strings.APP_UI["details"][lang])} →</a>'
        else:
            title, link = f"<h3>{name}</h3>", ""
        pill = f'<span class="pill">{esc(a["badge"][lang])}</span>' if a["badge"][lang] else ""
        cards += (f'<div class="card product">{stage}<div class="product-body">{pill}'
                  f'{title}<p>{esc(short(a["tagline"][lang]))}</p>'
                  f'<div class="row">{store_buttons(a, lang)}</div>{link}</div></div>')
    title = "앱 | ML Music Studio" if lang == "ko" else "Apps | ML Music Studio"
    h1 = "앱" if lang == "ko" else "Apps"
    sub = ("사운드 엔지니어가 현장에서 쓰려고 만든 앱입니다." if lang == "ko"
           else "Apps built by a sound engineer for real-world use.")
    body = (f'<section class="hero"><div class="wrap"><h1>{h1}</h1><p class="sub">{sub}</p></div></section>'
            f'<section class="band"><div class="wrap"><div class="cards c3">{cards}</div></div></section>')
    path = url(lang, "/apps/")
    return path, kit.page(lang, path, title, sub, body, alts_for("/apps/"))


def app_langs(slug):
    """상세 페이지를 낼 언어(kit.LANGS 순). ko·en 은 직접 쓴 bullets 가 있을 때, 나머지는 앱스토어 문구(이름·설명)가 있을 때."""
    app = load_app(slug)
    if not app or "detail" not in app:
        return []
    out = []
    for lang in kit.LANGS:
        if lang in ("ko", "en"):
            if lang in app["detail"].get("bullets", {}):
                out.append(lang)
        else:
            s = (app.get("store") or {}).get(lang) or {}
            if s.get("name") and s.get("description"):
                out.append(lang)
    return out


def alts_for_app(slug):
    return {l: url(l, f"/apps/{slug}/") for l in app_langs(slug)}


BULLET_RE = re.compile(r"([•・]|-\s)\s*")
HANGUL_RUN = kit.HANGUL_RUN
esc_mixed = kit.esc_mixed       # sections.py 도 쓰므로 kit 에 있다


def _is_bullet(line):
    return bool(BULLET_RE.match(line) and BULLET_RE.sub("", line, count=1).strip())


def _ul(lines):
    return '<ul class="bullets">' + "".join(
        f"<li>{esc_mixed(BULLET_RE.sub('', l, count=1).strip())}</li>" for l in lines) + "</ul>"


def render_store_text(text):
    """앱스토어 설명문을 HTML 로. 빈 줄=문단, •/-/・ 로 시작하는 줄만 이어지면 목록, 문단 안 줄바꿈=<br>.
    첫 줄만 제목(불릿 아님)이고 나머지가 전부 불릿이면 <p>제목</p> 뒤에 목록."""
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        if all(_is_bullet(l) for l in lines):
            out.append(_ul(lines))
        elif len(lines) > 1 and not _is_bullet(lines[0]) and all(_is_bullet(l) for l in lines[1:]):
            out.append(f"<p>{esc_mixed(lines[0])}</p>" + _ul(lines[1:]))
        else:
            out.append("<p>" + "<br>".join(esc_mixed(l) for l in lines) + "</p>")
    return "".join(out)


def app_ld(lang, slug, app):
    """SoftwareApplication 구조화 데이터. 가격은 확인할 수 없어 offers 를 쓰지 않는다."""
    data = {"@context": "https://schema.org", "@type": "SoftwareApplication",
            "name": app["name"].get(lang) or app["name"]["en"], "url": kit.BASE + url(lang, f"/apps/{slug}/"),
            "applicationCategory": "MultimediaApplication", "inLanguage": lang, "downloadUrl": app["appstore"]}
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def privacy_href(app):
    return app.get("legal") or "/policy.html#policy"


def _app_page_full(lang, app, det, slug):
    """직접 쓴 상세(ko·en): 불릿·본문 블록·사용법·관련 가이드."""
    img_dir = f"/img/apps/{slug}/"
    ui = strings.APP_UI
    bullets = "".join(f"<li>{esc(b)}</li>" for b in det["bullets"][lang])
    facts = "".join(f"<li>{esc(f)}</li>" for f in det["facts"][lang])
    blocks = ""
    for i, b in enumerate(det["blocks"]):
        blocks += (f'<div class="alt{" rev" if i % 2 else ""}"><div class="alt-img">'
                   f'{shot_img(img_dir + pick_img(b["img"], lang), b["alt"][lang], "shot")}</div>'
                   f'<div class="alt-text"><h3>{esc(b["title"][lang])}</h3><p>{esc(b["text"][lang])}</p></div></div>')
    steps = "".join(f'<li><strong>{esc(s["t"])}</strong><br>{esc(s["d"])}</li>' for s in det["steps"][lang])
    guides = ""
    for g in det.get("related", []):
        info = guide_title(g)
        if info:
            guides += f'<li><a href="/guides/{esc(g)}.html">{esc(info[0])}</a></li>'
    rel = (f'<section class="band"><div class="wrap"><h2>{esc(ui["related"][lang])}</h2>'
           f'<ul class="bullets">{guides}</ul></div></section>') if guides else ""
    privacy = f'<p><a href="{esc(privacy_href(app))}">{esc(ui["privacy"][lang])}</a></p>'
    price = (det.get("price") or {}).get(lang)
    price_pill = f'<span class="pill" style="align-self:center">{esc(price)}</span>' if price else ""
    body = (
        f'<section class="hero app-hero"><div class="wrap"><div class="grid"><div>'
        f'<span class="pill">{esc(det["platforms"][lang])}</span>'
        f'<h1>{esc(app["name"][lang])}</h1><p class="sub">{esc(det["lead"][lang] if det.get("lead") else short(app["tagline"][lang], 160))}</p>'
        f'<ul class="bullets">{bullets}</ul>'
        f'<div class="row">{store_buttons(app, lang)}{price_pill}</div>'
        f'</div><div class="hero-shot">{shot_img(img_dir + pick_img(det["hero_img"], lang), app["name"][lang], "shot", eager=True)}</div></div></div></section>'
        f'<section class="band"><div class="wrap">{blocks}</div></section>'
        f'<section class="band"><div class="wrap"><h2>{esc(ui["howto"][lang])}</h2><ol class="steps">{steps}</ol></div></section>'
        f'<section class="band"><div class="wrap"><ul class="facts">{facts}</ul>{privacy}</div></section>{rel}')
    title = f'{app["name"][lang]} | ML Music Studio'
    return title, short(app["tagline"][lang], 150), body, app_ld(lang, slug, app)


def _app_page_store(lang, app, det, s, slug):
    """앱스토어 문구만으로 만든 상세(그 밖의 언어): 이름·부제·스토어 버튼 -> 화면 3장 -> 설명 -> 개인정보."""
    img_dir = f"/img/apps/{slug}/"
    name = s["name"]
    shots = "".join(shot_img(img_dir + pick_img(b["img"], lang), name, "shot") for b in det["blocks"][:3])
    body = (
        f'<section class="hero app-hero"><div class="wrap"><div class="grid"><div>'
        f'<h1>{esc_mixed(name)}</h1><p class="sub">{esc_mixed(s.get("subtitle", ""))}</p>'
        f'<div class="row">{store_buttons(app, lang)}</div></div>'
        f'<div class="hero-shot">{shot_img(img_dir + pick_img(det["hero_img"], lang), name, "shot", eager=True)}</div></div></div></section>'
        f'<section class="band"><div class="wrap"><h2>{esc(strings.APP_UI["screens"][lang])}</h2>'
        f'<div class="shots">{shots}</div></div></section>'
        f'<section class="band"><div class="wrap">{render_store_text(s["description"])}'
        f'<p><a href="{esc(privacy_href(app))}">{esc(strings.APP_UI["privacy"][lang])}</a></p></div></section>')
    title = f'{name} | ML Music Studio'
    lead = " — ".join(x for x in (s.get("subtitle", ""), s["description"]) if x)   # 홍보 문구(기간 한정)는 쓰지 않는다
    return title, short(lead, 150), body, app_ld(lang, slug, dict(app, name={lang: name}))


def app_page(lang, slug):
    d = load("apps.json")
    app = next(a for a in d["apps"] if a["slug"] == slug)
    data = load_app(slug)
    det = data["detail"]
    if lang in det.get("bullets", {}):
        title, desc, body, ld = _app_page_full(lang, app, det, slug)
    else:
        s = (data.get("store") or {}).get(lang)
        if not s:
            raise ValueError(f"no content for {slug} [{lang}]")
        title, desc, body, ld = _app_page_store(lang, app, det, s, slug)
    path = url(lang, f"/apps/{slug}/")
    return path, kit.page(lang, path, title, desc, body, alts_for_app(slug), extra_head=ld)


def app_page_re(slugs):
    """알려진 앱 slug 의 상세 페이지 주소(언어 접두사 선택)를 알아보는 정규식."""
    langs = "|".join(re.escape(l) for l in kit.LANGS if l != "ko")
    names = "|".join(re.escape(x) for x in slugs) or "(?!)"
    return re.compile(rf"^(?:/(?:{langs}))?/apps/(?:{names})/$")


SITEMAP_REPLACES = {"/about/": "/about.html"}   # 새 주소가 만들어졌을 때만 옛 주소 항목을 뺀다


def update_sitemap(root, new_paths, known_slugs=(), noindex_paths=()):
    """new_paths 를 사이트맵에 더하고, known_slugs 앱의 상세 페이지 주소 중 new_paths 에 없는 것은 뺀다.
    noindex_paths(색인 제외 페이지)는 더하지 않고, 이미 있으면 뺀다. 나머지는 그대로."""
    f = pathlib.Path(root) / "sitemap.xml"
    if not f.exists():          # 임시 폴더 테스트 등
        return
    text = orig = f.read_text(encoding="utf-8")
    skip = set(noindex_paths)
    new_paths = [p for p in new_paths if p not in skip]
    keep = set(new_paths)
    gone = {kit.BASE + old for new, old in SITEMAP_REPLACES.items() if new in keep}
    gone |= {kit.BASE + p for p in skip}
    app_re = app_page_re(known_slugs)

    def drop(m):
        loc = m.group(1)
        if loc in gone:
            return ""
        path = loc[len(kit.BASE):] if loc.startswith(kit.BASE) else None
        return "" if path and app_re.match(path) and path not in keep else m.group(0)
    text = re.sub(r"[ \t]*<url>\s*<loc>([^<]*)</loc>.*?</url>[ \t]*\n?", drop, text, flags=re.S)
    add = ""
    for p in dict.fromkeys(new_paths):
        loc = f"<loc>{kit.BASE}{p}</loc>"
        if loc not in text:
            add += f"<url>{loc}</url>\n"
    if add:
        text = text.replace("</urlset>", add + "</urlset>")
    if text != orig:
        f.write_text(text, encoding="utf-8")


def prune_stale_app_pages(root, slugs):
    """app_langs 에 없는 언어(상세가 없어진 앱은 ko·en 도)의 옛 상세 페이지 index.html 을 지우고, 비면 폴더도 지운다."""
    root = pathlib.Path(root)
    for slug in slugs:
        live = set(app_langs(slug))
        for lang in kit.LANGS:
            if lang in live:
                continue
            f = root / url(lang, f"/apps/{slug}/").strip("/") / "index.html"
            if f.exists():
                f.unlink()
                try:
                    f.parent.rmdir()
                except OSError:      # 다른 파일이 남아 있으면 그대로 둔다
                    pass


def build_all(root):
    root = pathlib.Path(root)
    d = load("apps.json")
    made, noindex = [], []
    for lang in ("ko", "en"):
        for fn in (home, tools, apps_index):
            path, html = fn(lang)
            kit.write(root, path, html)
        made += [url(lang, "/"), url(lang, "/tools/"), url(lang, "/apps/")]
    for name in SIMPLE_PAGES:
        if load_page(name) is None:
            continue
        for lang in ("ko", "en"):
            path, html = simple_page(lang, name)
            kit.write(root, path, html)
            made.append(path)
            if is_noindex(name):
                noindex.append(path)
    slugs = [a["slug"] for a in d["apps"]]
    for slug in slugs:
        for lang in app_langs(slug):
            path, html = app_page(lang, slug)
            kit.write(root, path, html)
            made.append(path)
    prune_stale_app_pages(root, slugs)
    update_sitemap(root, made, slugs, noindex)
