#!/usr/bin/env python3
"""기존 가이드(guides/*.html)에 새 메뉴·푸터 링크·글쓴이 박스를 넣는 멱등 변환기.

사용: chrome_legacy.py          guides/*.html 을 제자리 변환(바뀐 파일 수 출력)
      chrome_legacy.py --check  쓰지 않고, 변환이 필요한 파일이 있으면 종료코드 1
정규식·문자열 치환만 쓴다. 바꿀 자리가 파일에 없으면 ValueError(템플릿에서 벗어난 가이드를 알아채려고).
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CAREER = ROOT / "_src" / "content" / "career.json"

MENU = [("/apps/", "Apps"), ("/tools/", "Tools"), ("/plugins/", "Plugins"),
        ("/studio/", "Studio"), ("/guides/", "Guides"), ("/about/", "About")]
COMPANY = [("/about/", "About"), ("/studio/", "Studio"), ("/privacy/", "Privacy"),
           ("/policy.html#policy", "App privacy policy"), ("/contact/", "Contact")]

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


def _body_anchors(html):
    """본문 안 옛 홈 앵커 링크(예: 앱 카드의 '자세히 보기')도 새 주소로."""
    return html.replace('href="/#apps"', 'href="/apps/"').replace('href="/#tools"', 'href="/tools/"')


def _career():
    return json.loads(CAREER.read_text(encoding="utf-8"))


def _modified(html):
    for key in ("dateModified", "datePublished"):
        m = re.search(r'"%s"\s*:\s*"(\d{4}-\d{2}-\d{2})' % key, html)
        if m:
            return m.group(1)
    return None


def _author_box(html):
    c = _career()
    mod = _modified(html)
    tail = " · 최종 수정 %s" % mod if mod else ""
    return "\n".join([
        "  <!-- author-box -->",
        '  <aside class="author-box" aria-label="글쓴이">',
        '    <div class="who"><strong>이효섭</strong> · 사운드 엔지니어</div>',
        "    <p>%d년부터 믹싱·마스터링·녹음 작업을 하고 있으며(기록된 작업 %d건), 현장에서 쓰는 앱과 웹 도구를 만듭니다.</p>"
        % (c["since"], c["total"]),
        '    <p class="meta"><a href="/about/">글쓴이 소개</a>%s</p>' % tail,
        "  </aside>",
        "  <!-- /author-box -->",
    ])


def transform(html, kind):
    if kind not in ("guide", "guides-index"):
        raise ValueError("알 수 없는 kind: %r" % (kind,))
    html = _menu(html)
    html = _footer(html)
    html = _body_anchors(html)
    html = AUTHOR_RE.sub("", html) if kind == "guide" else html
    if kind == "guide":
        if html.count("\n</article>") != 1:
            _fail("</article> 가 줄 머리에 정확히 한 번 있어야 함")
        # 박스 앞에 빈 줄 하나(관련 글 블록과 구분)
        html = html.replace("\n</article>", "\n\n" + _author_box(html) + "\n</article>")
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
