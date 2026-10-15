#!/usr/bin/env python3
"""웹 도구 9쪽(옛 화면)에 사이트 머리·푸터·관련 앱 띠를 넣고 새 색·글꼴로 바꾸는 멱등 변환기.

사용: chrome_tools.py          9개 파일을 제자리 변환(바뀐 파일 수 출력)
      chrome_tools.py --check  쓰지 않고, 변환이 필요한 파일이 있으면 종료코드 1

- <script> 의 내용은 한 글자도 건드리지 않는다(테스트가 변환 전후를 바이트 비교한다).
- <style> 안의 옛 크림색·글꼴 이름만 새 값으로 바꾼다. 바꾼 값은 원래 값 목록에 없으므로 다시 적용해도 그대로다.
- <head>: Google Fonts 링크를 새 글꼴로 바꾸고, </head> 앞에 표시(<!-- site-chrome:head -->) 사이로 tools.css 를 넣는다.
- <body>: 바로 뒤에 사이트 머리(ko·en 두 벌, 도구의 언어 선택에 따라 CSS 로 하나만 보임),
          </body> 바로 앞에 관련 앱 띠 + 사이트 푸터. 모두 표시 주석 사이에 있어 다시 적용하면 갈아 끼운다.
- 도구 자체의 언어 선택(i18n-core.js)은 그대로 두고, 사이트 머리에는 언어 메뉴를 넣지 않는다.
- 옛 "← 홈으로" 단추와 문제풀이의 옛 상단 막대는 tools.css 에서 숨긴다(마크업·스크립트는 그대로).
바꿀 자리가 없으면 ValueError(템플릿에서 벗어난 파일을 알아채려고).
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_src"))
from sitegen import kit, pages  # noqa: E402

FILES = ("rta.html", "trainer.html", "generator.html", "effects-listening.html", "delay-calculator.html",
         "acoustics-calculator.html", "electrical-calculator.html", "tempo-pitch-calculator.html",
         "stage-sound-quiz.html")

# 사이트 글꼴(kit.FONTS) + 도구의 숫자 표시에 쓰는 IBM Plex Mono
FONTS = kit.FONTS.replace("&display=swap", "&family=IBM+Plex+Mono:wght@400;500;600&display=swap")
FONT_LINK_RE = re.compile(r'<link href="https://fonts\.googleapis\.com/css2\?[^"]*" rel="stylesheet">')

# 옛 값 -> 새 값(<style> 안에서만). 새 값은 어느 것도 옛 값 목록에 들어 있지 않아야 한다(멱등).
STYLE_MAP = {
    "#faf8f3": "#f4f5f3",            # 바탕
    "#f1ede3": "#e8eeeb",            # 입력칸·보조 판
    "#e3ddd0": "#dbe3df",            # 눌린 단추
    "#ece7db": "#e2e8e5",
    "#d9d3c4": "#cdd5d2",
    "#e8f2ec": "#e8eeeb",
    "#221f1a": "#202426",            # 글
    "#5c574c": "#5b6468",            # 보조 글
    "#8c8677": "#5f686c",            # 흐린 글(대비 4.5:1 이상으로)
    "#2f6d4c": "#23695c",            # 강조
    "#1e4a33": "#194e45",
    "#3a8c5e": "#2c8070",
    "rgba(30,26,20,": "rgba(32,36,38,",
    "rgba(250,248,243,": "rgba(244,245,243,",
    "rgba(47,109,76,": "rgba(35,105,92,",
    "'Space Grotesk','Inter',sans-serif": "'Inter','Noto Sans KR',sans-serif",
    "'Inter',-apple-system,sans-serif": "'Inter','Noto Sans KR',-apple-system,sans-serif",
    "'Inter', -apple-system, sans-serif": "'Inter','Noto Sans KR',-apple-system,sans-serif",
    "'Inter',sans-serif": "'Inter','Noto Sans KR',sans-serif",
}
STYLE_RE = re.compile("|".join(re.escape(k) for k in sorted(STYLE_MAP, key=len, reverse=True)))
STYLE_BLOCK_RE = re.compile(r"(<style>)(.*?)(</style>)", re.S)

HEAD_RE = re.compile(r"\n?<!-- site-chrome:head -->.*?<!-- /site-chrome:head -->", re.S)
TOP_RE = re.compile(r"\n?<!-- site-chrome:header -->.*?<!-- /site-chrome:header -->", re.S)
BOTTOM_RE = re.compile(r"\n?<!-- site-chrome:footer -->.*?<!-- /site-chrome:footer -->", re.S)

UI = {"ko": {"kicker": "관련 앱", "more": "앱 자세히 보기"},
      "en": {"kicker": "Related app", "more": "App details"}}


def _fail(msg):
    raise ValueError(msg)


def _retheme_style(html):
    def one(m):
        return m.group(1) + STYLE_RE.sub(lambda x: STYLE_MAP[x.group(0)], m.group(2)) + m.group(3)
    out, n = STYLE_BLOCK_RE.subn(one, html)
    if n < 1:
        _fail("<style> 블록이 없음")
    return out


def _head(html):
    html, n = FONT_LINK_RE.subn('<link href="%s" rel="stylesheet">' % FONTS, html)
    if n != 1:
        _fail("Google Fonts <link> 가 정확히 하나여야 함(%d개)" % n)
    html = HEAD_RE.sub("", html)
    if html.count("</head>") != 1:
        _fail("</head> 가 정확히 하나여야 함")
    block = ("<!-- site-chrome:head -->\n"
             '<meta name="theme-color" content="%s">\n'
             '<link rel="stylesheet" href="/assets/tools.css">\n'
             "<!-- /site-chrome:head -->\n" % kit.THEME_COLOR)
    return html.replace("</head>", block + "</head>")


def _tag(markup, tag, lang):
    """kit 이 만든 <header class="site-header">·<footer class="site-footer"> 에 언어 표시 클래스를 단다."""
    cls = "site-header" if tag == "header" else "site-footer"
    extra = ' lang="en"' if lang == "en" else ""
    old = '<%s class="%s">' % (tag, cls)
    if not markup.startswith(old):
        _fail("kit 머리/푸터 모양이 바뀜: %s" % markup[:60])
    return '<%s class="%s chrome-%s"%s>' % (tag, cls, lang, extra) + markup[len(old):]


def _tool_items():
    data = pages.load("tools.json")
    return {lang: {it["href"]: it for g in data[lang]["groups"] for it in g["items"]} for lang in ("ko", "en")}


def related(lang, href):
    """도구에 맞는 앱(tools.json 의 app) 띠. 앱 상세 페이지가 있을 때만."""
    it = _tool_items()[lang].get(href)
    if not it or not it.get("app") or not pages.has_detail(it["app"]):
        return ""
    app = next(a for a in pages.load("apps.json")["apps"] if a["slug"] == it["app"])
    det = pages.load_app(app["slug"])["detail"]
    page = kit.url(lang, "/apps/%s/" % app["slug"]) if lang in pages.app_langs(app["slug"]) else kit.url(lang, "/apps/")
    lead = (det.get("lead") or {}).get(lang)
    line = pages.first_sentence(lead) if lead else pages.short(app["tagline"][lang], 90)
    src = pages.app_shot(app, lang)
    shot = ('<span class="tr-shot"><img src="%s" alt=""%s loading="lazy"></span>'
            % (kit.esc(src), kit.img_attrs(src))) if src else ""
    ui = UI[lang]
    extra = ' lang="en"' if lang == "en" else ""
    return ('<section class="tool-related chrome-%s"%s aria-label="%s"><div class="wrap">'
            '<p class="tr-kicker">%s</p><a class="tr-card" href="%s">%s<span class="tr-text">'
            '<strong>%s</strong><span>%s</span><span class="tr-more">%s →</span></span></a></div></section>'
            % (lang, extra, kit.esc(ui["kicker"]), kit.esc(ui["kicker"]), kit.esc(page), shot,
               kit.esc(app["name"][lang]), kit.esc(line), kit.esc(ui["more"])))


def _body(html, href):
    html = TOP_RE.sub("", html)
    html = BOTTOM_RE.sub("", html)
    if html.count("<body>\n") != 1 or html.count("</body>") != 1:
        _fail("<body> / </body> 가 정확히 하나여야 함")
    top = ("<!-- site-chrome:header -->\n" + _tag(kit.header("ko", {}, "/tools/"), "header", "ko") + "\n"
           + _tag(kit.header("en", {}, "/en/tools/"), "header", "en") + "\n<!-- /site-chrome:header -->")
    bottom = ("<!-- site-chrome:footer -->\n" + related("ko", href) + related("en", href) + "\n"
              + _tag(kit.footer("ko"), "footer", "ko") + "\n" + _tag(kit.footer("en"), "footer", "en")
              + "\n<!-- /site-chrome:footer -->")
    html = html.replace("<body>\n", "<body>\n" + top + "\n", 1)
    return html.replace("</body>", bottom + "\n</body>", 1)


def transform(html, name):
    if name not in FILES:
        raise ValueError("알 수 없는 도구 파일: %r" % (name,))
    html = _retheme_style(html)
    html = _head(html)
    return _body(html, "/" + name)


def run(check=False, root=ROOT):
    changed = []
    for name in FILES:
        path = pathlib.Path(root) / name
        old = path.read_text(encoding="utf-8")
        try:
            new = transform(old, name)
        except ValueError as e:
            raise ValueError("%s: %s" % (name, e))
        if new != old:
            changed.append(name)
            if not check:
                path.write_text(new, encoding="utf-8")
    return changed


def main(argv):
    check = "--check" in argv
    changed = run(check=check)
    if check:
        for n in changed:
            print("변환 필요: %s" % n)
        return 1 if changed else 0
    print("바뀐 파일 %d개" % len(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
