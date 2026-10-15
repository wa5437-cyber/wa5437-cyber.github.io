import html
import json
import pathlib
import re

from . import strings

SRC = pathlib.Path(__file__).resolve().parents[1]
SITE = json.loads((SRC / "content" / "site.json").read_text(encoding="utf-8"))
BASE = "https://mlmusicstudio.co.kr"
FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
         "&family=Noto+Sans+KR:wght@400;500;600;700&display=swap")   # 가이드(chrome_legacy.FONTS)도 같은 주소
THEME_COLOR = "#f4f5f3"          # assets/site.css 의 --bg 와 같아야 한다
LANGS = ("ko", "en", "ja", "zh-Hans", "es", "de", "fr", "pt-BR")  # 지원 언어의 유일한 기준
CHROME_LANGS = ("ko", "en")     # 상단 메뉴·푸터를 그 언어로 번역해 둔 언어. 나머지는 영어로 보여 준다.
OG_LOCALE = {"ko": "ko_KR", "en": "en_US", "ja": "ja_JP", "zh-Hans": "zh_CN",
             "es": "es_ES", "de": "de_DE", "fr": "fr_FR", "pt-BR": "pt_BR"}
ADS = ('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
       '?client=ca-pub-2274337627237362" crossorigin="anonymous"></script>')


def esc(s):
    return html.escape(str(s), quote=True)


HANGUL_RUN = re.compile(r"[가-힣]+(?:[ ·→\-][가-힣]+)*")
NOINDEX = '<meta name="robots" content="noindex,follow">'


def esc_mixed(text):
    """esc() 한 뒤 한글 덩어리마다 <span lang="ko"> 로 감싼다(비ko 페이지·영어 표의 앱 이름·곡명 등).
    한글에는 HTML 특수문자가 없어 이스케이프 후 감싸도 안전하다."""
    return HANGUL_RUN.sub(lambda m: f'<span lang="ko">{m.group(0)}</span>', esc(text))


def url(lang, path):
    """ko 는 기본(접두사 없음), 나머지 언어는 /<lang> 접두사. 모르는 언어는 오류."""
    if lang not in LANGS:
        raise ValueError(f"unknown language: {lang}")
    return path if lang == "ko" else "/" + lang + path


def chrome(lang):
    """상단 메뉴·푸터를 어느 언어로 보여 줄지. ko/en 외에는 영어(그 언어의 사이트 본체가 없음)."""
    if lang not in LANGS:
        raise ValueError(f"unknown language: {lang}")
    return lang if lang in CHROME_LANGS else "en"


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
    return (f'<details class="lang"><summary aria-label="{esc(t("lang_label", chrome(lang)))}">'
            f'{esc(strings.LANG_SHORT[lang])} ▾</summary><ul>{items}</ul></details>')


def chrome_lang_attr(lang):
    """영어 chrome 을 다른 언어 페이지에 쓸 때, 그 영역이 영어임을 스크린리더에 알린다."""
    return ' lang="en"' if chrome(lang) != lang else ""


# 녹음실·엔지니어가 먼저, 앱·도구는 그다음(2차 개편, 사용자 지시)
NAV = (("nav_work", "/work/"), ("nav_studio", "/studio/"), ("nav_apps", "/apps/"), ("nav_tools", "/tools/"),
       ("nav_plugins", "/plugins/"), ("nav_guides", "/guides/"))


def _nav_href(c, p):
    return "/guides/" if p == "/guides/" else url(c, p)


def header(lang, alts, current=None):
    """current: 지금 페이지 주소. 그 주소가 속한 메뉴 항목에 aria-current="page" 를 단다."""
    c = chrome(lang)
    def item(k, p):
        href = _nav_href(c, p)
        here = current is not None and current.startswith(url(lang, p) if p != "/guides/" else p)
        cur = ' aria-current="page"' if here else ""
        return f'<li><a href="{esc(href)}"{cur}>{esc(t(k, c))}</a></li>'
    nav = "".join(item(k, p) for k, p in NAV)
    return (f'<header class="site-header"{chrome_lang_attr(lang)}><div class="wrap bar">'
            f'<a class="brand" href="{esc(url(c, "/"))}">{esc(SITE["brand"])}</a>'
            f'<details class="menu"><summary>{esc(t("menu", c))}</summary><ul class="nav">{nav}</ul></details>'
            f'<ul class="nav nav-wide">{nav}</ul>{lang_menu(lang, alts)}</div></header>')


def footer(lang):
    """푸터: 작업 / 스튜디오 / 제품 / 문의 네 묶음."""
    c = SITE["contact"]
    k = chrome(lang)
    def links(items):
        return "".join(f'<li><a href="{esc(h)}"{extra}>{esc(label)}</a></li>' for h, label, extra in items)
    groups = (
        ("footer_work", [(url(k, "/work/"), t("nav_work", k), ""), (url(k, "/about/"), t("footer_about", k), "")]),
        ("footer_studio", [(url(k, "/studio/"), t("nav_studio", k), ""), (c["map"], t("footer_map", k), ' rel="noopener"')]),
        ("footer_products", [(url(k, "/apps/"), t("nav_apps", k), ""), (url(k, "/tools/"), t("nav_tools", k), ""),
                             (url(k, "/plugins/"), t("nav_plugins", k), ""), ("/guides/", t("nav_guides", k), "")]),
        ("footer_support", [(url(k, "/contact/"), t("footer_contact", k), ""),
                            (c["kakao"], t("chat", k), ' rel="noopener"'),
                            (f'mailto:{c["email"]}', c["email"], ""),
                            (url(k, "/privacy/"), t("footer_privacy", k), "")]),
    )
    cols = "".join(f'<div class="foot-col"><p class="foot-h">{esc(t(g, k))}</p><ul class="foot-links">{links(items)}</ul></div>'
                   for g, items in groups)
    return (f'<footer class="site-footer"{chrome_lang_attr(lang)}><div class="wrap foot-grid">'
            f'<div class="foot-brand"><a class="brand" href="{esc(url(k, "/"))}">{esc(SITE["brand"])}</a>'
            f'<p class="foot-tag">{esc(t("footer_tag", k))}</p></div>{cols}</div>'
            f'<div class="wrap"><p class="copy">© 2026 {esc(SITE["brand"])}</p></div></footer>')


def img_size(rel_path):
    """사이트 루트 기준 이미지 파일의 (가로, 세로) 픽셀. JPEG 은 SOF 표시를, PNG 는 IHDR 을 읽는다. 없거나 모르면 None."""
    f = SRC.parent / rel_path.lstrip("/")
    try:
        data = f.read_bytes()
    except OSError:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker == 0xFF:          # 채움 바이트
            i += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg = int.from_bytes(data[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h = int.from_bytes(data[i + 5:i + 7], "big")
            w = int.from_bytes(data[i + 7:i + 9], "big")
            return w, h
        i += 2 + seg
    return None


def shape(size):
    """화면 모양: 세로로 긴 휴대폰(phone), 세로 태블릿(tablet), 가로 화면(wide). 크기를 모르면 phone."""
    if not size:
        return "phone"
    w, h = size
    if w >= h:
        return "wide"
    return "phone" if w / h < 0.6 else "tablet"


def img_attrs(rel_path):
    """<img> 에 붙일 width·height 속성 문자열(크기를 모르면 빈 문자열)."""
    size = img_size(rel_path)
    return f' width="{size[0]}" height="{size[1]}"' if size else ""


def page(lang, path, title, description, body, alts, extra_head="", noindex=False):
    if lang not in LANGS:
        raise ValueError(f"unknown language: {lang}")
    alt_tags = "".join(
        f'<link rel="alternate" hreflang="{code}" href="{BASE}{p}">' for code, p in alts.items())
    xdef = f'<link rel="alternate" hreflang="x-default" href="{BASE}{alts.get("ko", path)}">' if alts else ""
    verif = "".join(tag + "\n" for tag in SITE["verification_meta"])
    robots = NOINDEX + "\n" if noindex else ""
    ads = "" if noindex else ADS + "\n"      # 내용이 얇은 페이지는 색인에서 빼고 광고도 넣지 않는다
    return (f'<!DOCTYPE html>\n<html lang="{lang}">\n<head>\n<meta charset="UTF-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{esc(title)}</title>\n<meta name="description" content="{esc(description)}">\n'
            f'<link rel="canonical" href="{BASE}{path}">\n{alt_tags}{xdef}\n{verif}'
            f'<meta name="theme-color" content="{THEME_COLOR}">\n<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
            f'<meta property="og:type" content="website"><meta property="og:site_name" content="{esc(SITE["brand"])}">\n'
            f'<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}">\n'
            f'<meta property="og:url" content="{BASE}{path}"><meta property="og:image" content="{BASE}/og-image.png">\n'
            f'<meta property="og:locale" content="{OG_LOCALE[lang]}">\n'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)}">\n'
            f'<meta name="twitter:description" content="{esc(description)}"><meta name="twitter:image" content="{BASE}/og-image.png">\n'
            f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'<link href="{FONTS}" rel="stylesheet"><link rel="stylesheet" href="/assets/site.css">\n'
            f'{robots}{ads}{extra_head}\n</head>\n<body>\n'
            f'<a class="skip" href="#main"{chrome_lang_attr(lang)}>{esc(t("skip", chrome(lang)))}</a>\n'
            f'{header(lang, alts, path)}\n<main id="main">{body}</main>\n{footer(lang)}\n</body>\n</html>\n')
