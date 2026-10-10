import pathlib, re, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sitegen import pages


class HomeTests(unittest.TestCase):
    def test_home_ko_and_en_paths_and_hash_redirect(self):
        path, html = pages.home("ko")
        self.assertEqual(path, "/")
        self.assertIn("location.replace('/policy.html'", html)
        self.assertIn("(policy|privacy)", html)
        path_en, html_en = pages.home("en")
        self.assertEqual(path_en, "/en/")
        self.assertIn('<html lang="en">', html_en)

    def test_home_has_three_cards_and_contact_links_free_of_made_up_hours(self):
        _, html = pages.home("ko")
        for word in ("앱", "플러그인", "녹음실", "웹 도구"):
            self.assertIn(word, html)
        self.assertNotIn("10:00", html)

    def test_home_links_point_to_existing_site_areas(self):
        _, html = pages.home("ko")
        for href in ('href="/apps/"', 'href="/studio/"', 'href="/tools/"'):
            self.assertIn(href, html)

    def test_home_ko_and_en_keep_google_site_verification_tags(self):
        pol = (pathlib.Path(__file__).resolve().parents[2] / "policy.html").read_text(encoding="utf-8")
        expected = re.findall(r'<meta name="google-site-verification" content="[^"]+" />', pol)
        self.assertEqual(len(expected), 2)
        for lang in ("ko", "en"):
            _, html = pages.home(lang)
            for tag in expected:
                self.assertIn(tag, html, lang)
            self.assertEqual(html.count('name="google-site-verification"'), 2, lang)

    def test_build_all_writes_home_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            pages.build_all(root)
            self.assertTrue((root / "index.html").exists())
            self.assertTrue((root / "en/index.html").exists())


class ToolsTests(unittest.TestCase):
    def test_tools_lists_every_existing_tool_page_once(self):
        _, html = pages.tools("ko")
        for f in ("/rta.html", "/generator.html", "/trainer.html", "/effects-listening.html",
                  "/delay-calculator.html", "/acoustics-calculator.html",
                  "/electrical-calculator.html", "/tempo-pitch-calculator.html", "/stage-sound-quiz.html"):
            self.assertEqual(html.count(f'href="{f}"'), 1, f)

    def test_prototype_page_is_not_listed(self):
        _, html = pages.tools("en")
        self.assertNotIn("eartrainer_prototype", html)

    def test_tools_paths(self):
        self.assertEqual(pages.tools("ko")[0], "/tools/")
        self.assertEqual(pages.tools("en")[0], "/en/tools/")


if __name__ == "__main__":
    unittest.main()
