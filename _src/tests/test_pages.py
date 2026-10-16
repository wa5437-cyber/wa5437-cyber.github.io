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

    def test_home_guide_list_has_short_one_line_ledes(self):
        _, html = pages.home("ko")
        items = re.findall(r'<li><a href="/guides/([^"]+)\.html">(.*?)</a><p>(.*?)</p></li>', html, re.S)
        self.assertEqual([i[0] for i in items], pages.load("home.json")["latest_guides"])
        for _, title, p in items:
            self.assertTrue(title)
            self.assertLessEqual(len(p), 71)
        self.assertTrue(any(p.endswith("…") for _, _, p in items))


# 화면에 보이면 안 되는 경력 숫자·기간(사용자 지시: 포트폴리오에서 건수·기간 강조를 뺀다)
CAREER_NUMBERS = re.compile(r"\b111\b|\b66\b|\b49\b|\b30건|기록된 작업|기록한 작업|2009|recorded credits|credits on record|\{(since|total|mastering|mixing|recording)\}")


def visible(html):
    """<head>·스크립트를 빼고, 태그를 걷어낸 본문 글 + alt·title 속성."""
    body = html[html.index("<body>"):]
    body = re.sub(r"<script\b.*?</script>", "", body, flags=re.S)
    attrs = " ".join(re.findall(r'\s(?:alt|title|aria-label)="([^"]*)"', body))
    return re.sub(r"<[^>]+>", " ", body) + " " + attrs


def section_of(html, cls):
    m = re.search(r'<section class="%s">(.*?)</section>' % re.escape(cls), html, re.S)
    return m.group(1) if m else None


class HomeLayoutTests(unittest.TestCase):
    """홈(2차): 사진 히어로 → 참여한 작업 띠 → 엔지니어 → 녹음실(어두운 띠) → 앱(보조) → 플러그인 띠 → 웹 도구·가이드 → 문의(어두운 띠)."""
    def test_sections_in_studio_first_order(self):
        for lang in ("ko", "en"):
            _, html = pages.home(lang)
            main = re.search(r"<main.*?</main>", html, re.S).group(0)
            marks = ['class="photo-hero"', 'class="covers strip-5"', 'class="wrap engineer"', '<section class="band dark">',
                     'class="band apps-band"', '<section class="strip">', 'class="wrap split"', '<h2>%s</h2>' % pages.load("home.json")[lang]["contact_title"]]
            pos = [main.index(m) for m in marks]
            self.assertEqual(pos, sorted(pos), lang)

    def test_hero_photo_is_eager_sized_and_text_is_short(self):
        for lang in ("ko", "en"):
            _, html = pages.home(lang)
            hero = section_of(html, "photo-hero")
            img = re.search(r"<img [^>]+>", hero).group(0)
            self.assertIn('src="/img/studio/control-room.jpg"', img)
            self.assertIn('fetchpriority="high"', img)
            self.assertNotIn('loading="lazy"', img)
            width, height = kit.img_size("/img/studio/control-room.jpg")
            self.assertIn(f'width="{width}" height="{height}"', img)
            self.assertRegex(img, r'alt="[^"]+"')
        _, ko = pages.home("ko")
        self.assertIn("<h1>ML Music Studio 녹음실</h1>", ko)
        self.assertIn('<p class="sub">서울 용산 · 녹음 · 믹싱 · 마스터링</p>', ko)

    def test_hero_ctas_contact_on_kakao_then_work(self):
        _, ko = pages.home("ko")
        hero = section_of(ko, "photo-hero")
        btns = re.findall(r'<a class="(btn[^"]*)" href="([^"]+)"[^>]*>([^<]+)</a>', hero)
        self.assertEqual(btns[0], ("btn primary", "https://open.kakao.com/o/sQhjCeZb", "문의하기"))
        self.assertEqual(btns[1], ("btn", "/work/", "작업 보기"))
        _, en = pages.home("en")
        self.assertIn('href="/en/work/"', section_of(en, "photo-hero"))

    def test_credits_strip_has_ten_lazy_sized_posters_mixing_categories(self):
        posters = {p["img"]: p for p in pages.load("work_posters.json")}
        for lang in ("ko", "en"):
            _, html = pages.home(lang)
            strip = re.search(r'<div class="covers strip-5">(.*?)</div></div></section>', html, re.S).group(1)
            imgs = re.findall(r"<img [^>]+>", strip)
            self.assertEqual(len(imgs), 10, lang)
            cats = set()
            for img in imgs:
                self.assertIn('loading="lazy"', img)
                self.assertRegex(img, r'width="324" height="324"')
                src = re.search(r'src="([^"]+)"', img).group(1)
                p = posters[src]
                cats.add(p["category"])
                alt = re.search(r'alt="([^"]*)"', img).group(1)
                if p["artist"] and p["title"]:
                    self.assertEqual(alt, kit.esc(f'{p["artist"]} — {p["title"]}'))
                self.assertTrue(alt)
            self.assertGreaterEqual(len(cats), 4, lang)
            self.assertIn(f'href="{kit.url(lang, "/work/")}"', html)

    def test_engineer_block_has_portrait_and_about_link_but_no_numbers(self):
        for lang in ("ko", "en"):
            _, html = pages.home(lang)
            eng = re.search(r'<div class="wrap engineer">(.*?)</div></div></section>', html, re.S).group(1)
            self.assertIn('src="/img/about/profile.png"', eng)
            self.assertIn(f'href="{kit.url(lang, "/about/")}"', eng)
            self.assertNotIn("stat", eng)
            self.assertNotRegex(re.sub(r"<[^>]+>", " ", eng), r"\d")

    def test_dark_studio_band_has_three_photos_captions_and_gear(self):
        gear = pages.load_page("studio")["gear"]
        for lang in ("ko", "en"):
            _, html = pages.home(lang)
            band = section_of(html, "band dark")
            self.assertEqual(len(re.findall(r'<figure class="pic"><img [^>]*loading="lazy"', band)), 3, lang)
            self.assertEqual(len(re.findall(r"<figcaption>[^<]+</figcaption>", band)), 3, lang)
            for g in gear[lang]:
                self.assertIn(kit.esc(g), band)
            self.assertIn(f'href="{kit.url(lang, "/studio/")}"', band)
            self.assertNotIn('class="stats"', html)

    def test_apps_are_a_secondary_band_of_four_small_screens(self):
        n = len(pages.load("apps.json")["apps"])
        _, html = pages.home("ko")
        band = section_of(html, "band apps-band")
        shots = re.findall(r'<img class="mini [^"]*"[^>]+>', band)
        self.assertEqual(len(shots), 4)
        for img in shots:
            self.assertIn('loading="lazy"', img)
        self.assertIn(f"앱 {n}개 보기 →", band)
        self.assertNotIn('class="card product"', html)
        self.assertGreater(html.index("band apps-band"), html.index('<section class="band dark">'))

    def test_contact_band_is_dark_with_kakao_mail_and_address(self):
        for lang in ("ko", "en"):
            _, html = pages.home(lang)
            last = html[html.rindex('<section class="band dark">'):html.index("</main>")]
            self.assertIn("open.kakao.com/o/sQhjCeZb", last)
            self.assertIn("mailto:wa547@hanmail.net", last)
            self.assertIn("map.naver.com", last)

    def test_no_career_counts_or_ranges_on_home(self):
        for lang in ("ko", "en"):
            _, html = pages.home(lang)
            self.assertNotRegex(visible(html), CAREER_NUMBERS, lang)
            head = html[:html.index("<body>")]
            self.assertNotRegex(head, CAREER_NUMBERS, lang)

    def test_old_three_cards_and_empty_tools_band_are_gone(self):
        _, html = pages.home("ko")
        self.assertNotIn("곧 선보일 오디오 플러그인", html)
        self.assertNotIn('style="text-decoration:none', html)
        self.assertNotIn("브라우저에서 바로 쓰세요", html)

    def test_plugin_strip_and_compact_tool_links(self):
        _, html = pages.home("ko")
        strip = re.search(r'<section class="strip">(.*?)</section>', html, re.S).group(1)
        self.assertIn('href="/plugins/"', strip)
        self.assertIn("VST3 · AU 개발 중", strip)
        tools = re.search(r'<ul class="link-list">(.*?)</ul>', html, re.S).group(1)
        hrefs = re.findall(r'href="([^"]+)"', tools)
        self.assertTrue(3 <= len(hrefs) <= 4)
        from sitegen import check
        for href in hrefs:
            self.assertTrue(check.exists(pages.ROOT, href), href)


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
            self.assertEqual(html.count(f'<h3><a href="{f}">'), 1, f)

    def test_prototype_page_is_not_listed(self):
        _, html = pages.tools("en")
        self.assertNotIn("eartrainer_prototype", html)

    def test_tools_paths(self):
        self.assertEqual(pages.tools("ko")[0], "/tools/")
        self.assertEqual(pages.tools("en")[0], "/en/tools/")

    def test_tools_links_exam_to_detail_page_and_others_to_apps_index(self):
        tools_data = pages.load("tools.json")
        for lang, pre in (("ko", ""), ("en", "/en")):
            _, html = pages.tools(lang)
            slugs = {it["app"] for g in tools_data[lang]["groups"] for it in g["items"] if it.get("app")}
            self.assertIn("stage-sound", slugs)
            self.assertTrue(pages.has_detail("stage-sound"))
            for slug in slugs:
                detail = f'href="{pre}/apps/{slug}/"'
                if pages.has_detail(slug):
                    self.assertIn(detail, html, (lang, slug))     # 상세 페이지가 있으면 거기로
                else:
                    self.assertNotIn(detail, html, (lang, slug))  # 없으면 깨진 링크 대신 앱 목록으로
                    self.assertIn(f'href="{pre}/apps/"', html, (lang, slug))
            if not all(pages.has_detail(sl) for sl in slugs):
                self.assertIn(f'href="{pre}/apps/"', html, lang)


class AppsTests(unittest.TestCase):
    def test_apps_index_lists_all_apps_with_pages_only_for_detailed_ones(self):
        _, html = pages.apps_index("ko")
        self.assertIn("무대음향 자격증 기출문제", html)
        self.assertIn('href="/apps/stage-sound/"', html)
        for a in pages.load("apps.json")["apps"]:
            link = f'href="/apps/{a["slug"]}/"'
            if pages.has_detail(a["slug"]):
                self.assertIn(link, html, a["slug"])
            else:
                self.assertNotIn(link, html, a["slug"])      # 상세 페이지가 없으면 링크도 없다

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
            lead = pages.load_app("stage-sound")["detail"]["lead"][lang]
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


class AppFilesTests(unittest.TestCase):
    def test_stage_sound_loads_from_its_own_file(self):
        app = pages.load_app("stage-sound")
        self.assertIn("detail", app)
        self.assertTrue(pages.has_detail("stage-sound"))
        self.assertFalse(pages.has_detail("no-such-app"))
        self.assertIsNone(pages.load_app("no-such-app"))

    def test_apps_json_no_longer_embeds_details_or_flag(self):
        d = pages.load("apps.json")
        self.assertNotIn("details", d)
        for a in d["apps"]:
            self.assertNotIn("detail", a)

    def test_pick_img(self):
        self.assertEqual(pages.pick_img("a.jpg", "ja"), "a.jpg")
        both = {"ko": "k.jpg", "en": "e.jpg"}
        self.assertEqual(pages.pick_img(both, "ko"), "k.jpg")
        self.assertEqual(pages.pick_img(both, "en"), "e.jpg")
        self.assertEqual(pages.pick_img(both, "ja"), "e.jpg")
        self.assertEqual(pages.pick_img({"ko": "k.jpg"}, "en"), "k.jpg")

    def test_stage_sound_page_unchanged_in_substance(self):
        _, html = pages.app_page("ko", "stage-sound")
        self.assertIn("/img/apps/stage-sound/01_home.jpg", html)
        self.assertIn("평생 이용권 ₩9,900", html)


class AppImageTests(unittest.TestCase):
    def test_every_shot_has_size_and_shape_class(self):
        for slug, langs in (("keymap", ("ko", "en", "ja")), ("nora", ("ko",)), ("spl-rta", ("ko", "ja"))):
            for lang in langs:
                if lang not in pages.app_langs(slug):
                    continue
                _, html = pages.app_page(lang, slug)
                shots = re.findall(r'<img class="shot [^"]*"[^>]*>', html)
                self.assertTrue(shots, (slug, lang))
                for img in shots:
                    self.assertRegex(img, r'class="shot (phone|tablet|wide)"')
                    self.assertRegex(img, r'width="\d+" height="\d+"')
                self.assertNotIn('<img class="shot" ', html)

    def test_tablet_and_mac_screens_are_not_phone_sized(self):
        _, html = pages.app_page("ko", "keymap")
        self.assertIn('class="shot tablet" src="/img/apps/keymap/01_translate_ko.jpg"', html)
        _, html = pages.app_page("ko", "nora")
        self.assertIn('class="shot wide"', html)
        css = (pages.ROOT / "assets" / "site.css").read_text(encoding="utf-8")
        self.assertIn(".shot.phone{max-width:340px}", css)
        self.assertIn(".shot.tablet,.shot.wide{max-width:560px", css)
        self.assertNotRegex(css, r"\.shot\{[^}]*max-width:300px")

    def test_only_hero_image_loads_eagerly(self):
        _, html = pages.app_page("ko", "spl-rta")
        hero = re.search(r'<div class="hero-shot">(<img[^>]+>)', html).group(1)
        self.assertIn('fetchpriority="high"', hero)
        self.assertEqual(html.count('fetchpriority="high"'), 1)

    def test_apps_index_cards_have_screenshot_stage(self):
        n = len(pages.load("apps.json")["apps"])
        for lang in ("ko", "en"):
            _, html = pages.apps_index(lang)
            self.assertEqual(html.count('<div class="card product">'), n)
            self.assertEqual(html.count('<div class="stage"><img class="stage-img'), n)


if __name__ == "__main__":
    unittest.main()
