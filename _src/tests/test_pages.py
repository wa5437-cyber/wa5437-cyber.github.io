import json, pathlib, re, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sitegen import pages, kit


class HomeTests(unittest.TestCase):
    def test_home_ko_and_en_paths_and_hash_redirect(self):
        path, html = pages.home("ko")
        self.assertEqual(path, "/")
        self.assertIn("location.replace(u)", html)
        path_en, html_en = pages.home("en")
        self.assertEqual(path_en, "/en/")
        self.assertIn('<html lang="en">', html_en)

    def test_old_anchor_map_is_in_ko_home_only_and_targets_exist(self):
        _, ko = pages.home("ko")
        _, en = pages.home("en")
        for key, target in pages.HASH_MAP.items():
            self.assertIn(json.dumps(key) + ":" + json.dumps(target), ko)
        self.assertEqual(ko.count("location.replace"), 1)
        self.assertNotIn("location.replace", en)
        self.assertNotIn("/policy.html#policy", en)
        for key in ("policy", "privacy", "apps", "download", "tools", "guides"):
            self.assertIn(key, pages.HASH_MAP)
        from sitegen import check
        for target in pages.HASH_MAP.values():
            self.assertTrue(check.exists(pages.ROOT, target.split("#")[0]), target)

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


class PolicyPageTests(unittest.TestCase):
    def test_policy_has_charset_first_and_its_own_og_url(self):
        text = (pathlib.Path(__file__).resolve().parents[2] / "policy.html").read_text(encoding="utf-8")
        head = text[text.index("<head>"):]
        self.assertLess(head.index('<meta charset="UTF-8">'), head.index('<meta name="robots"'))
        self.assertIn('<meta property="og:url" content="https://mlmusicstudio.co.kr/policy.html">', text)
        self.assertNotIn('<meta property="og:url" content="https://mlmusicstudio.co.kr/">', text)


class HomeExtrasTests(unittest.TestCase):
    def jsonld(self, html):
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        self.assertTrue(blocks)
        out = []
        for b in blocks:
            data = json.loads(b)
            out += data if isinstance(data, list) else [data]
        return out

    def test_home_has_organization_and_website_json_ld_in_both_languages(self):
        for lang in ("ko", "en"):
            _, html = pages.home(lang)
            items = {d["@type"]: d for d in self.jsonld(html)}
            self.assertEqual(set(items), {"Organization", "WebSite"}, lang)
            self.assertEqual(items["Organization"]["name"], "ML Music Studio")
            self.assertEqual(items["Organization"]["logo"], "https://mlmusicstudio.co.kr/og-image.png")
            self.assertEqual(items["WebSite"]["inLanguage"], lang)
            self.assertEqual(items["WebSite"]["url"], "https://mlmusicstudio.co.kr/")

    def test_ko_home_keeps_hash_redirect_next_to_json_ld(self):
        _, html = pages.home("ko")
        self.assertIn('"policy":"/policy.html#policy"', html)
        self.assertIn("location.replace(u)", html)
        self.assertNotIn("location.replace", pages.home("en")[1])

    def test_en_home_marks_guides_as_korean(self):
        _, html = pages.home("en")
        self.assertIn("Latest guides (in Korean)", html)

    def test_home_guide_cards_end_with_ellipsis_when_truncated(self):
        _, html = pages.home("ko")
        ps = re.findall(r'<a class="card" href="/guides/[^"]+"[^>]*><h3>.*?</h3><p>(.*?)</p>', html, re.S)
        self.assertTrue(ps)
        for p in ps:
            self.assertLessEqual(len(p), 111)
        self.assertTrue(any(p.endswith("…") for p in ps))


class ShortTests(unittest.TestCase):
    def test_short_string_is_unchanged(self):
        self.assertEqual(pages.short("짧은 문장입니다."), "짧은 문장입니다.")
        self.assertEqual(pages.short("x" * 110), "x" * 110)

    def test_long_korean_cut_at_word_boundary_with_ellipsis(self):
        src = "무대음향 자격증 시험을 준비하는 분들을 위해 기출문제와 모의고사 그리고 오답노트 기능을 한 곳에 모았습니다"
        out = pages.short(src, 40)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 41)
        last = out[:-1].split(" ")[-1]
        self.assertIn(last, src.split(" "))

    def test_trailing_punctuation_is_stripped_before_ellipsis(self):
        out = pages.short("가나다 라마바, 사아자 차카타", 10)
        self.assertFalse(out[:-1].endswith((",", " ", ".")))
        self.assertTrue(out.endswith("…"))

    def test_no_space_falls_back_to_hard_cut(self):
        self.assertEqual(pages.short("가" * 50, 10), "가" * 10 + "…")


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

    def test_stage_sound_hero_uses_short_lead_not_long_description(self):
        for lang in ("ko", "en"):
            _, html = pages.app_page(lang, "stage-sound")
            sub = re.search(r'<p class="sub">(.*?)</p>', html, re.S).group(1)
            lead = pages.load("apps.json")["details"]["stage-sound"]["lead"][lang]
            self.assertEqual(sub, kit.esc(lead), lang)
            self.assertLess(len(sub), 120, lang)
        self.assertIn("무대예술전문인(음향) 1·2·3급 필기시험을 기출문제로 준비하는 앱입니다.",
                      pages.app_page("ko", "stage-sound")[1])

    def test_stage_sound_wrongnote_block_wording(self):
        _, html = pages.app_page("ko", "stage-sound")
        self.assertIn("오답은 다시 풀고, 북마크한 문제는 따로 모아 볼 수 있습니다.", html)
        _, html = pages.app_page("en", "stage-sound")
        self.assertIn("Redo your missed questions, and keep bookmarked ones together in one place.", html)

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
                '<url><loc>https://mlmusicstudio.co.kr/guides/</loc></url>\n'
                '<url><loc>https://mlmusicstudio.co.kr/apps/</loc></url>\n</urlset>\n', encoding="utf-8")
            pages.update_sitemap(root, ["/", "/apps/", "/apps/"])
            pages.update_sitemap(root, ["/", "/apps/", "/apps/"])
            text = (root / "sitemap.xml").read_text(encoding="utf-8")
            self.assertEqual(text.count("<loc>https://mlmusicstudio.co.kr/apps/</loc>"), 1)
            self.assertEqual(text.count("<loc>https://mlmusicstudio.co.kr/</loc>"), 1)
            self.assertIn("<loc>https://mlmusicstudio.co.kr/guides/</loc>", text)


if __name__ == "__main__":
    unittest.main()
