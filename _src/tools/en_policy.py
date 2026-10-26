#!/usr/bin/env python3
"""policy.html(한국어 원본)에서 영어판 en/policy.html 을 만든다. 사용: python3 _src/tools/en_policy.py

본문은 policy.html 의 I18N 표(en)를 그대로 정적 HTML 로 박는다. 앱스토어의 한국어 밖 지역이 링크할 수 있도록
JS 없이도 영어로 보이고, 언어 메뉴는 그대로 둔다(고르지 않았으면 영어). policy.html 을 고치면 이것을 다시 돌린다.
"""
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC, OUT = ROOT / "policy.html", ROOT / "en" / "policy.html"
EL = re.compile(r'<(\w+)([^>]*?)data-i18n="([^"]+)"([^>]*)>(.*?)</\1>', re.S)

TITLE = "Privacy Policy — ML Music Studio"
DESC = ("Privacy policy for ML Music Studio apps and website: what each app collects, ads and affiliate links, "
        "third-party sharing, and how to contact us.")
OG_DESC = "Privacy policy for ML Music Studio apps and website."

# (원문, 영어판) — 정확히 한 번씩 있어야 한다
SWAPS = [
    ('<html lang="ko">', '<html lang="en">'),
    ("<title>개인정보처리방침 — ML Music Studio</title>", f"<title>{TITLE}</title>"),
    ('<link rel="canonical" href="https://mlmusicstudio.co.kr/policy.html">',
     '<link rel="canonical" href="https://mlmusicstudio.co.kr/en/policy.html">'),
    ('<meta property="og:url" content="https://mlmusicstudio.co.kr/policy.html">',
     '<meta property="og:url" content="https://mlmusicstudio.co.kr/en/policy.html">'),
    ('<meta property="og:title" content="개인정보처리방침 — ML Music Studio">',
     f'<meta property="og:title" content="{TITLE}">'),
    ('<meta property="og:description" content="ML Music Studio 앱과 웹사이트의 개인정보처리방침입니다.">',
     f'<meta property="og:description" content="{OG_DESC}">'),
    ('<meta property="og:locale" content="ko_KR">', '<meta property="og:locale" content="en_US">'),
    ('<meta property="og:locale:alternate" content="en_US">', '<meta property="og:locale:alternate" content="ko_KR">'),
    ('<meta name="twitter:title" content="개인정보처리방침 — ML Music Studio">', f'<meta name="twitter:title" content="{TITLE}">'),
    ('<meta name="twitter:description" content="ML Music Studio 앱과 웹사이트의 개인정보처리방침입니다.">',
     f'<meta name="twitter:description" content="{OG_DESC}">'),
    ('"description": "사운드 엔지니어를 위한 iOS 앱과 무료 웹 도구를 만드는 1인 개발 스튜디오."',
     '"description": "A one-person studio making iOS apps and free web tools for sound engineers."'),
    ('"name": "ML Music Studio 앱"', '"name": "ML Music Studio apps"'),
    ('"name": "무대음향 자격증 기출문제"', '"name": "Stage Sound Exam Prep (Korea)"'),
    ('"name": "NORA — 커버곡 노래 녹음"', '"name": "NORA: Cover Song Studio"'),
    ('"name": "Patch & I/O — 인아웃 리스트"', '"name": "Patch & I/O — Stage I/O List"'),
    ('"name": "TempoScope — 템포·키·코드 자동 감지"', '"name": "TempoScope"'),
    ('"name": "SheetScope — 악보 사진·PDF 를 MusicXML·미디로"', '"name": "SheetScope"'),
    ('<span id="langSwitchLabel">한국어</span>', '<span id="langSwitchLabel">English</span>'),
    ('if (!SUPPORTED_LANGS.includes(lang)) lang = "ko";', 'if (!SUPPORTED_LANGS.includes(lang)) lang = "en";'),
    ("const val = entry[lang] || entry.ko;", "const val = entry[lang] || entry.en || entry.ko;"),
]
# 영어판은 브라우저 언어로 바꾸지 않는다: 직접 고른 언어(siteLang)가 없으면 영어
DETECT = re.compile(r"(function detectLang\(\)\{.*?catch\(e\) \{\}\n)(.*?)(\n  \})", re.S)
# 사이트 안 링크는 영어 쪽이 있는 곳만 영어 쪽으로
LINKS = [('href="/apps/"', 'href="/en/apps/"'), ('href="/tools/"', 'href="/en/tools/"'),
         ('href="/about.html"', 'href="/en/about/"')]


def build(text):
    m = re.search(r"const I18N = (\{.*?\});\n", text, re.S)
    i18n = json.loads(m.group(1))
    for a, b in SWAPS:
        assert text.count(a) == 1, a
        text = text.replace(a, b)
    text = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{DESC}">', text, count=1)
    text, n = DETECT.subn(lambda mm: mm.group(1) + "    return 'en';" + mm.group(3), text)
    assert n == 1, "detectLang"
    head, tail = text.split("<script>\n  const I18N", 1)

    def en(mm):
        key = mm.group(3)
        val = (i18n.get(key) or {}).get("en")
        if val is None:
            return mm.group(0)
        is_html = "data-i18n-html" in mm.group(2) + mm.group(4)
        inner = val if is_html else html.escape(val, quote=False)
        return f'<{mm.group(1)}{mm.group(2)}data-i18n="{key}"{mm.group(4)}>{inner}</{mm.group(1)}>'

    head = EL.sub(en, head)
    for a, b in LINKS:
        head = head.replace(a, b)
    return head + "<script>\n  const I18N" + tail


def main():
    OUT.write_text(build(SRC.read_text(encoding="utf-8")), encoding="utf-8")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
