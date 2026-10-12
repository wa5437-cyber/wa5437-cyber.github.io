import json, pathlib, sys, tempfile, unittest
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
    V = [{"id": "v1", "attributes": {"platform": "IOS", "appStoreState": "READY_FOR_SALE", "versionString": "1.1"}},
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


class RenderTests(unittest.TestCase):
    def test_dash_bullets_need_whitespace_after_marker(self):
        self.assertIn('<ul class="bullets"><li>a</li><li>b</li></ul>', pages.render_store_text("- a\n- b"))
        html = pages.render_store_text("-3 dB\nnote")
        self.assertEqual(html, "<p>-3 dB<br>note</p>")
        self.assertNotIn("<li></li>", pages.render_store_text("-"))
        self.assertNotIn("<li>", pages.render_store_text("-"))
        self.assertNotIn("<li></li>", pages.render_store_text("•"))
        self.assertIn("<li>x</li>", pages.render_store_text("・x"))

    def test_render_store_text_paragraphs_lists_and_escape(self):
        html = pages.render_store_text("A & B <script>\n둘째 줄\n\n• one\n• two\n\nlast")
        self.assertIn("<p>A &amp; B &lt;script&gt;<br>둘째 줄</p>", html)
        self.assertIn('<ul class="bullets"><li>one</li><li>two</li></ul>', html)
        self.assertIn("<p>last</p>", html)
        self.assertNotIn("<script>", html)

    def test_render_store_text_handles_many_blank_lines_and_long_text(self):
        html = pages.render_store_text("\n\n\n" + ("가나다 " * 2000) + "\n\n\n\n끝")
        self.assertTrue(html.endswith("<p>끝</p>"))


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
