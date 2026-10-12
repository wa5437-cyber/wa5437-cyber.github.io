#!/usr/bin/env python3
"""기존 가이드(guides/*.html)에 새 메뉴·푸터 링크·글쓴이 박스·사이트 글꼴을 넣는 멱등 변환기.

사용: chrome_legacy.py          guides/*.html 을 제자리 변환(바뀐 파일 수 출력)
      chrome_legacy.py --check  쓰지 않고, 변환이 필요한 파일이 있으면 종료코드 1
정규식·문자열 치환만 쓴다. 바꿀 자리가 파일에 없으면 ValueError(템플릿에서 벗어난 가이드를 알아채려고).
날짜는 content/guide_dates.json(guide_dates.py 가 git 기록에서 만든 것)만 읽고, 이 도구는 git 을 부르지 않는다.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CAREER = ROOT / "_src" / "content" / "career.json"
DATES = ROOT / "_src" / "content" / "guide_dates.json"
AUTHOR_LD = {"@type": "Person", "name": "이효섭", "url": "https://mlmusicstudio.co.kr/about/"}

MENU = [("/apps/", "Apps"), ("/tools/", "Tools"), ("/plugins/", "Plugins"),
        ("/studio/", "Studio"), ("/guides/", "Guides"), ("/about/", "About")]
COMPANY = [("/about/", "About"), ("/studio/", "Studio"), ("/privacy/", "Privacy"),
           ("/policy.html#policy", "App privacy policy"), ("/contact/", "Contact")]

# 사이트(_src/sitegen/kit.py 의 FONTS·THEME_COLOR)와 같은 글꼴·브라우저 색. 테스트가 두 값이 같은지 본다.
FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
         "&family=Noto+Sans+KR:wght@400;500;600;700&display=swap")
THEME_COLOR = "#f4f5f3"
FONT_LINK_RE = re.compile(r'<link href="https://fonts\.googleapis\.com/css2\?[^"]*" rel="stylesheet">')
THEME_RE = re.compile(r'<meta name="theme-color" content="#[0-9a-fA-F]{6}">')

AUTHOR_RE = re.compile(r"\n\n?[ \t]*<!-- author-box -->.*?<!-- /author-box -->(?=\n</article>)", re.S)


def _fail(msg):
    raise ValueError(msg)


def _menu(html):
    m = re.search(r'(<nav>.*?)(<div class="links">)(.*?)(</div>)', html, re.S)
    if not m:
        _fail('<nav> 안에 <div class="links"> 가 없음')
    current = 'aria-current="page"' in m.group(3)
    lines = []
    for href, label in MENU:
        cur = ' aria-current="page"' if current and href == "/guides/" else ""
        lines.append('      <a href="%s"%s>%s</a>' % (href, cur, label))
    new = m.group(2) + "\n" + "\n".join(lines) + "\n    " + m.group(4)
    html = html[:m.start(2)] + new + html[m.end(4):]
    cta, n = re.subn(r'(class="navcta" href=")/(?:#apps|apps/)(")', r"\1/apps/\2", html)
    if n != 1:
        _fail('navcta(href="/#apps") 링크를 찾지 못함')
    return cta


def _footer(html):
    m = re.search(r"<footer.*?</footer>", html, re.S)
    if not m:
        _fail("<footer> 가 없음")
    foot = m.group(0)
    if "<h4>Product</h4>" not in foot:
        _fail("푸터에 Product 열이 없음")
    foot = foot.replace('href="/#apps"', 'href="/apps/"').replace('href="/#tools"', 'href="/tools/"')
    if 'href="/apps/"' not in foot or 'href="/tools/"' not in foot:
        _fail("푸터 Product 열에 Apps/Tools 링크가 없음")
    col = re.search(r'(<h4>Company</h4>)(.*?)(\n    </div>)', foot, re.S)
    if not col:
        _fail("푸터에 Company 열이 없음")
    links = "".join('\n      <a href="%s">%s</a>' % c for c in COMPANY)
    foot = foot[:col.start(2)] + links + foot[col.end(2):]
    return html[:m.start()] + foot + html[m.end():]


def _head(html):
    """<head> 의 Google Fonts 링크와 theme-color 를 사이트와 같게."""
    html, n = FONT_LINK_RE.subn('<link href="%s" rel="stylesheet">' % FONTS, html)
    if n != 1:
        _fail("Google Fonts <link> 가 정확히 하나여야 함(%d개)" % n)
    html, n = THEME_RE.subn('<meta name="theme-color" content="%s">' % THEME_COLOR, html)
    if n != 1:
        _fail('<meta name="theme-color"> 가 정확히 하나여야 함(%d개)' % n)
    return html


def _body_anchors(html):
    """본문 안 옛 홈 앵커 링크(예: 앱 카드의 '자세히 보기')도 새 주소로."""
    return html.replace('href="/#apps"', 'href="/apps/"').replace('href="/#tools"', 'href="/tools/"')


def _career():
    return json.loads(CAREER.read_text(encoding="utf-8"))


def _slug(html):
    m = re.search(r'<link rel="canonical" href="https://mlmusicstudio\.co\.kr/guides/([^"/]+)\.html">', html)
    if not m:
        _fail("canonical 링크에서 가이드 slug 를 찾지 못함")
    return m.group(1)


def _dates(html, dates):
    slug = _slug(html)
    if dates is None:
        dates = json.loads(DATES.read_text(encoding="utf-8"))
    if slug not in dates:
        _fail("guide_dates.json 에 %s 항목이 없음(guide_dates.py 를 다시 실행)" % slug)
    return dates[slug]["published"], dates[slug]["modified"]


def _inline(v):
    """원래 파일 모양: 중첩 객체는 한 줄 `{ "k": v, ... }`."""
    if isinstance(v, dict):
        return "{ " + ", ".join("%s: %s" % (json.dumps(k, ensure_ascii=False), _inline(x)) for k, x in v.items()) + " }"
    return json.dumps(v, ensure_ascii=False)


def _dump_ld(d):
    rows = ["  %s: %s" % (json.dumps(k, ensure_ascii=False), _inline(v)) for k, v in d.items()]
    return "{\n" + ",\n".join(rows) + "\n}"


def _json_ld(html, published, modified):
    m = re.search(r'(<script type="application/ld\+json">\n)(.*?)(\n</script>)', html, re.S)
    if not m:
        _fail("JSON-LD 블록이 없음")
    try:
        ld = json.loads(m.group(2))
    except ValueError as e:
        _fail("JSON-LD 를 읽을 수 없음: %s" % e)
    if ld.get("@type") != "Article":
        _fail('JSON-LD @type 이 "Article" 이 아님')
    if "author" not in ld:
        _fail("JSON-LD 에 author 가 없음")
    ordered = {}
    for k, v in ld.items():  # 날짜는 author 바로 앞에, 나머지 순서는 그대로
        if k in ("datePublished", "dateModified"):
            continue
        if k == "author":
            ordered["datePublished"], ordered["dateModified"] = published, modified
            v = dict(AUTHOR_LD)
        ordered[k] = v
    return html[:m.start(2)] + _dump_ld(ordered) + html[m.end(2):]


def _author_box(published, modified):
    c = _career()
    when = "게시 %s" % published if modified == published else "게시 %s · 최종 수정 %s" % (published, modified)
    return "\n".join([
        "  <!-- author-box -->",
        '  <aside class="author-box" aria-label="글쓴이">',
        '    <div class="who"><strong>이효섭</strong> · 사운드 엔지니어</div>',
        "    <p>%d년부터 기록한 작업이 %d건이며, 현장에서 쓰는 앱과 웹 도구를 만듭니다.</p>"
        % (c["since"], c["total"]),
        '    <p class="meta"><a href="/about/">글쓴이 소개</a> · %s</p>' % when,
        "  </aside>",
        "  <!-- /author-box -->",
    ])


def transform(html, kind, dates=None):
    if kind not in ("guide", "guides-index"):
        raise ValueError("알 수 없는 kind: %r" % (kind,))
    html = _head(html)
    html = _menu(html)
    html = _footer(html)
    html = _body_anchors(html)
    html = AUTHOR_RE.sub("", html) if kind == "guide" else html
    if kind == "guide":
        if html.count("\n</article>") != 1:
            _fail("</article> 가 줄 머리에 정확히 한 번 있어야 함")
        pub, mod = _dates(html, dates)
        # 박스 앞에 빈 줄 하나(관련 글 블록과 구분)
        html = html.replace("\n</article>", "\n\n" + _author_box(pub, mod) + "\n</article>")
        html = _json_ld(html, pub, mod)
    elif "author-box" in html:
        _fail("guides-index 에 글쓴이 박스가 있음")
    return html


def _kind(path):
    return "guides-index" if path.name == "index.html" else "guide"


def run(check=False, root=ROOT):
    changed = []
    for path in sorted((root / "guides").glob("*.html")):
        old = path.read_text(encoding="utf-8")
        try:
            new = transform(old, _kind(path))
        except ValueError as e:
            raise ValueError("%s: %s" % (path.name, e))
        if new != old:
            changed.append(path.name)
            if not check:
                path.write_text(new, encoding="utf-8")
    return changed


def main(argv):
    check = "--check" in argv
    changed = run(check=check)
    if check:
        for n in changed:
            print("변환 필요: guides/%s" % n)
        return 1 if changed else 0
    print("바뀐 파일 %d개" % len(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
