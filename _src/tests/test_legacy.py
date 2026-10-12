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
    """AdSense 줄, apps.apple.com 링크 줄, h1 줄(변환 전후 바이트 동일해야 함)."""
    return [l for l in text.split("\n") if "adsbygoogle" in l or "apps.apple.com" in l or "<h1" in l]


def ld_of(text):
    m = re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', text, re.S)
    return json.loads(m.group(1)) if m else None


DATES = json.loads((ROOT / "_src" / "content" / "guide_dates.json").read_text(encoding="utf-8"))
LD_KEEP = ("headline", "description", "inLanguage", "image", "publisher", "mainEntityOfPage", "@context", "@type")


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
        self.assertIn("%d년부터의 작업 기록이 있으며" % CAREER["since"], box)
        self.assertIn("기록된 작업 %d건" % CAREER["total"], box)
        self.assertIn('<a href="/about/">글쓴이 소개</a>', box)
        self.assertLess(self.out.index("<!-- /author-box -->"), self.out.index("</article>"))
        self.assertEqual(self.out.count("</article>"), 1)

    def test_dates_in_box_and_json_ld_from_guide_dates(self):
        d = {"gain-staging-basics": {"published": "2026-01-02", "modified": "2026-03-04"}}
        out = chrome_legacy.transform(self.raw, "guide", dates=d)
        self.assertIn("게시 2026-01-02 · 최종 수정 2026-03-04</p>", out)
        ld = ld_of(out)
        self.assertEqual((ld["datePublished"], ld["dateModified"]), ("2026-01-02", "2026-03-04"))
        same = {"gain-staging-basics": {"published": "2026-01-02", "modified": "2026-01-02"}}
        out2 = chrome_legacy.transform(self.raw, "guide", dates=same)
        self.assertIn("· 게시 2026-01-02</p>", out2)
        self.assertNotIn("최종 수정", out2)
        # 날짜를 바꿔 다시 적용해도 중복 키 없이 교체(멱등)
        again = chrome_legacy.transform(out, "guide", dates=same)
        self.assertEqual(again.count('"datePublished"'), 1)
        self.assertEqual(again, out2)

    def test_json_ld_author_person_and_other_fields_unchanged(self):
        before, after = ld_of(self.raw), ld_of(self.out)
        for k in LD_KEEP:
            self.assertEqual(after[k], before[k], k)
        self.assertEqual(after["author"], {"@type": "Person", "name": "이효섭", "url": "https://mlmusicstudio.co.kr/about/"})
        self.assertEqual(after["@type"], "Article")
        self.assertEqual(self.out.count('<script type="application/ld+json">'), 1)

    def test_missing_navcta_product_column_and_json_ld_raise(self):
        cases = (self.raw.replace('class="navcta"', 'class="cta"'),
                 self.raw.replace("<h4>Product</h4>", "<h4>Products</h4>"),
                 self.raw.replace('<script type="application/ld+json">', '<script type="text/plain">'),
                 self.raw.replace('"@type": "Article"', '"@type": "BlogPosting"'))
        for broken in cases:
            with self.assertRaises(ValueError):
                chrome_legacy.transform(broken, "guide")

    def test_missing_date_entry_raises(self):
        with self.assertRaises(ValueError):
            chrome_legacy.transform(self.raw, "guide", dates={})

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
            if self.kind(f) == "guide":
                slug = pathlib.Path(f).stem
                ld0, ld1 = ld_of(raw), ld_of(once)
                self.assertEqual(ld1["@type"], "Article", f)
                for k in LD_KEEP:
                    self.assertEqual(ld1[k], ld0[k], f + k)
                self.assertEqual(ld1["datePublished"], DATES[slug]["published"], f)
                self.assertEqual(ld1["dateModified"], DATES[slug]["modified"], f)
                self.assertEqual(ld1["author"]["@type"], "Person", f)
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


def strip_chrome(text):
    """메뉴 링크·푸터·글쓴이 박스·JSON-LD 를 걷어내고 옛 홈 앵커를 새 주소로 맞춘 본문 비교용 문자열."""
    text = re.sub(r'<div class="links">.*?</div>', "", text, flags=re.S)
    text = re.sub(r"<footer.*?</footer>", "", text, flags=re.S)
    text = re.sub(r"\n\n?[ \t]*<!-- author-box -->.*?<!-- /author-box -->", "", text, flags=re.S)
    text = re.sub(r'<script type="application/ld\+json">.*?</script>', "", text, flags=re.S)
    return text.replace('href="/#apps"', 'href="/apps/"').replace('href="/#tools"', 'href="/tools/"')


class BodyAndDatesTests(unittest.TestCase):
    def test_meta_line_and_json_ld_match_guide_dates_for_all_guides(self):
        for slug, d in DATES.items():
            text = src(slug + ".html")
            want = "게시 %s" % d["published"]
            if d["modified"] != d["published"]:
                want += " · 최종 수정 %s" % d["modified"]
            self.assertIn('<a href="/about/">글쓴이 소개</a> · %s</p>' % want, text, slug)
            ld = ld_of(text)
            self.assertEqual((ld["datePublished"], ld["dateModified"]), (d["published"], d["modified"]), slug)

    def test_only_chrome_changed_versus_pre_transform_commit(self):
        """변환 전 커밋(09605f1 의 부모)과 비교: 메뉴·푸터·박스·JSON-LD 를 걷어내면 본문이 같다."""
        for f in guide_files():
            name = pathlib.Path(f).name
            r = subprocess.run(["git", "show", "09605f1~1:guides/" + name], cwd=str(ROOT),
                               capture_output=True, text=True)
            if r.returncode != 0:
                self.skipTest("git 기록에서 변환 전 파일을 읽을 수 없음")
            self.assertEqual(strip_chrome(src(name)), strip_chrome(r.stdout), name)


class GuideDatesTests(unittest.TestCase):
    def test_pick_dates(self):
        import guide_dates
        added = [("2026-09-02", "가이드 추가", 1), ("2026-09-01", "가이드 3편 추가", 3)]
        touched = [("2026-10-12", "기존 가이드 25개에 새 메뉴·푸터 링크·글쓴이 박스 추가", 25),
                   ("2026-10-05", "앱스토어 링크에 캠페인 표시", 3),
                   ("2026-10-02", "컴프레서 설명 보강", 1),
                   ("2026-09-01", "가이드 3편 추가", 3)]
        self.assertEqual(guide_dates.pick_dates(added, touched), ("2026-09-01", "2026-10-02"))

    def test_pick_dates_all_mechanical_falls_back_to_published(self):
        import guide_dates
        added = [("2026-09-01", "커스텀 도메인 연결", 5)]
        touched = [("2026-10-05", "앱스토어 링크에 캠페인 표시", 3), ("2026-09-01", "커스텀 도메인 연결", 5)]
        self.assertEqual(guide_dates.pick_dates(added, touched), ("2026-09-01", "2026-09-01"))

    def test_mechanical_marker_and_bulk_size_and_promo_subject(self):
        import guide_dates
        added = [("2026-09-01", "가이드 추가", 1)]
        base = ("2026-09-01", "가이드 추가", 1)
        for subject, n in (("링크 정리 [mechanical]", 1), ("그냥 수정", 15), ("무대음향 앱 1.2 반영: 문항수", 2)):
            self.assertEqual(guide_dates.pick_dates(added, [("2026-10-01", subject, n), base]),
                             ("2026-09-01", "2026-09-01"), subject)
        self.assertEqual(guide_dates.pick_dates(added, [("2026-10-01", "그냥 수정", 14), base]),
                         ("2026-09-01", "2026-10-01"))

    def test_json_covers_every_guide_with_valid_dates(self):
        import datetime
        slugs = {pathlib.Path(f).stem for f in guide_files() if not f.endswith("/index.html")}
        self.assertEqual(set(DATES), slugs)
        for slug, d in DATES.items():
            pub = datetime.date.fromisoformat(d["published"])
            mod = datetime.date.fromisoformat(d["modified"])
            self.assertLessEqual(pub, mod, slug)


class CliTests(unittest.TestCase):
    def test_check_exits_zero_when_up_to_date(self):
        r = subprocess.run([sys.executable, str(ROOT / "_src" / "tools" / "chrome_legacy.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
