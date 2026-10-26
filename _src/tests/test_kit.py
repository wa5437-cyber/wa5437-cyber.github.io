import pathlib, re, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sitegen import kit, strings


class KitTests(unittest.TestCase):
    def test_esc_escapes_quotes_and_amp(self):
        self.assertEqual(kit.esc('a & "b" <c>'), "a &amp; &quot;b&quot; &lt;c&gt;")

    def test_url_ko_is_unchanged_and_en_gets_prefix(self):
        self.assertEqual(kit.url("ko", "/apps/"), "/apps/")
        self.assertEqual(kit.url("en", "/apps/"), "/en/apps/")
        self.assertEqual(kit.url("en", "/"), "/en/")

    def test_unknown_language_raises(self):
        with self.assertRaises(ValueError):
            kit.url("xx", "/apps/")
        with self.assertRaises(ValueError):
            kit.t("menu", "xx")
        with self.assertRaises(ValueError):
            kit.t("no_such_key", "ko")
        with self.assertRaises(ValueError):
            kit.page("xx", "/xx/", "T", "D", "<p>b</p>", {"xx": "/xx/"})
        with self.assertRaises(ValueError):
            kit.chrome("xx")

    def test_eight_languages_registered_with_prefixes(self):
        self.assertEqual(kit.LANGS, ("ko", "en", "ja", "zh-Hans", "es", "de", "fr", "pt-BR"))
        self.assertEqual(kit.url("ja", "/apps/x/"), "/ja/apps/x/")
        self.assertEqual(kit.url("zh-Hans", "/apps/x/"), "/zh-Hans/apps/x/")
        self.assertEqual(kit.url("pt-BR", "/"), "/pt-BR/")
        for code in kit.LANGS:
            self.assertIn(code, kit.OG_LOCALE)
            self.assertIn(code, strings.LANG_NAMES)
            self.assertIn(code, strings.LANG_SHORT)
            for key, per in strings.APP_UI.items():
                if key in ("related", "details"):
                    continue
                self.assertTrue(per.get(code), (key, code))

    def test_chrome_falls_back_to_english_for_other_languages(self):
        self.assertEqual(kit.chrome("ko"), "ko")
        self.assertEqual(kit.chrome("en"), "en")
        self.assertEqual(kit.chrome("ja"), "en")
        self.assertEqual(kit.chrome("pt-BR"), "en")

    def test_ja_page_has_ja_html_lang_but_english_chrome_and_en_links(self):
        alts = {"ko": "/apps/x/", "en": "/en/apps/x/", "ja": "/ja/apps/x/"}
        html = kit.page("ja", "/ja/apps/x/", "T", "D", "<p>b</p>", alts)
        self.assertIn('<html lang="ja">', html)
        self.assertIn('property="og:locale" content="ja_JP"', html)
        self.assertIn('<a class="skip" href="#main" lang="en">Skip to content</a>', html)
        self.assertIn('href="/en/apps/"', html)           # 상단 메뉴는 영어 페이지로
        self.assertIn('href="/en/"', html)                # 브랜드 링크
        self.assertIn('hreflang="ja" lang="ja" aria-current="true"', html)
        self.assertIn(">JA ▾<", html)
        self.assertEqual(html.count('rel="alternate" hreflang="ja"'), 1)

    def test_english_chrome_on_other_languages_is_marked_lang_en(self):
        alts = {"ko": "/apps/x/", "ja": "/ja/apps/x/"}
        for lang in ("ja", "zh-Hans", "es", "de", "fr", "pt-BR"):
            html = kit.page(lang, f"/{lang}/apps/x/", "T", "D", "<p>b</p>", alts if lang == "ja" else {"ko": "/apps/x/"})
            self.assertIn('<header class="site-header" lang="en">', html, lang)
            self.assertIn('<footer class="site-footer" lang="en">', html, lang)
            self.assertIn('<a class="skip" href="#main" lang="en">', html, lang)
            self.assertIn(f'<html lang="{lang}">', html)
            self.assertIn('<main id="main"><p>b</p></main>', html)       # 본문에는 lang 을 덧붙이지 않는다

    def test_ko_and_en_chrome_carry_no_extra_lang(self):
        for lang in ("ko", "en"):
            html = kit.page(lang, "/x/", "T", "D", "<p>b</p>", {"ko": "/x/"})
            self.assertIn('<header class="site-header">', html, lang)
            self.assertIn('<footer class="site-footer">', html, lang)
            self.assertIn('<a class="skip" href="#main">', html, lang)

    def test_lang_menu_unknown_code_raises(self):
        with self.assertRaises(KeyError):
            kit.lang_menu("ko", {"ko": "/", "xx": "/xx/"})

    def test_write_folder_url_creates_index_html(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            kit.write(root, "/en/apps/", "<p>x</p>")
            self.assertEqual((root / "en/apps/index.html").read_text(encoding="utf-8"), "<p>x</p>")
            kit.write(root, "/policy.html", "<p>y</p>")
            self.assertTrue((root / "policy.html").exists())

    def test_header_lists_nav_and_only_existing_language_alternates(self):
        h = kit.header("ko", {"ko": "/tools/", "en": "/en/tools/"})
        for label in ("작업", "앱", "웹 도구", "플러그인", "녹음실", "가이드"):
            self.assertIn(label, h)
        self.assertIn('href="/en/tools/"', h)

    def test_header_hides_language_menu_with_zero_or_one_alternate(self):
        self.assertNotIn('class="lang"', kit.header("ko", {"ko": "/x/"}))
        self.assertNotIn('class="lang"', kit.header("ko", {}))

    def test_english_header_uses_en_prefix_and_keeps_guides_korean_only(self):
        h = kit.header("en", {"ko": "/", "en": "/en/"})
        self.assertIn('href="/en/apps/"', h)
        self.assertIn('href="/guides/"', h)
        self.assertIn("Apps", h)
        self.assertIn('class="lang"', h)

    def test_footer_has_contact_links(self):
        f = kit.footer("ko")
        self.assertIn('href="https://open.kakao.com/o/sQhjCeZb"', f)
        self.assertIn('href="mailto:wa547@hanmail.net"', f)

    def test_footer_has_business_info(self):
        # 전자상거래법: 상호·대표자·사업자등록번호·통신판매업 신고번호·주소·연락처 표시
        ko = kit.footer("ko")
        for s in ("엠엘뮤직스튜디오", "이효섭", "163-05-01983", "제2026-안양동안-1060호",
                  "https://www.ftc.go.kr/bizCommPop.do?wrkr_no=1630501983", kit.SITE["business"]["address"]["ko"]):
            self.assertIn(s, ko)
        en = kit.footer("en")
        for s in ("ML Music Studio", "Hyoseop Lee", "163-05-01983", "2026-Anyang Dongan-1060",
                  kit.SITE["business"]["address"]["en"]):
            self.assertIn(s, en)

    def test_page_escapes_title_and_description(self):
        html = kit.page("ko", "/x/", 'T "q" <b>', "D & d", "<p>x</p>", {"ko": "/x/"})
        self.assertIn("<title>T &quot;q&quot; &lt;b&gt;</title>", html)
        self.assertIn('content="D &amp; d"', html)
        self.assertNotIn("<b>", html)

    def test_page_has_og_locale_and_twitter_card_mirroring_og(self):
        ko = kit.page("ko", "/x/", 'T "q"', "D & d", "<p>b</p>", {"ko": "/x/"})
        self.assertIn('<meta property="og:locale" content="ko_KR">', ko)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', ko)
        self.assertIn('<meta name="twitter:title" content="T &quot;q&quot;">', ko)
        self.assertIn('<meta name="twitter:description" content="D &amp; d">', ko)
        self.assertIn('<meta name="twitter:image" content="https://mlmusicstudio.co.kr/og-image.png">', ko)
        en = kit.page("en", "/en/x/", "T", "D", "<p>b</p>", {"en": "/en/x/"})
        self.assertIn('<meta property="og:locale" content="en_US">', en)

    def test_page_has_hreflang_canonical_and_skip_link(self):
        html = kit.page("en", "/en/", "T", "D", "<p>b</p>", {"ko": "/", "en": "/en/"})
        self.assertIn('<html lang="en">', html)
        self.assertIn('rel="canonical" href="https://mlmusicstudio.co.kr/en/"', html)
        self.assertIn('hreflang="ko" href="https://mlmusicstudio.co.kr/"', html)
        self.assertIn('hreflang="x-default"', html)
        self.assertIn("#main", html)
        self.assertIn('<main id="main"><p>b</p></main>', html)
    def test_page_emits_google_site_verification_tags_from_policy(self):
        # 기대값은 policy.html(옛 홈)의 <head> 에서 직접 읽는다. site.json 과 어긋나면 실패한다.
        pol = (pathlib.Path(__file__).resolve().parents[2] / "policy.html").read_text(encoding="utf-8")
        expected = re.findall(r'<meta name="google-site-verification" content="[^"]+" />', pol)
        self.assertEqual(len(expected), 2)
        html = kit.page("ko", "/x/", "T", "D", "<p>b</p>", {"ko": "/x/"})
        for tag in expected:
            self.assertIn(tag, html)
        self.assertEqual(html.count('name="google-site-verification"'), 2)


class FooterAndHeaderTests(unittest.TestCase):
    def test_footer_has_four_groups_work_studio_products_contact(self):
        f = kit.footer("ko")
        self.assertEqual(re.findall(r'<p class="foot-h">(.*?)</p>', f), ["작업", "스튜디오", "제품", "문의"])
        for href in ('href="/work/"', 'href="/apps/"', 'href="/tools/"', 'href="/plugins/"', 'href="/guides/"', 'href="/studio/"',
                     'href="/about/"', 'href="/contact/"', 'href="/privacy/"', "map.naver.com"):
            self.assertIn(href, f)
        en = kit.footer("en")
        self.assertEqual(re.findall(r'<p class="foot-h">(.*?)</p>', en), ["Work", "Studio", "Products", "Contact"])
        self.assertIn('href="/en/studio/"', en)
        self.assertIn('href="/en/work/"', en)
        self.assertNotIn("/policy.html", en)

    def test_header_menu_order_is_studio_first(self):
        h = kit.header("ko", {})
        wide = re.search(r'<ul class="nav nav-wide">(.*?)</ul>', h).group(1)
        self.assertEqual(re.findall(r">([^<]+)</a>", wide), ["작업", "녹음실", "앱", "웹 도구", "플러그인", "가이드"])
        en = re.search(r'<ul class="nav nav-wide">(.*?)</ul>', kit.header("en", {})).group(1)
        self.assertEqual(re.findall(r">([^<]+)</a>", en), ["Work", "Studio", "Apps", "Web Tools", "Plugins", "Guides"])
        self.assertIn('href="/en/work/"', en)

    def test_header_marks_current_section(self):
        h = kit.header("ko", {}, "/apps/keymap/")
        self.assertEqual(h.count('aria-current="page"'), 2)          # 넓은 메뉴 + 접는 메뉴
        self.assertIn('<a href="/apps/" aria-current="page">', h)
        self.assertNotIn('aria-current', kit.header("ko", {}, "/"))
        self.assertIn('<a href="/en/studio/" aria-current="page">', kit.header("en", {}, "/en/studio/"))

    def test_page_uses_new_fonts_and_theme_color(self):
        html = kit.page("ko", "/x/", "T", "D", "<p>b</p>", {"ko": "/x/"})
        self.assertIn("family=Inter:wght@400;500;600;700", html)
        self.assertIn("family=Noto+Sans+KR:wght@400;500;600;700", html)
        self.assertNotIn("Serif", html)
        self.assertIn('<meta name="theme-color" content="#f4f5f3">', html)


class ImageSizeTests(unittest.TestCase):
    def test_reads_jpeg_sizes_and_shapes(self):
        self.assertEqual(kit.img_size("/img/apps/spl-rta/01_spl_ko.jpg"), (736, 1600))
        self.assertEqual(kit.img_size("/img/apps/keymap/01_translate_ko.jpg"), (1199, 1600))
        self.assertEqual(kit.img_size("/img/apps/nora/01_device_ko.jpg"), (1600, 1000))
        self.assertEqual(kit.img_size("/og-image.png")[0] > 0, True)
        self.assertIsNone(kit.img_size("/img/no-such.jpg"))
        self.assertEqual(kit.shape((736, 1600)), "phone")
        self.assertEqual(kit.shape((1199, 1600)), "tablet")
        self.assertEqual(kit.shape((1600, 1000)), "wide")
        self.assertEqual(kit.shape(None), "phone")
        self.assertEqual(kit.img_attrs("/img/apps/spl-rta/01_spl_ko.jpg"), ' width="736" height="1600"')
        self.assertEqual(kit.img_attrs("/img/no-such.jpg"), "")


if __name__ == "__main__":
    unittest.main()
