import pathlib, re, sys, tempfile, unittest
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

    def test_header_hides_language_menu_with_zero_or_one_alternate(self):
        self.assertNotIn('class="lang"', kit.header("ko", "/x/", {"ko": "/x/"}))
        self.assertNotIn('class="lang"', kit.header("ko", "/x/", {}))

    def test_english_header_uses_en_prefix_and_keeps_guides_korean_only(self):
        h = kit.header("en", "/en/", {"ko": "/", "en": "/en/"})
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
