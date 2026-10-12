import pathlib, sys, unittest
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
