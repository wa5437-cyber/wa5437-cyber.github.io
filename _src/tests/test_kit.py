import pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sitegen import kit


class KitTests(unittest.TestCase):
    def test_esc_escapes_quotes_and_amp(self):
        self.assertEqual(kit.esc('a & "b" <c>'), "a &amp; &quot;b&quot; &lt;c&gt;")

    def test_url_ko_is_unchanged_and_en_gets_prefix(self):
        self.assertEqual(kit.url("ko", "/apps/"), "/apps/")
        self.assertEqual(kit.url("en", "/apps/"), "/en/apps/")
        self.assertEqual(kit.url("en", "/"), "/en/")

    def test_write_folder_url_creates_index_html(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            kit.write(root, "/en/apps/", "<p>x</p>")
            self.assertEqual((root / "en/apps/index.html").read_text(encoding="utf-8"), "<p>x</p>")
            kit.write(root, "/policy.html", "<p>y</p>")
            self.assertTrue((root / "policy.html").exists())


    def test_header_lists_nav_and_only_existing_language_alternates(self):
        h = kit.header("ko", "/tools/", {"ko": "/tools/", "en": "/en/tools/"})
        for label in ("앱", "웹 도구", "플러그인", "녹음실", "가이드"):
            self.assertIn(label, h)
        self.assertIn('href="/en/tools/"', h)
        self.assertNotIn("/ja/", h)

    def test_page_has_hreflang_canonical_and_skip_link(self):
        html = kit.page("en", "/en/", "T", "D", "<main>b</main>", {"ko": "/", "en": "/en/"})
        self.assertIn('<html lang="en">', html)
        self.assertIn('rel="canonical" href="https://mlmusicstudio.co.kr/en/"', html)
        self.assertIn('hreflang="ko" href="https://mlmusicstudio.co.kr/"', html)
        self.assertIn('hreflang="x-default"', html)
        self.assertIn("#main", html)


if __name__ == "__main__":
    unittest.main()
