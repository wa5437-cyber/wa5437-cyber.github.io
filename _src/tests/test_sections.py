import pathlib, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sitegen import sections, pages

CTX = {"contact": {"kakao": "https://open.kakao.com/o/x", "email": "a@b.kr"},
       "img_exists": lambda p: p == "/img/ok.jpg", "career": None}


class SectionTests(unittest.TestCase):
    def test_prose_escapes_and_renders_paragraphs(self):
        html = sections.render([{"type": "prose", "title": "T & U", "paragraphs": ["a <b>", "c"]}], "ko", CTX)
        self.assertIn("<h2>T &amp; U</h2>", html)
        self.assertIn("<p>a &lt;b&gt;</p>", html)
        self.assertEqual(html.count("<p>"), 2)

    def test_contact_has_kakao_and_email(self):
        html = sections.render([{"type": "contact", "title": "문의", "text": None}], "ko", CTX)
        self.assertIn('href="https://open.kakao.com/o/x"', html)
        self.assertIn('href="mailto:a@b.kr"', html)

    def test_photos_skip_missing_files_and_hide_empty_section(self):
        one = sections.render([{"type": "photos", "title": "사진", "items": [
            {"src": "/img/ok.jpg", "alt": "a"}, {"src": "/img/missing.jpg", "alt": "b"}]}], "ko", CTX)
        self.assertIn("/img/ok.jpg", one)
        self.assertNotIn("missing.jpg", one)
        none = sections.render([{"type": "photos", "title": "사진", "items": [
            {"src": "/img/missing.jpg", "alt": "b"}]}], "ko", CTX)
        self.assertEqual(none.strip(), "")

    def test_works_without_career_is_hidden(self):
        self.assertEqual(sections.render([{"type": "works", "title": "대표작"}], "ko", CTX).strip(), "")

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            sections.render([{"type": "nope"}], "ko", CTX)


class PluginsPageTests(unittest.TestCase):
    def test_plugins_page_ko_en(self):
        path, html = pages.simple_page("ko", "plugins")
        self.assertEqual(path, "/plugins/")
        self.assertIn('<html lang="ko">', html)
        self.assertIn("VST3", html)
        self.assertIn("open.kakao.com", html)
        path_en, html_en = pages.simple_page("en", "plugins")
        self.assertEqual(path_en, "/en/plugins/")
        self.assertIn('hreflang="ko"', html_en)

    def test_about_html_is_a_stub_pointing_to_new_about(self):
        text = (pages.ROOT / "about.html").read_text(encoding="utf-8")
        self.assertIn('rel="canonical" href="https://mlmusicstudio.co.kr/about/"', text)
        self.assertIn('http-equiv="refresh"', text)
        self.assertIn('href="/about/"', text)


CAREER = {"works": [
    {"year": 2020, "artist": "A", "title": "T1", "role": "믹싱", "church": False},
    {"year": 2021, "artist": "B", "title": None, "role": "녹음", "church": True},
    {"year": 2022, "artist": "C <b>&", "title": "X <b>&", "role": "마스터링", "church": False},
]}


class MoreSectionTests(unittest.TestCase):
    def test_list_cards_steps_facts_escape(self):
        e = "<i>&"
        html = sections.render([
            {"type": "list", "title": "L", "items": [e]},
            {"type": "cards", "title": None, "items": [{"title": e, "text": e}]},
            {"type": "steps", "title": "S", "items": [{"t": e, "d": e}]},
            {"type": "facts", "items": [e]}], "ko", CTX)
        self.assertNotIn("<i>", html)
        self.assertEqual(html.count("&lt;i&gt;&amp;"), 6)
        for cls in ('class="bullets"', 'class="cards c3"', 'class="steps"', 'class="facts"'):
            self.assertIn(cls, html)

    def test_contact_address_ko_en_and_map(self):
        ctx = dict(CTX, contact=dict(CTX["contact"], address={"ko": "서울 가", "en": "Seoul A"},
                                     map="https://map.example/x"))
        sec = [{"type": "contact", "title": "c", "text": "t"}]
        ko = sections.render(sec, "ko", ctx)
        en = sections.render(sec, "en", ctx)
        self.assertIn("서울 가", ko)
        self.assertNotIn("Seoul A", ko)
        self.assertIn("Seoul A", en)
        self.assertIn('href="https://map.example/x"', ko)
        self.assertIn("<p>t</p>", ko)
        self.assertNotIn("addr", sections.render(sec, "ko", CTX))

    def test_works_rows_escape_pill_and_labels(self):
        ctx = dict(CTX, career=CAREER)
        sec = [{"type": "works", "title": "대표작", "note": "n <b>"}]
        ko = sections.render(sec, "ko", ctx)
        self.assertIn("<caption>대표작</caption>", ko)
        for label in ("연도", "아티스트", "작품", "역할"):
            self.assertIn(f"<th>{label}</th>", ko)
        for v in ("2020", "2021", "2022", "T1", "믹싱", "녹음", "마스터링"):
            self.assertIn(v, ko)
        self.assertNotIn("<b>", ko)
        self.assertIn("C &lt;b&gt;&amp;", ko)
        self.assertIn("X &lt;b&gt;&amp;", ko)
        self.assertEqual(ko.count('class="pill"'), 1)
        self.assertIn("B <span class=\"pill\">교회·찬양</span>", ko)
        self.assertIn('<td data-label="작품"></td>', ko)
        self.assertIn('<p class="note">n &lt;b&gt;</p>', ko)
        en = sections.render(sec, "en", ctx)
        for label in ("Year", "Artist", "Work", "Role"):
            self.assertIn(f"<th>{label}</th>", en)
        self.assertIn("Worship", en)


class SitemapAndBuildTests(unittest.TestCase):
    def _sitemap(self, root):
        (root / "sitemap.xml").write_text(
            '<urlset>\n  <url><loc>https://mlmusicstudio.co.kr/about.html</loc></url>\n</urlset>\n', encoding="utf-8")
        return root / "sitemap.xml"

    def test_about_swap_only_when_new_page_built(self):
        with tempfile.TemporaryDirectory() as d:
            f = self._sitemap(pathlib.Path(d))
            pages.update_sitemap(d, ["/", "/plugins/"])
            t = f.read_text(encoding="utf-8")
            self.assertIn("/about.html<", t)
            self.assertNotIn("/about/<", t)
            pages.update_sitemap(d, ["/", "/about/"])
            pages.update_sitemap(d, ["/", "/about/"])
            t = f.read_text(encoding="utf-8")
            self.assertNotIn("/about.html<", t)
            self.assertEqual(t.count("/about/<"), 1)

    def test_build_all_skips_page_without_json(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(pages, "SIMPLE_PAGES", ("plugins", "nonexistent")):
                pages.build_all(d)
            root = pathlib.Path(d)
            self.assertTrue((root / "plugins" / "index.html").exists())
            self.assertTrue((root / "en" / "plugins" / "index.html").exists())
            self.assertFalse((root / "nonexistent").exists())
