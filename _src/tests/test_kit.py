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
        self.assertIn('<a class="skip" href="#main">Skip to content</a>', html)
        self.assertIn('href="/en/apps/"', html)           # 상단 메뉴는 영어 페이지로
        self.assertIn('href="/en/"', html)                # 브랜드 링크
        self.assertIn('hreflang="ja" lang="ja" aria-current="true"', html)
        self.assertIn(">JA ▾<", html)
        self.assertEqual(html.count('rel="alternate" hreflang="ja"'), 1)

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
        for label in ("앱", "웹 도구", "플러그인", "녹음실", "가이드"):
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


if __name__ == "__main__":
    unittest.main()
