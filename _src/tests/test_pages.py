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

    def test_tools_links_exam_to_detail_page_and_others_to_apps_index(self):
        for lang, pre in (("ko", ""), ("en", "/en")):
            _, html = pages.tools(lang)
            self.assertIn(f'href="{pre}/apps/stage-sound/"', html, lang)
            self.assertIn(f'href="{pre}/apps/"', html, lang)
            for slug in ("spl-rta", "ear-trainer", "toolkit"):
                self.assertNotIn(f'href="{pre}/apps/{slug}/"', html, lang)


class AppsTests(unittest.TestCase):
    def test_apps_index_lists_all_apps_with_pages_only_for_detailed_ones(self):
        _, html = pages.apps_index("ko")
        self.assertIn("무대음향 자격증 기출문제", html)
        self.assertIn('href="/apps/stage-sound/"', html)
        self.assertNotIn('href="/apps/spl-rta/"', html)   # 상세 페이지는 아직 없음

    def test_stage_sound_page_uses_only_known_facts_and_campaign_links(self):
        path, html = pages.app_page("ko", "stage-sound")
        self.assertEqual(path, "/apps/stage-sound/")
        self.assertIn("2,174", html)
        self.assertIn("pt=129167489&amp;ct=homepage&amp;mt=8", html)
        self.assertIn("play.google.com/store/apps/details?id=com.mlmusicstudio.stagesoundexam", html)
        for banned in ("광고 없음", "오프라인", "No ads", "offline"):
            self.assertNotIn(banned, html)

    def test_stage_sound_pages_make_no_score_trend_claim(self):
        for lang in ("ko", "en"):
            _, html = pages.app_page(lang, "stage-sound")
            self.assertNotIn("점수 추이", html, lang)
            self.assertNotIn("score trend", html.lower(), lang)

    def test_stage_sound_page_en_exists_with_alternates(self):
        path, html = pages.app_page("en", "stage-sound")
        self.assertEqual(path, "/en/apps/stage-sound/")
        self.assertIn('hreflang="ko" href="https://mlmusicstudio.co.kr/apps/stage-sound/"', html)


class SitemapTests(unittest.TestCase):
    def test_update_adds_missing_urls_once_and_keeps_existing(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "sitemap.xml").write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                '<url><loc>https://mlmusicstudio.co.kr/guides/</loc></url>\n</urlset>\n', encoding="utf-8")
            pages.update_sitemap(root, ["/", "/apps/", "/apps/"])
            text = (root / "sitemap.xml").read_text(encoding="utf-8")
            self.assertEqual(text.count("<loc>https://mlmusicstudio.co.kr/apps/</loc>"), 1)
            self.assertIn("<loc>https://mlmusicstudio.co.kr/guides/</loc>", text)
            self.assertIn("<loc>https://mlmusicstudio.co.kr/</loc>", text)


if __name__ == "__main__":
    unittest.main()
