#!/usr/bin/env python3
"""웹 도구 9쪽(옛 화면)에 사이트 머리·푸터·관련 앱 띠를 넣고 새 색·글꼴로 바꾸는 멱등 변환기.

사용: chrome_tools.py          9개 파일을 제자리 변환(바뀐 파일 수 출력)
      chrome_tools.py --check  쓰지 않고, 변환이 필요한 파일이 있으면 종료코드 1

- <script> 의 내용은 한 글자도 건드리지 않는다(테스트가 변환 전후를 바이트 비교한다).
- <style> 안의 옛 크림색·글꼴 이름·대비가 부족한 강조색을 바꾼다. 새 값은 치환 대상이 아니므로 멱등이다.
- <head>: Google Fonts 링크를 새 글꼴로 바꾸고, </head> 앞에 표시(<!-- site-chrome:head -->) 사이로 tools.css 를 넣는다.
- <body>: 바로 뒤에 사이트 머리(ko·en 두 벌, 도구의 언어 선택에 따라 CSS 로 하나만 보임),
          상단 도구 제목 바로 아래에 앱 버전 패널, </body> 앞에 사이트 푸터. 표시 주석 사이를 다시 갈아 끼운다.
- i18n 쌍(<script>window.I18N_DATA = …</script> + <script src="i18n-core.js"></script>)은 본문 맨 끝에서 꺼내
  첫 번째 인라인 본 <script> 바로 앞으로 옮긴다. 본 스크립트가 시작할 때 window.i18n.t() 를 부르는 쪽(지연·전기·템포 계산기)이
  "Cannot read properties of undefined" 로 죽던 버그를 고친다. 스크립트 내용은 그대로, 순서만 바뀐다.
- 도구 자체의 언어 선택(i18n-core.js)은 그대로 두고, 사이트 머리에는 언어 메뉴를 넣지 않는다.
- 옛 "← 홈으로" 단추와 문제풀이의 옛 상단 막대는 tools.css 에서 숨긴다(마크업·스크립트는 그대로).
- 확대 제한을 없애고 본문 랜드마크·제목·정적 입력 라벨을 보완한다. 스크립트로 만드는 입력은 건드리지 않는다.
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
    "#8c8677": "#5b6468",            # 선택된 회색 바탕에서도 대비 4.5:1 이상
    "#5f686c": "#5b6468",
    "#9c6b17": "#805710",            # amber: 선택된 버튼 바탕에서 3.55:1 -> 4.89:1
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
PAIR_RE = re.compile(r"\n?<!-- site-chrome:app -->.*?<!-- /site-chrome:app -->", re.S)
TOOL_TOP_RE = re.compile(r'(<div class="topbar">.*?<a class="home-link"[^>]*>.*?</a>\s*</div>)', re.S)

# 언어 선택이 없는 파일(문제풀이)에는 i18n 쌍이 없다. 나머지 8쪽에는 반드시 있어야 한다.
NO_I18N = ("stage-sound-quiz.html",)
I18N_PAIR_RE = re.compile(r'^<script>window\.I18N_DATA = [^\n]*</script>\n<script src="i18n-core\.js"></script>\n', re.M)
ADSENSE_RE = re.compile(r'<script async src="https://pagead2\.googlesyndication\.com/[^"]*"[^>]*></script>')
INLINE_SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>")

def _fail(msg):
    raise ValueError(msg)


def _retheme_style(html):
    def one(m):
        return m.group(1) + STYLE_RE.sub(lambda x: STYLE_MAP[x.group(0)], m.group(2)) + m.group(3)
    out, n = STYLE_BLOCK_RE.subn(one, html)
    if n < 1:
        _fail("<style> 블록이 없음")
    return out


def _head(html, name):
    html, n = FONT_LINK_RE.subn('<link href="%s" rel="stylesheet">' % FONTS, html)
    if n != 1:
        _fail("Google Fonts <link> 가 정확히 하나여야 함(%d개)" % n)
    html = HEAD_RE.sub("", html)
    if html.count("</head>") != 1:
        _fail("</head> 가 정확히 하나여야 함")
    item = _tool_items()["ko"]["/" + name]
    description = (f'<meta name="description" content="{kit.esc(item["text"])}">\n'
                   if not re.search(r'<meta\b[^>]*name="description"', html) else "")
    canonical = (f'<link rel="canonical" href="{kit.BASE}/{name}">\n'
                 if not re.search(r'<link\b[^>]*rel="canonical"', html) else "")
    block = ("<!-- site-chrome:head -->\n" + description + canonical +
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
    """도구에 맞는 앱(tools.json 의 app). 목록과 같은 패널을 사용한다."""
    it = _tool_items()[lang].get(href)
    if not it or not it.get("app") or not pages.has_detail(it["app"]):
        return ""
    app = next(a for a in pages.load("apps.json")["apps"] if a["slug"] == it["app"])
    extra = ' lang="en"' if lang == "en" else ""
    return ('<section class="tool-related chrome-%s"%s>%s</section>'
            % (lang, extra, pages.app_pair(app, lang, compact=True)))


def _body(html, href):
    html = TOP_RE.sub("", html)
    html = BOTTOM_RE.sub("", html)
    html = PAIR_RE.sub("", html)
    if html.count("<body>\n") != 1 or html.count("</body>") != 1:
        _fail("<body> / </body> 가 정확히 하나여야 함")
    top = ('<!-- site-chrome:header -->\n<a class="skip chrome-ko" href="#main">본문으로 건너뛰기</a>\n'
           '<a class="skip chrome-en" href="#main" lang="en">Skip to content</a>\n'
           + _tag(kit.header("ko", {}, "/tools/"), "header", "ko") + "\n"
           + _tag(kit.header("en", {}, "/en/tools/"), "header", "en") + "\n<!-- /site-chrome:header -->")
    bottom = ("<!-- site-chrome:footer -->\n" + _tag(kit.footer("ko"), "footer", "ko") + "\n" + _tag(kit.footer("en"), "footer", "en")
              + "\n<!-- /site-chrome:footer -->")
    pair = ("\n<!-- site-chrome:app -->\n" + related("ko", href) + related("en", href)
            + "\n<!-- /site-chrome:app -->")
    if href == "/stage-sound-quiz.html":
        anchor = '\n    <div class="prose">'
        if html.count(anchor) != 1:
            _fail("문제풀이 소개 문단 위치가 정확히 하나여야 함")
        html = html.replace(anchor, pair + anchor, 1)
    else:
        html, n = TOOL_TOP_RE.subn(lambda m: m.group(1) + pair, html, count=1)
        if n != 1:
            _fail("상단 도구 제목 위치를 찾지 못함")
    html = html.replace("<body>\n", "<body>\n" + top + "\n", 1)
    return html.replace("</body>", bottom + "\n</body>", 1)


def _semantics(html, name):
    """Add document structure and label associations outside scripts only.

    Keep existing container tags/IDs and every script byte intact: tool code uses
    those nodes. Native labels also follow the tool's existing text translations.
    """
    html = html.replace(', maximum-scale=1.0', '')
    parts = re.split(r'(<script\b[^>]*>.*?</script>)', html, flags=re.S)
    has_main = 'id="main"' in html
    for i in range(0, len(parts), 2):
        part = parts[i]
        container = 'wrap' if name == 'stage-sound-quiz.html' else 'app'
        if not has_main and f'<div class="{container}">' in part:
            part = part.replace(f'<div class="{container}">',
                                f'<div class="{container}" id="main" role="main" tabindex="-1">', 1)
            has_main = True
        part = re.sub(r'<div class="title">(.*?)</div>', r'<h1 class="title">\1</h1>', part, count=1, flags=re.S)
        # A label followed immediately by its input, optionally in a row or
        # after the slider's current-value span. Never cross another control.
        label_text = r'((?:(?!</?label\b).)*?)'
        label_input = (r'<label(?![^>]*\bfor=)([^>]*)>' + label_text + r'</label>'
                       r'(\s*(?:<div class="(?:range-input-row|input-row)">\s*|'
                       r'<span class="slider-val"[^>]*>.*?</span></div>\s*)?)'
                       r'(<(?:input|select)\b[^>]*\bid="([^"]+)"[^>]*>)')
        part = re.sub(label_input, lambda m: f'<label for="{m[5]}"{m[1]}>{m[2]}</label>{m[3]}{m[4]}',
                      part, flags=re.S)
        # Button pickers are named groups rather than unassociated <label>s.
        group = (r'<label(?![^>]*\bid=)([^>]*)>' + label_text + r'</label>(\s*)'
                 r'<div class="(unit-toggle|tab-picker|solve-picker)" id="([^"]+)"')
        part = re.sub(group, lambda m: f'<span id="label-{m[5]}" class="control-label"{m[1]}>{m[2]}</span>{m[3]}'
                      f'<div class="{m[4]}" id="{m[5]}" role="group" aria-labelledby="label-{m[5]}"',
                      part, flags=re.S)
        if name == 'generator.html':
            part = part.replace('<div class="knob-label">Frequency</div>',
                                '<div class="knob-label" id="frequency-label">Frequency</div>')
            part = part.replace('id="freqInput" class=', 'id="freqInput" aria-labelledby="frequency-label" class=')
        if name == 'acoustics-calculator.html':
            part = part.replace('id="absorptionAlphaInput" value=',
                                'id="absorptionAlphaInput" aria-labelledby="label-absorptionPresetPicker" value=')
        parts[i] = part
    return ''.join(parts)


def _i18n_first(html):
    """I18N_DATA + i18n-core.js 쌍을 첫 인라인 본 <script> 바로 앞으로(이미 거기면 그대로)."""
    pairs = I18N_PAIR_RE.findall(html)
    if len(pairs) != 1:
        _fail("I18N_DATA + i18n-core.js 쌍(줄 맨 앞, 연속 두 줄)이 정확히 하나여야 함(%d개)" % len(pairs))
    html = I18N_PAIR_RE.sub("", html, count=1)
    ad = ADSENSE_RE.search(html)
    if not ad:
        _fail("AdSense async <script> 를 찾지 못함")
    main = INLINE_SCRIPT_RE.search(html, ad.end())
    if not main:
        _fail("AdSense 뒤에 인라인 본 <script> 가 없음")
    if html[main.start() - 1] != "\n":
        _fail("본 <script> 가 줄 맨 앞이 아님")
    return html[:main.start()] + pairs[0] + html[main.start():]


def transform(html, name):
    if name not in FILES:
        raise ValueError("알 수 없는 도구 파일: %r" % (name,))
    html = _retheme_style(html)
    html = _head(html, name)
    if name not in NO_I18N:
        html = _i18n_first(html)
    return _semantics(_body(html, "/" + name), name)


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
