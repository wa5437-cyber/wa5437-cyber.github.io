import glob, json, pathlib, re, subprocess, sys, unittest
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_src" / "tools"))
import chrome_legacy  # noqa: E402

SAMPLE = ROOT / "guides" / "gain-staging-basics.html"
VOID = {"meta", "link", "br", "img", "hr", "input", "source", "wbr", "col", "area", "base", "embed", "track"}
NEW_MENU = ("/apps/", "/tools/", "/plugins/", "/studio/", "/guides/", "/about/")
CAREER = json.loads((ROOT / "_src" / "content" / "career.json").read_text(encoding="utf-8"))


class Balance(HTMLParser):
    """publish_guide.py 의 Balance 와 같은 열린/닫힌 태그 스택 검사."""
    def __init__(self):
        super().__init__()
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append("</%s> 앞에서 태그 불일치 (열린 태그: %s)" % (tag, self.stack[-3:]))
        else:
            self.stack.pop()


def balanced_errors(text):
    p = Balance()
    p.feed(text)
    return p.errors + (["닫히지 않은 태그: %s" % p.stack] if p.stack else [])


def src(name):
    return (ROOT / "guides" / name).read_text(encoding="utf-8")


def protected_lines(text):
    """JSON-LD 블록, AdSense 줄, apps.apple.com 링크 줄, h1 줄."""
    ld = re.findall(r'<script type="application/ld\+json">.*?</script>', text, re.S)
    lines = [l for l in text.split("\n") if "adsbygoogle" in l or "apps.apple.com" in l or "<h1" in l]
    return ld, lines


def guide_files():
    return sorted(glob.glob(str(ROOT / "guides" / "*.html")))


class TransformSampleTests(unittest.TestCase):
    def setUp(self):
        self.raw = SAMPLE.read_text(encoding="utf-8")
        self.out = chrome_legacy.transform(self.raw, "guide")

    def test_idempotent(self):
        self.assertEqual(chrome_legacy.transform(self.out, "guide"), self.out)
        self.assertEqual(chrome_legacy.transform(self.raw, "guide"), self.out)

    def test_new_menu_has_six_links_and_guides_stays_current(self):
        links = re.search(r'<div class="links">(.*?)</div>', self.out, re.S).group(1)
        self.assertEqual(re.findall(r'href="([^"]+)"', links), list(NEW_MENU))
        self.assertIn('<a href="/guides/" aria-current="page">Guides</a>', links)
        self.assertEqual(links.count("aria-current"), 1)
        self.assertIn('<a class="navcta" href="/apps/">', self.out)

    def test_old_anchors_gone(self):
        self.assertNotIn('href="/#', self.out)
        self.assertNotIn("/about.html", self.out)
        self.assertNotIn("mailto:", self.out)

    def test_footer_links(self):
        footer = re.search(r"<footer.*?</footer>", self.out, re.S).group(0)
        for href in ("/apps/", "/tools/", "/guides/", "/about/", "/studio/", "/privacy/",
                     "/policy.html#policy", "/contact/"):
            self.assertIn('href="%s"' % href, footer)

    def test_author_box_once_with_career_numbers_before_article_end(self):
        self.assertEqual(self.out.count('class="author-box"'), 1)
        self.assertEqual(self.out.count("<!-- author-box -->"), 1)
        self.assertEqual(self.out.count("<!-- /author-box -->"), 1)
        box = re.search(r"<!-- author-box -->.*?<!-- /author-box -->", self.out, re.S).group(0)
        self.assertIn("%d년부터" % CAREER["since"], box)
        self.assertIn("기록된 작업 %d건" % CAREER["total"], box)
        self.assertIn('<a href="/about/">글쓴이 소개</a>', box)
        self.assertLess(self.out.index("<!-- /author-box -->"), self.out.index("</article>"))
        self.assertEqual(self.out.count("</article>"), 1)

    def test_modified_date_only_from_json_ld(self):
        no_date = chrome_legacy.transform(self.raw, "guide")
        self.assertNotIn("최종 수정", no_date)
        with_mod = self.raw.replace('"inLanguage": "ko",', '"inLanguage": "ko",\n  "datePublished": "2026-01-02",\n  "dateModified": "2026-03-04T10:00:00+09:00",')
        self.assertIn("최종 수정 2026-03-04", chrome_legacy.transform(with_mod, "guide"))
        only_pub = self.raw.replace('"inLanguage": "ko",', '"inLanguage": "ko",\n  "datePublished": "2026-01-02",')
        self.assertIn("최종 수정 2026-01-02", chrome_legacy.transform(only_pub, "guide"))

    def test_protected_lines_identical(self):
        self.assertEqual(protected_lines(self.out), protected_lines(self.raw))

    def test_balanced(self):
        self.assertEqual(balanced_errors(self.out), [])
        for tag in ("aside", "div", "nav", "footer"):
            self.assertEqual(len(re.findall(r"<%s[\s>]" % tag, self.out)), self.out.count("</%s>" % tag), tag)

    def test_missing_pattern_raises_value_error(self):
        for broken in (self.raw.replace('<div class="links">', '<div class="menu">'),
                       self.raw.replace("<h4>Company</h4>", "<h4>Firm</h4>"),
                       self.raw.replace("</article>", "")):
            with self.assertRaises(ValueError):
                chrome_legacy.transform(broken, "guide")
        with self.assertRaises(ValueError):
            chrome_legacy.transform(self.raw, "unknown-kind")


class GuidesIndexTests(unittest.TestCase):
    def test_index_has_no_author_box_but_new_chrome(self):
        raw = src("index.html")
        out = chrome_legacy.transform(raw, "guides-index")
        self.assertNotIn("author-box", out)
        self.assertNotIn('href="/#', out)
        self.assertIn('href="/studio/"', out)
        self.assertEqual(chrome_legacy.transform(out, "guides-index"), out)
        self.assertEqual(protected_lines(out), protected_lines(raw))


class AllGuidesTests(unittest.TestCase):
    def kind(self, path):
        return "guides-index" if path.endswith("/index.html") else "guide"

    def test_25_files(self):
        self.assertEqual(len(guide_files()), 25)

    def test_every_guide_is_transformed_on_disk(self):
        """리포지토리에 있는 파일이 이미 변환된 상태(--check 와 같은 뜻)."""
        for f in guide_files():
            text = pathlib.Path(f).read_text(encoding="utf-8")
            self.assertEqual(chrome_legacy.transform(text, self.kind(f)), text, f)

    def test_idempotent_balanced_protected_for_all(self):
        for f in guide_files():
            raw = pathlib.Path(f).read_text(encoding="utf-8")
            once = chrome_legacy.transform(raw, self.kind(f))
            self.assertEqual(chrome_legacy.transform(once, self.kind(f)), once, f)
            self.assertEqual(balanced_errors(once), [], f)
            self.assertEqual(protected_lines(once), protected_lines(raw), f)
            self.assertNotIn('href="/#', once, f)
            self.assertEqual(once.count('class="author-box"'), 0 if self.kind(f) == "guides-index" else 1, f)

    def test_disk_guides_balanced_like_publish_guide(self):
        for f in guide_files():
            self.assertEqual(balanced_errors(pathlib.Path(f).read_text(encoding="utf-8")), [], f)

    def test_guide_urls_preserved(self):
        for f in guide_files():
            raw = pathlib.Path(f).read_text(encoding="utf-8")
            out = chrome_legacy.transform(raw, self.kind(f))
            self.assertEqual(set(re.findall(r'href="(/guides/[^"]+)"', raw)) - {"/guides/"},
                             set(re.findall(r'href="(/guides/[^"]+)"', out)) - {"/guides/"}, f)


class CliTests(unittest.TestCase):
    def test_check_exits_zero_when_up_to_date(self):
        r = subprocess.run([sys.executable, str(ROOT / "_src" / "tools" / "chrome_legacy.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
