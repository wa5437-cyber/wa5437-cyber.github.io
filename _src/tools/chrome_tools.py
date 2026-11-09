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
import json
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
INLINE_SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)(?![^>]*ld\+json)[^>]*>")   # JSON-LD 는 본 스크립트가 아니다

def _fail(msg):
    raise ValueError(msg)


def _retheme_style(html):
    def one(m):
        return m.group(1) + STYLE_RE.sub(lambda x: STYLE_MAP[x.group(0)], m.group(2)) + m.group(3)
    out, n = STYLE_BLOCK_RE.subn(one, html)
    if n < 1:
        _fail("<style> 블록이 없음")
    return out


# 검색 결과용 머리 정보(제목·설명·og·구조화 데이터). 이 표에 있는 파일만 제목·설명을 이 값으로 바꾸고,
# og·twitter·JSON-LD(WebApplication+BreadcrumbList)를 표시 블록 안에 넣는다. 설명에는 쪽에 실제로 있는 기능만 쓴다.
SEO = {
    "rta.html": ("실시간 RTA 분석기 — 마이크로 31밴드 스펙트럼 보기 | ML Music Studio", "RTA 실시간 분석기",
                 "기기 마이크로 들어오는 소리를 31밴드(ISO 266) 스펙트럼으로 실시간 표시합니다. 룸 특성 확인, 하울링 후보 찾기, 보정 사용법을 함께 정리했습니다."),
    "generator.html": ("신호 발생기 — 핑크·화이트 노이즈, 사인·사각·삼각파 | ML Music Studio", "신호 발생기",
                       "핑크·화이트 노이즈, 사인·사각·삼각파, 험·버즈·히스 신호를 내서 스피커와 신호 체인을 점검합니다. 신호별 듣는 법과 현장 점검 순서, 귀를 지키는 법을 안내합니다."),
    "electrical-calculator.html": ("전기 계산기 — 옴의 법칙·전력·임피던스·dB 환산 | ML Music Studio", "전기 계산기",
                                   "옴의 법칙, 전력, 임피던스, dB와 전력 환산, 케이블 전압 강하를 계산합니다. 탭별 입력 항목과 계산 방식, 숫자 예시, 흔한 실수를 함께 정리했습니다."),
    "acoustics-calculator.html": ("음향 계산기 — 주파수·파장·룸 모드·잔향(RT60) | ML Music Studio", "음향 계산기",
                                  "주파수·파장·주기와 음정, 룸 모드, 잔향(RT60)을 계산합니다. 탭별 계산 방식과 숫자 예시, 현장에서 쓰는 순서, 한계까지 설명합니다."),
    "delay-calculator.html": ("딜레이 계산기 — 시간·거리·위상·스피커 정렬 | ML Music Studio", "딜레이 계산기",
                              "딜레이 시간·거리·주파수·위상을 서로 환산하고 스피커 정렬을 점검합니다. 음속(온도), Haas 효과 참고표, 템포-딜레이 환산, 리버브 타임을 함께 봅니다."),
    "effects-listening.html": ("이펙트 듣기 훈련 — 리버브·딜레이·컴프레서 비교 청음 | ML Music Studio", "이펙트 듣기 훈련",
                               "Reverb·Delay·Chorus 등 이펙트 10종과 컴프레서·게이트·더킹을 켜고 끄며 비교해 듣습니다. 자유 청음, 청음 문제, 다이나믹스 모드로 귀를 훈련합니다."),
    "tempo-pitch-calculator.html": ("템포·피치 계산기 — 탭 템포·음표 길이·속도와 피치 | ML Music Studio", "템포·피치 계산기",
                                    "탭 템포, BPM별 음표 길이, 속도↔피치 환산, 루프 BPM 찾기, 마디 길이, 타임 스트레치, 샘플레이트까지 한 화면에서 계산합니다. 계산 문제 모드로 연습도 할 수 있는 무료 웹 도구입니다."),
}


def _seo_head(html, name):
    """SEO 표에 있는 파일의 제목·설명을 바꾸고, 표시 블록에 넣을 og·twitter·JSON-LD 를 돌려준다(없으면 빈 문자열)."""
    seo = SEO.get(name)
    if not seo:
        return html, ""
    title, short, desc = seo
    url = "%s/%s" % (kit.BASE, name)
    html, n1 = re.subn(r"<title>.*?</title>", lambda m: "<title>%s</title>" % kit.esc(title), html, count=1, flags=re.S)
    if n1 != 1:
        _fail("<title> 이 없음")
    html = re.sub(r'<meta name="description" content="[^"]*">\n?', "", html)   # 설명은 표시 블록 안에서 다시 넣는다
    ld = [{"@context": "https://schema.org", "@type": "WebApplication", "name": short, "description": desc,
           "applicationCategory": "UtilitiesApplication", "operatingSystem": "Any",
           "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "inLanguage": "ko", "url": url},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "ML Music Studio", "item": kit.BASE + "/"},
              {"@type": "ListItem", "position": 2, "name": "도구", "item": kit.BASE + "/tools/"},
              {"@type": "ListItem", "position": 3, "name": short, "item": url}]}]
    ld_text = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    extra = ('<meta name="description" content="%s">\n' % kit.esc(desc)
             + '<meta property="og:type" content="website"><meta property="og:site_name" content="ML Music Studio">\n'
             '<meta property="og:title" content="%s"><meta property="og:description" content="%s">\n'
             '<meta property="og:url" content="%s"><meta property="og:image" content="%s/og-image.png"><meta property="og:locale" content="ko_KR">\n'
             '<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="%s"><meta name="twitter:description" content="%s">\n'
             '<script type="application/ld+json">%s</script>\n'
             % (kit.esc(title), kit.esc(desc), url, kit.BASE, kit.esc(title), kit.esc(desc), ld_text))
    return html, extra


def _head(html, name):
    html, n = FONT_LINK_RE.subn('<link href="%s" rel="stylesheet">' % FONTS, html)
    if n != 1:
        _fail("Google Fonts <link> 가 정확히 하나여야 함(%d개)" % n)
    html = HEAD_RE.sub("", html)
    html, seo_extra = _seo_head(html, name)
    if html.count("</head>") != 1:
        _fail("</head> 가 정확히 하나여야 함")
    item = _tool_items()["ko"]["/" + name]
    description = (f'<meta name="description" content="{kit.esc(item["text"])}">\n'
                   if name not in SEO and not re.search(r'<meta\b[^>]*name="description"', html) else "")
    canonical = (f'<link rel="canonical" href="{kit.BASE}/{name}">\n'
                 if not re.search(r'<link\b[^>]*rel="canonical"', html) else "")
    block = ("<!-- site-chrome:head -->\n" + description + canonical + seo_extra +
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
