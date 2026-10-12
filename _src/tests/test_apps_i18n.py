import json, pathlib, re, sys, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_src"))
sys.path.insert(0, str(ROOT / "_src" / "tools"))
from sitegen import pages, kit
import pull_store


class FakeAsc:
    """asc.get(path, **params) 를 흉내낸다. 경로 문자열로 응답을 고른다."""
    def __init__(self, versions, vlocs, infos, ilocs):
        self.versions, self.vlocs, self.infos, self.ilocs = versions, vlocs, infos, ilocs

    def __call__(self, path, **params):
        if path.endswith("/appStoreVersions"):
            return {"data": self.versions}
        if "/appStoreVersionLocalizations" in path:
            return {"data": self.vlocs[path.split("/")[2]]}
        if path.endswith("/appInfos"):
            return {"data": self.infos}
        if "/appInfoLocalizations" in path:
            return {"data": self.ilocs}
        raise AssertionError(path)


def vloc(locale, desc, promo=""):
    return {"attributes": {"locale": locale, "description": desc, "promotionalText": promo}}


def iloc(locale, name, sub=""):
    return {"attributes": {"locale": locale, "name": name, "subtitle": sub}}


class PullStoreTests(unittest.TestCase):
    def test_map_locale(self):
        self.assertEqual(pull_store.map_locale("en-US"), "en")
        self.assertEqual(pull_store.map_locale("es-ES"), "es")
        self.assertEqual(pull_store.map_locale("de-DE"), "de")
        self.assertEqual(pull_store.map_locale("pt-BR"), "pt-BR")
        self.assertIsNone(pull_store.map_locale("en-GB"))
        self.assertIsNone(pull_store.map_locale("es-MX"))

    def test_collect_uses_only_ready_for_sale_and_drops_empty_locales(self):
        versions = [
            {"id": "v2", "attributes": {"platform": "IOS", "appStoreState": "WAITING_FOR_REVIEW", "versionString": "1.3"}},
            {"id": "v1", "attributes": {"platform": "IOS", "appStoreState": "READY_FOR_SALE", "versionString": "1.2"}},
            {"id": "vm", "attributes": {"platform": "MAC_OS", "appStoreState": "READY_FOR_SALE", "versionString": "9"}},
        ]
        get = FakeAsc(
            versions,
            {"v1": [vloc("ja", "説明", "プロモ"), vloc("de-DE", ""), vloc("en-GB", "x")],
             "v2": [vloc("fr-FR", "NEW FEATURE")]},
            [{"id": "i1", "attributes": {"state": "READY_FOR_SALE"}}],
            [iloc("ja", "名前", "副題"), iloc("de-DE", "Name"), iloc("fr-FR", "Nom")],
        )
        out = pull_store.collect("123", get=get)
        self.assertEqual(sorted(out), ["ja"])               # de 는 설명 없음, fr 는 심사 중 버전에만 있음
        self.assertEqual(out["ja"], {"name": "名前", "subtitle": "副題", "promo": "プロモ", "description": "説明"})


class CollectSafetyTests(unittest.TestCase):
    V = [{"id": "v1", "attributes": {"platform": "IOS", "appStoreState": "READY_FOR_SALE", "versionString": "1.9"}},
         {"id": "v10", "attributes": {"platform": "IOS", "appStoreState": "READY_FOR_SALE", "versionString": "1.10"}}]

    def test_two_appinfos_uses_live_one_even_when_draft_is_listed_first(self):
        draft = {"id": "d", "attributes": {"state": "PREPARE_FOR_SUBMISSION"}}
        live = {"id": "l", "attributes": {"state": "READY_FOR_SALE"}}

        class Get(FakeAsc):
            def __call__(self, path, **params):
                if "/appInfoLocalizations" in path:
                    return {"data": [iloc("ja", "DRAFT" if "/d/" in path else "公開名", "副")]}
                return super().__call__(path, **params)
        out = pull_store.collect("1", get=Get(self.V, {"v1": [], "v10": [vloc("ja", "説明")]}, [draft, live], []))
        self.assertEqual(out["ja"]["name"], "公開名")

    def test_two_appinfos_none_live_yields_nothing(self):
        a = {"id": "a", "attributes": {"state": "PREPARE_FOR_SUBMISSION"}}
        b = {"id": "b", "attributes": {"state": "WAITING_FOR_REVIEW"}}
        get = FakeAsc(self.V, {"v1": [], "v10": [vloc("ja", "説明")]}, [a, b], [iloc("ja", "DRAFT")])
        self.assertEqual(pull_store.collect("1", get=get), {})

    def test_single_appinfo_is_used_regardless_of_state(self):
        a = {"id": "a", "attributes": {"state": "PREPARE_FOR_SUBMISSION"}}
        get = FakeAsc(self.V, {"v1": [], "v10": [vloc("ja", "説明")]}, [a], [iloc("ja", "名前")])
        self.assertEqual(pull_store.collect("1", get=get)["ja"]["name"], "名前")

    def test_highest_numeric_version_wins(self):
        get = FakeAsc(self.V, {"v1": [vloc("ja", "OLD")], "v10": [vloc("ja", "NEW")]},
                      [{"id": "i", "attributes": {"state": "READY_FOR_SALE"}}], [iloc("ja", "名前")])
        self.assertEqual(pull_store.collect("1", get=get)["ja"]["description"], "NEW")


class StateNameTests(unittest.TestCase):
    """Apple 이 상태 이름을 옮겨 가는 중이라 어느 키로 와도 공개 중으로 읽어야 한다."""
    @staticmethod
    def get(version_attrs, info_attrs):
        return FakeAsc([{"id": "v1", "attributes": dict(platform="IOS", versionString="1.0", **version_attrs)}],
                       {"v1": [vloc("ja", "説明")]},
                       [{"id": "a", "attributes": info_attrs}, {"id": "b", "attributes": {"state": "PREPARE_FOR_SUBMISSION"}}],
                       [iloc("ja", "名前")])

    def test_appinfo_with_only_app_store_state(self):
        out = pull_store.collect("1", get=self.get({"appStoreState": "READY_FOR_SALE"}, {"appStoreState": "READY_FOR_SALE"}))
        self.assertEqual(out["ja"]["name"], "名前")

    def test_appinfo_state_ready_for_distribution_is_live(self):
        out = pull_store.collect("1", get=self.get({"appStoreState": "READY_FOR_SALE"}, {"state": "READY_FOR_DISTRIBUTION"}))
        self.assertEqual(out["ja"]["name"], "名前")

    def test_version_with_app_version_state(self):
        out = pull_store.collect("1", get=self.get({"appVersionState": "READY_FOR_SALE"}, {"state": "READY_FOR_SALE"}))
        self.assertEqual(out["ja"]["description"], "説明")

    def test_version_with_plain_state_ready_for_distribution(self):
        out = pull_store.collect("1", get=self.get({"state": "READY_FOR_DISTRIBUTION"}, {"state": "READY_FOR_SALE"}))
        self.assertEqual(out["ja"]["description"], "説明")

    def test_version_not_live_in_any_key_is_ignored(self):
        out = pull_store.collect("1", get=self.get({"appVersionState": "WAITING_FOR_REVIEW"}, {"state": "READY_FOR_SALE"}))
        self.assertEqual(out, {})


class MergeStoreTests(unittest.TestCase):
    OLD = {"ja": {"name": "旧", "subtitle": "", "promo": "", "description": "説明"}}
    NEW = {"fr": {"name": "N", "subtitle": "", "promo": "", "description": "D"}}

    def test_empty_result_keeps_existing_store_and_warns(self):
        import contextlib, io
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            out = pull_store.merge_store(self.OLD, {}, allow_empty=False)
        self.assertEqual(out, self.OLD)
        self.assertIn("--allow-empty", err.getvalue())

    def test_allow_empty_replaces_with_empty(self):
        self.assertEqual(pull_store.merge_store(self.OLD, {}, allow_empty=True), {})

    def test_nonempty_result_replaces_and_empty_over_empty_is_empty(self):
        self.assertEqual(pull_store.merge_store(self.OLD, self.NEW, allow_empty=False), self.NEW)
        self.assertEqual(pull_store.merge_store(None, {}, allow_empty=False), {})
        self.assertEqual(pull_store.merge_store({}, {}, allow_empty=False), {})


class PlatformFallbackTests(unittest.TestCase):
    LIVE = [{"id": "i", "attributes": {"state": "READY_FOR_SALE"}}]

    @staticmethod
    def ver(vid, platform, state, string):
        return {"id": vid, "attributes": {"platform": platform, "appStoreState": state, "versionString": string}}

    def test_mac_only_app_uses_mac_version(self):
        get = FakeAsc([self.ver("m1", "MAC_OS", "READY_FOR_SALE", "1.0")],
                      {"m1": [vloc("ko", "맥 설명", "맥 프로모")]}, self.LIVE, [iloc("ko", "노라", "부제")])
        out = pull_store.collect("1", get=get)
        self.assertEqual(out["ko"], {"name": "노라", "subtitle": "부제", "promo": "맥 프로모", "description": "맥 설명"})

    def test_ios_wins_over_mac_regardless_of_version_number(self):
        get = FakeAsc([self.ver("m2", "MAC_OS", "READY_FOR_SALE", "2.0"),
                       self.ver("i1", "IOS", "READY_FOR_SALE", "1.0")],
                      {"i1": [vloc("ko", "IOS 설명")], "m2": [vloc("ko", "MAC 설명")]},
                      self.LIVE, [iloc("ko", "이름")])
        self.assertEqual(pull_store.collect("1", get=get)["ko"]["description"], "IOS 설명")

    def test_no_ready_version_yields_nothing(self):
        get = FakeAsc([self.ver("m1", "MAC_OS", "WAITING_FOR_REVIEW", "1.0"),
                       self.ver("i1", "IOS", "PREPARE_FOR_SUBMISSION", "1.0")],
                      {"m1": [vloc("ko", "x")], "i1": [vloc("ko", "x")]}, self.LIVE, [iloc("ko", "이름")])
        self.assertEqual(pull_store.collect("1", get=get), {})


class RenderTests(unittest.TestCase):
    def test_dash_bullets_need_whitespace_after_marker(self):
        self.assertIn('<ul class="bullets"><li>a</li><li>b</li></ul>', pages.render_store_text("- a\n- b"))
        html = pages.render_store_text("-3 dB\nnote")
        self.assertEqual(html, "<p>-3 dB<br>note</p>")
        self.assertNotIn("<li></li>", pages.render_store_text("-"))
        self.assertNotIn("<li>", pages.render_store_text("-"))
        self.assertNotIn("<li></li>", pages.render_store_text("•"))
        self.assertIn("<li>x</li>", pages.render_store_text("・x"))

    def test_bullet_without_space_renders_as_list_item(self):
        self.assertEqual(pages.render_store_text("•x\n•y"), '<ul class="bullets"><li>x</li><li>y</li></ul>')
        self.assertEqual(pages.render_store_text("•x"), '<ul class="bullets"><li>x</li></ul>')

    def test_heading_line_followed_only_by_bullets_splits_into_p_and_ul(self):
        self.assertEqual(pages.render_store_text("免费\n• a\n• b"),
                         '<p>免费</p><ul class="bullets"><li>a</li><li>b</li></ul>')
        html = pages.render_store_text("Free\n- a\n- b")
        self.assertEqual(html, '<p>Free</p><ul class="bullets"><li>a</li><li>b</li></ul>')
        self.assertEqual(pages.render_store_text("제목\n• 가"),
                         '<p><span lang="ko">제목</span></p><ul class="bullets"><li><span lang="ko">가</span></li></ul>')

    def test_mixed_blocks_stay_one_paragraph(self):
        self.assertEqual(pages.render_store_text("head\n• a\ntail"), "<p>head<br>• a<br>tail</p>")
        self.assertEqual(pages.render_store_text("• a\ntail"), "<p>• a<br>tail</p>")
        self.assertEqual(pages.render_store_text("head\nmore\n• a"), "<p>head<br>more<br>• a</p>")
        self.assertEqual(pages.render_store_text("head\n•"), "<p>head<br>•</p>")

    def test_render_store_text_paragraphs_lists_and_escape(self):
        html = pages.render_store_text("A & B <script>\n둘째 줄\n\n• one\n• two\n\nlast")
        self.assertIn('<p>A &amp; B &lt;script&gt;<br><span lang="ko">둘째 줄</span></p>', html)
        self.assertIn('<ul class="bullets"><li>one</li><li>two</li></ul>', html)
        self.assertIn("<p>last</p>", html)
        self.assertNotIn("<script>", html)

    def test_render_store_text_handles_many_blank_lines_and_long_text(self):
        html = pages.render_store_text("\n\n\n" + ("가나다 " * 2000) + "\n\n\n\n끝")
        self.assertTrue(html.endswith('<p><span lang="ko">끝</span></p>'))


class PageLangTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig = pages.load_app
        data = {
            "store": {
                "ja": {"name": "ステージ音響", "subtitle": "副題", "promo": "", "description": "説明1\n\n• 項目"},
                "de": {"name": "", "subtitle": "", "promo": "", "description": ""},
            },
            "detail": self._orig("stage-sound")["detail"],
        }
        pages.load_app = lambda slug: data if slug == "stage-sound" else self._orig(slug)

    def tearDown(self):
        pages.load_app = self._orig
        self.tmp.cleanup()

    def test_only_ready_languages_get_pages_and_alts(self):
        self.assertEqual(pages.app_langs("stage-sound"), ["ko", "en", "ja"])
        alts = pages.alts_for_app("stage-sound")
        self.assertEqual(alts, {"ko": "/apps/stage-sound/", "en": "/en/apps/stage-sound/", "ja": "/ja/apps/stage-sound/"})

    def test_store_layout_page_for_ja(self):
        path, html = pages.app_page("ja", "stage-sound")
        self.assertEqual(path, "/ja/apps/stage-sound/")
        self.assertIn('<html lang="ja">', html)
        self.assertIn("ステージ音響", html)
        self.assertIn("スクリーンショット", html)
        self.assertIn("プライバシーポリシー", html)
        self.assertIn('<ul class="bullets"><li>項目</li></ul>', html)
        self.assertNotIn("평생 이용권", html)                # 가격 알약 없음
        self.assertNotIn("/guides/", html.split("<main", 1)[1])  # 관련 가이드(한국어 전용) 없음
        self.assertIn('hreflang="ja"', html)
        self.assertNotIn('hreflang="de"', html)
        self.assertIn('"@type": "SoftwareApplication"', html)
        self.assertIn('"inLanguage": "ja"', html)
        self.assertIn("apps.apple.com", html)

    def test_ja_main_has_no_hangul(self):
        import re
        _, html = pages.app_page("ja", "stage-sound")
        main = html.split("<main", 1)[1].split("</main>", 1)[0]
        self.assertIsNone(re.search("[\uac00-\ud7a3]", main))

    def test_full_layout_labels_follow_language(self):
        _, ko = pages.app_page("ko", "stage-sound")
        _, en = pages.app_page("en", "stage-sound")
        self.assertIn("사용법", ko)
        self.assertIn("How to use", en)
        self.assertIn("Privacy policy (Korean)", en)

    def test_build_all_writes_only_ready_language_pages(self):
        root = pathlib.Path(self.tmp.name)
        pages.build_all(root)
        self.assertTrue((root / "ja" / "apps" / "stage-sound" / "index.html").exists())
        self.assertFalse((root / "de" / "apps" / "stage-sound" / "index.html").exists())
        self.assertTrue((root / "apps" / "stage-sound" / "index.html").exists())


class PromoAndPruneTests(unittest.TestCase):
    """스토어 구성 페이지는 기간 한정 홍보 문구를 싣지 않고, 빠진 언어의 옛 출력은 지운다."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self._orig = pages.load_app
        self.det = self._orig("stage-sound")["detail"]
        self.store = {"ja": {"name": "ステージ音響", "subtitle": "副題", "promo": "最初の2週間無料", "description": "説明1"}}
        pages.load_app = lambda slug: ({"detail": self.det, "store": self.store} if slug == "stage-sound"
                                       else self._orig(slug))
        (self.root / "sitemap.xml").write_text("<urlset>\n</urlset>\n", encoding="utf-8")

    def tearDown(self):
        pages.load_app = self._orig
        self.tmp.cleanup()

    def sitemap(self):
        return (self.root / "sitemap.xml").read_text(encoding="utf-8")

    def test_store_page_has_no_promo_in_body_or_meta(self):
        _, html = pages.app_page("ja", "stage-sound")
        self.assertNotIn("最初の2週間無料", html)
        self.assertIn('<meta name="description" content="副題 — 説明1">', html)
        self.assertIn('<meta property="og:description" content="副題 — 説明1">', html)

    def test_description_is_cut_to_150_and_is_subtitle_only_when_description_empty(self):
        self.store["ja"]["description"] = "word " * 80
        _, html = pages.app_page("ja", "stage-sound")
        desc = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
        self.assertTrue(desc.startswith("副題 — word word") and desc.endswith("…"))
        self.assertLessEqual(len(desc), 151)
        self.store["ja"]["description"] = ""
        _, html = pages.app_page("ja", "stage-sound")
        self.assertIn('<meta name="description" content="副題">', html)

    def test_dropped_language_output_and_sitemap_entry_are_removed(self):
        pages.build_all(self.root)
        ja = self.root / "ja" / "apps" / "stage-sound"
        self.assertTrue((ja / "index.html").exists())
        self.assertIn(kit.BASE + "/ja/apps/stage-sound/", self.sitemap())
        del self.store["ja"]
        pages.build_all(self.root)
        self.assertFalse((ja / "index.html").exists())
        self.assertFalse(ja.exists())                                   # 빈 폴더도 지운다
        self.assertNotIn("/ja/apps/stage-sound/", self.sitemap())
        self.assertIn(kit.BASE + "/apps/stage-sound/", self.sitemap())  # ko 는 그대로
        self.assertIn(kit.BASE + "/en/apps/stage-sound/", self.sitemap())

    def test_app_losing_its_detail_loses_ko_and_en_pages_too(self):
        pages.build_all(self.root)
        self.assertTrue((self.root / "apps" / "stage-sound" / "index.html").exists())
        self.assertTrue((self.root / "apps" / "index.html").exists())
        self.det = None
        pages.load_app = lambda slug: ({"store": self.store} if slug == "stage-sound" else self._orig(slug))
        pages.build_all(self.root)
        for rel in ("apps/stage-sound", "en/apps/stage-sound", "ja/apps/stage-sound"):
            self.assertFalse((self.root / rel / "index.html").exists(), rel)
            self.assertFalse((self.root / rel).exists(), rel)
        self.assertTrue((self.root / "apps" / "index.html").exists())     # 목록 페이지는 건드리지 않는다
        sm = self.sitemap()
        self.assertNotIn("/apps/stage-sound/", sm)
        self.assertIn(kit.BASE + "/apps/", sm)

    def test_pruning_leaves_unknown_slugs_other_files_and_other_sitemap_entries(self):
        keep = ["https://mlmusicstudio.co.kr/guides/", "https://mlmusicstudio.co.kr/ja/apps/other-app/",
                "https://mlmusicstudio.co.kr/ja/apps/stage-sound/extra.html"]
        (self.root / "sitemap.xml").write_text(
            "<urlset>\n" + "".join(f"  <url><loc>{k}</loc><priority>0.5</priority></url>\n" for k in keep)
            + "  <url><loc>https://mlmusicstudio.co.kr/de/apps/stage-sound/</loc><priority>0.5</priority></url>\n"
            + "</urlset>\n", encoding="utf-8")
        other = self.root / "ja" / "apps" / "other-app"
        other.mkdir(parents=True)
        (other / "index.html").write_text("keep", encoding="utf-8")
        stray = self.root / "de" / "apps" / "stage-sound"
        stray.mkdir(parents=True)
        (stray / "index.html").write_text("old", encoding="utf-8")
        (stray / "notes.txt").write_text("mine", encoding="utf-8")
        pages.build_all(self.root)
        self.assertEqual((other / "index.html").read_text(encoding="utf-8"), "keep")
        self.assertFalse((stray / "index.html").exists())
        self.assertTrue((stray / "notes.txt").exists())                  # 비어 있지 않은 폴더는 남긴다
        sm = self.sitemap()
        for k in keep:
            self.assertIn(k, sm)
        self.assertIn("<priority>0.5</priority>", sm)
        self.assertNotIn("/de/apps/stage-sound/<", sm)


class DetailLinkTests(unittest.TestCase):
    """계획 Task 16: 상세 페이지가 있는 앱은 목록에서 링크되고, 그 언어 주소는 모두 사이트맵과 디스크에 있다."""
    def test_every_detail_app_is_linked_and_its_alternates_are_built_and_in_sitemap(self):
        slugs = [a["slug"] for a in pages.load("apps.json")["apps"] if pages.has_detail(a["slug"])]
        self.assertTrue(slugs)
        _, index = pages.apps_index("ko")
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "sitemap.xml").write_text("<urlset>\n</urlset>\n", encoding="utf-8")
            pages.build_all(root)
            sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
            for slug in slugs:
                self.assertIn(f'href="/apps/{slug}/"', index, slug)
                alts = pages.alts_for_app(slug)
                self.assertIn("ko", alts)
                for lang, path in alts.items():
                    self.assertIn(f"<loc>{kit.BASE}{path}</loc>", sitemap, (slug, lang))
                    self.assertTrue((root / path.lstrip("/") / "index.html").exists(), (slug, lang))


class PricePillTests(unittest.TestCase):
    """가격은 선택 항목: 있을 때만 알약을 그린다."""
    def setUp(self):
        self._load_app = pages.load_app
        self.det = json.loads(json.dumps(self._load_app("stage-sound")["detail"]))   # 깊은 복사
        pages.load_app = lambda slug: ({"detail": self.det, "store": {}} if slug == "stage-sound"
                                       else self._load_app(slug))

    def tearDown(self):
        pages.load_app = self._load_app

    def _hero_row(self, lang="ko"):
        _, html = pages.app_page(lang, "stage-sound")
        return html.split('<div class="row">', 1)[1].split("</div>", 1)[0]

    def test_price_pill_present_when_price_given(self):
        self.det["price"] = {"ko": "평생 이용권 ₩9,900", "en": "Lifetime ₩9,900"}
        self.assertIn('<span class="pill" style="align-self:center">평생 이용권 ₩9,900</span>', self._hero_row("ko"))
        self.assertIn("Lifetime ₩9,900", self._hero_row("en"))

    def test_no_price_key_renders_without_price_pill(self):
        self.det.pop("price", None)
        row = self._hero_row("ko")
        self.assertNotIn('class="pill"', row)
        _, html = pages.app_page("ko", "stage-sound")
        self.assertIn('<span class="pill">', html)            # 플랫폼 알약은 그대로
        self.assertNotIn("align-self:center", html)

    def test_price_dict_lacking_lang_renders_no_pill(self):
        self.det["price"] = {"ko": "평생 이용권 ₩9,900"}
        row = self._hero_row("en")
        self.assertNotIn('class="pill"', row)
        self.assertNotIn("9,900", row)
        self.det["price"] = {"ko": "", "en": ""}
        self.assertNotIn('class="pill"', self._hero_row("ko"))


class KoreanSpanTests(unittest.TestCase):
    NAME = "율 Yul — 国楽チューナー & 長短"
    DESC = "リズム 진양조→중모리→… のように\n\n• 자진모리 機能"

    def setUp(self):
        self._load_app = pages.load_app
        det = self._load_app("stage-sound")["detail"]
        store = {"ja": {"name": self.NAME, "subtitle": "부제 サブ", "promo": "", "description": self.DESC}}
        pages.load_app = lambda slug: {"detail": det, "store": store} if slug == "stage-sound" else self._load_app(slug)

    def tearDown(self):
        pages.load_app = self._load_app

    def test_hangul_runs_are_wrapped_and_check_passes(self):
        from sitegen import check
        _, html = pages.app_page("ja", "stage-sound")
        self.assertIn('<span lang="ko">율</span> Yul', html)
        self.assertIn('<span lang="ko">진양조→중모리</span>→…', html)
        self.assertIn('<li><span lang="ko">자진모리</span> 機能</li>', html)
        self.assertEqual(check.language_errors("ja/apps/x/index.html", html), [])

    def test_ampersand_in_name_stays_escaped(self):
        _, html = pages.app_page("ja", "stage-sound")
        self.assertIn("国楽チューナー &amp; 長短", html)
        self.assertNotIn("&amp;amp;", html)
        self.assertNotIn(" & 長短", html.split("<main", 1)[1])

    def test_title_and_alt_stay_plain(self):
        _, html = pages.app_page("ja", "stage-sound")
        head = html.split("<main", 1)[0]
        self.assertIn("<title>" + "율 Yul", head)
        self.assertNotIn("<span", head.split("</title>", 1)[0])
        self.assertNotIn("<span", re.search(r'<meta name="description"[^>]*>', head).group(0))
        self.assertNotIn('alt="<span', html)

    def test_esc_mixed_unit(self):
        self.assertEqual(pages.esc_mixed("a<b>&가나"), 'a&lt;b&gt;&amp;<span lang="ko">가나</span>')
        self.assertEqual(pages.esc_mixed("가 나·다-라→마"), '<span lang="ko">가 나·다-라→마</span>')
        self.assertEqual(pages.esc_mixed("가→x"), '<span lang="ko">가</span>→x')


class ImgAndLegalTests(unittest.TestCase):
    def setUp(self):
        self._load_app, self._load = pages.load_app, pages.load
        det = json.loads(json.dumps(self._load_app("stage-sound")["detail"]))   # 깊은 복사
        det["hero_img"] = {"ko": "hero_ko.jpg", "en": "hero_en.jpg"}
        for i, b in enumerate(det["blocks"]):
            b["img"] = {"ko": f"b{i}_ko.jpg", "en": f"b{i}_en.jpg"}
        store = {"ja": {"name": "ステージ音響", "subtitle": "", "promo": "", "description": "説明"}}
        pages.load_app = lambda slug: {"detail": det, "store": store} if slug == "stage-sound" else self._load_app(slug)

    def tearDown(self):
        pages.load_app, pages.load = self._load_app, self._load

    def test_dict_images_follow_language_in_both_layouts(self):
        _, ko = pages.app_page("ko", "stage-sound")
        _, en = pages.app_page("en", "stage-sound")
        _, ja = pages.app_page("ja", "stage-sound")          # 스토어 구성: ja -> en 파일
        self.assertIn("hero_ko.jpg", ko)
        self.assertIn("b0_ko.jpg", ko)
        self.assertNotIn("_en.jpg", ko)
        self.assertIn("hero_en.jpg", en)
        self.assertIn("b0_en.jpg", en)
        self.assertNotIn("_ko.jpg", en)
        self.assertIn("hero_en.jpg", ja)
        self.assertIn("b0_en.jpg", ja)
        self.assertNotIn("_ko.jpg", ja)

    def _with_legal(self, legal):
        def patched(name):
            d = self._load(name)
            if name == "apps.json":
                d = json.loads(json.dumps(d))
                for a in d["apps"]:
                    if a["slug"] == "stage-sound":
                        a["legal"] = legal
            return d
        pages.load = patched

    def test_privacy_link_uses_legal_when_set_in_both_layouts(self):
        self._with_legal("/stage_legal.html")
        for lang in ("ko", "en", "ja"):
            _, html = pages.app_page(lang, "stage-sound")
            self.assertIn('href="/stage_legal.html"', html, lang)
            self.assertNotIn("/policy.html#policy", html.split("<main", 1)[1], lang)

    def test_privacy_link_falls_back_to_policy_page(self):
        self._with_legal(None)
        for lang in ("ko", "en", "ja"):
            _, html = pages.app_page(lang, "stage-sound")
            self.assertIn('href="/policy.html#policy"', html, lang)


class PrepShotTests(unittest.TestCase):
    def test_prepare_resizes_to_jpeg(self):
        import prep_shot, subprocess
        with tempfile.TemporaryDirectory() as d:
            src = pathlib.Path(d) / "a.png"
            # 1x1 PNG
            import base64
            src.write_bytes(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))
            dst = pathlib.Path(d) / "out" / "a.jpg"
            prep_shot.prepare(src, dst)
            self.assertTrue(dst.exists())
            self.assertEqual(dst.read_bytes()[:2], b"\xff\xd8")

    def test_missing_source_raises(self):
        import prep_shot
        with self.assertRaises(RuntimeError):
            prep_shot.prepare("/no/such.png", "/tmp/never.jpg")
