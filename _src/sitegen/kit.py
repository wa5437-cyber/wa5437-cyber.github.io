import html
import json
import pathlib

from . import strings

SRC = pathlib.Path(__file__).resolve().parents[1]
SITE = json.loads((SRC / "content" / "site.json").read_text(encoding="utf-8"))
BASE = "https://mlmusicstudio.co.kr"
FONTS = ("https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700"
         "&family=Noto+Serif+KR:wght@600;700&display=swap")
LANGS = ("ko", "en")            # 지원 언어의 유일한 기준. 2단계에서 여기만 늘린다.
OG_LOCALE = {"ko": "ko_KR", "en": "en_US"}
ADS = ('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
       '?client=ca-pub-2274337627237362" crossorigin="anonymous"></script>')


def esc(s):
    return html.escape(str(s), quote=True)


def url(lang, path):
    """ko 는 기본(접두사 없음), 나머지 언어는 /<lang> 접두사. 모르는 언어는 오류."""
    if lang not in LANGS:
        raise ValueError(f"unknown language: {lang}")
    return path if lang == "ko" else "/" + lang + path


def write(root, url_path, content):
    root = pathlib.Path(root)
    rel = url_path.lstrip("/")
    target = root / (rel + "index.html" if url_path.endswith("/") else rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def t(key, lang):
    if lang not in LANGS:
        raise ValueError(f"unknown language: {lang}")
    if key not in strings.S:
        raise ValueError(f"unknown string key: {key}")
    if lang not in strings.S[key]:
        raise ValueError(f"missing translation: {key} [{lang}]")
    return strings.S[key][lang]


def lang_menu(lang, alts):
    """언어 드롭다운. 짝이 있는 언어만 보여 준다(없는 페이지로 보내지 않음)."""
    if len(alts) < 2:
        return ""
    def item(code, path):
        cur = ' aria-current="true"' if code == lang else ""
        return (f'<li><a href="{esc(path)}" hreflang="{code}" lang="{code}"{cur}>'
                f'{esc(strings.LANG_NAMES[code])}</a></li>')
    items = "".join(item(code, path) for code, path in alts.items())
    return (f'<details class="lang"><summary aria-label="{esc(t("lang_label", lang))}">'
            f'{lang.upper()} ▾</summary><ul>{items}</ul></details>')


def header(lang, alts):
    links = [("nav_apps", "/apps/"), ("nav_tools", "/tools/"), ("nav_plugins", "/plugins/"),
             ("nav_studio", "/studio/"), ("nav_guides", "/guides/")]
    # 아직 만들어지지 않은 단계의 메뉴(플러그인·녹음실)도 자리는 잡아 둔다. 링크 점검은 build 단계에서 한다.
    nav = "".join(
        f'<li><a href="{esc(url(lang, p) if p != "/guides/" else "/guides/")}">{esc(t(k, lang))}</a></li>'
        for k, p in links)
    return (f'<header class="site-header"><div class="wrap bar">'
            f'<a class="brand" href="{esc(url(lang, "/"))}">{esc(SITE["brand"])}</a>'
            f'<details class="menu"><summary>{esc(t("menu", lang))}</summary><ul class="nav">{nav}</ul></details>'
            f'<ul class="nav nav-wide">{nav}</ul>{lang_menu(lang, alts)}</div></header>')


def footer(lang):
    c = SITE["contact"]
    return (f'<footer class="site-footer"><div class="wrap">'
            f'<p class="foot-tag">{esc(t("footer_tag", lang))}</p>'
            f'<ul class="foot-links">'
            f'<li><a href="{esc(url(lang, "/about/"))}">{esc(t("footer_about", lang))}</a></li>'
            f'<li><a href="{esc(url(lang, "/privacy/"))}">{esc(t("footer_privacy", lang))}</a></li>'
            f'<li><a href="{esc(url(lang, "/contact/"))}">{esc(t("footer_contact", lang))}</a></li>'
            f'<li><a href="{esc(c["kakao"])}" rel="noopener">{esc(t("chat", lang))}</a></li>'
            f'<li><a href="mailto:{esc(c["email"])}">{esc(c["email"])}</a></li></ul>'
            f'<p class="copy">© 2026 {esc(SITE["brand"])}</p></div></footer>')


def page(lang, path, title, description, body, alts, extra_head=""):
    if lang not in LANGS:
        raise ValueError(f"unknown language: {lang}")
    alt_tags = "".join(
        f'<link rel="alternate" hreflang="{code}" href="{BASE}{p}">' for code, p in alts.items())
    xdef = f'<link rel="alternate" hreflang="x-default" href="{BASE}{alts.get("ko", path)}">' if alts else ""
    verif = "".join(tag + "\n" for tag in SITE["verification_meta"])
    return (f'<!DOCTYPE html>\n<html lang="{lang}">\n<head>\n<meta charset="UTF-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{esc(title)}</title>\n<meta name="description" content="{esc(description)}">\n'
            f'<link rel="canonical" href="{BASE}{path}">\n{alt_tags}{xdef}\n{verif}'
            f'<meta name="theme-color" content="#f6f0e6">\n<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
            f'<meta property="og:type" content="website"><meta property="og:site_name" content="{esc(SITE["brand"])}">\n'
            f'<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}">\n'
            f'<meta property="og:url" content="{BASE}{path}"><meta property="og:image" content="{BASE}/og-image.png">\n'
            f'<meta property="og:locale" content="{OG_LOCALE[lang]}">\n'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)}">\n'
            f'<meta name="twitter:description" content="{esc(description)}"><meta name="twitter:image" content="{BASE}/og-image.png">\n'
            f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'<link href="{FONTS}" rel="stylesheet"><link rel="stylesheet" href="/assets/site.css">\n'
            f'{ADS}\n{extra_head}\n</head>\n<body>\n'
            f'<a class="skip" href="#main">{esc(t("skip", lang))}</a>\n'
            f'{header(lang, alts)}\n<main id="main">{body}</main>\n{footer(lang)}\n</body>\n</html>\n')
