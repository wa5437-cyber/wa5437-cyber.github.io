import json, pathlib, re, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_src"))
from sitegen import pages, kit


class StudioAboutContactTests(unittest.TestCase):
    def test_pages_exist_in_both_languages_with_hreflang_pairs(self):
        for name in ("studio", "about", "contact"):
            for lang, prefix in (("ko", ""), ("en", "/en")):
                path, html = pages.simple_page(lang, name)
                self.assertEqual(path, f"{prefix}/{name}/")
                self.assertIn('hreflang="ko"', html)
                self.assertIn('hreflang="en"', html)

    def test_studio_has_works_table_address_and_contact(self):
        _, html = pages.simple_page("ko", "studio")
        self.assertIn('<table class="works">', html)
        self.assertIn("원효로4가 120-3", html)
        self.assertIn("open.kakao.com/o/sQhjCeZb", html)
        self.assertIn("wa547@hanmail.net", html)
        self.assertNotIn("10:00", html)             # 운영시간 지어내지 않음
        _, en = pages.simple_page("en", "studio")
        self.assertIn("Wonhyo-ro", en)

    def test_about_numbers_come_from_career_json(self):
        career = json.loads((ROOT / "_src" / "content" / "career.json").read_text(encoding="utf-8"))
        _, html = pages.simple_page("ko", "about")
        self.assertIn(str(career["total"]), html)
        self.assertIn(str(career["roles"]["마스터링"]), html)
        self.assertIn(str(career["since"]), html)
        self.assertNotRegex(html, r"\{(since|total|mastering|mixing|recording)\}")   # 자리표시자가 남지 않음

    def test_missing_photos_leave_no_broken_images(self):
        for name in ("studio", "about"):
            _, html = pages.simple_page("ko", name)
            for src in re.findall(r'<img[^>]+src="(/[^"]+)"', html):
                self.assertTrue((ROOT / src.lstrip("/")).exists(), src)

    def test_works_church_items_are_marked_and_few(self):
        _, html = pages.simple_page("ko", "studio")
        self.assertLessEqual(html.count("교회·찬양"), 5)
        self.assertGreaterEqual(html.count("교회·찬양"), 1)

    def test_no_invented_claims(self):
        for name in ("studio", "about", "contact"):
            _, html = pages.simple_page("ko", name)
            for bad in ("최고", "No.1", "수상", "영업일", "24시간"):
                self.assertNotIn(bad, html)

    def test_moon_studio_links_use_http_not_https(self):
        _, html = pages.simple_page("ko", "studio")
        self.assertNotIn("https://moonstudiorecording.com", html)


class FactsPlaceholderTests(unittest.TestCase):
    def test_fill_facts_uses_career_and_raises_on_unknown_key(self):
        career = {"since": 2009, "total": 111, "roles": {"마스터링": 66, "믹싱": 49, "녹음": 30}}
        secs = [{"type": "facts", "items": ["{since}년 {total}건 {mastering}/{mixing}/{recording}"]},
                {"type": "prose", "title": "{since}", "paragraphs": ["{x}"]}]
        out = pages.fill_facts(secs, career)
        self.assertEqual(out[0]["items"], ["2009년 111건 66/49/30"])
        self.assertEqual(out[1], secs[1])           # facts 가 아닌 구역은 손대지 않는다
        with self.assertRaises(KeyError):
            pages.fill_facts([{"type": "facts", "items": ["{nope}"]}], career)


class PrivacyPageTests(unittest.TestCase):
    def test_privacy_page_has_ads_cookie_notice_and_optout_links(self):
        _, html = pages.simple_page("ko", "privacy")
        for needle in ("Google", "쿠키", "adssettings.google.com", "aboutads.info", "/policy.html#policy", "2026-10-12"):
            self.assertIn(needle, html)
        _, en = pages.simple_page("en", "privacy")
        for needle in ("cookies", "adssettings.google.com", "aboutads.info"):
            self.assertIn(needle, en)

    def test_privacy_does_not_claim_tools_the_site_lacks(self):
        # 사이트가 실제로 분석 도구를 쓰지 않을 때만 "쓰지 않는다"고 말할 수 있다 — 코드로 확인
        import subprocess
        hits = subprocess.run(["grep", "-rlE", "googletagmanager|google-analytics|gtag\\(", "--include=*.html", "."],
                              cwd=ROOT, capture_output=True, text=True).stdout.strip()
        _, html = pages.simple_page("ko", "privacy")
        if hits:
            self.assertNotIn("분석 도구를 쓰지 않", html)
        else:
            self.assertIn("분석 도구", html)

    def test_privacy_has_no_collection_form_claim(self):
        _, html = pages.simple_page("ko", "privacy")
        self.assertNotIn("회원가입", html.replace("회원가입이 없", ""))

    def test_privacy_never_claims_no_cookies_or_no_third_party_processing(self):
        for lang in ("ko", "en"):
            _, html = pages.simple_page(lang, "privacy")
            text = re.sub(r"<[^>]+>", " ", html)
            for bad in ("쿠키를 쓰지 않", "쿠키를 사용하지 않", "쿠키가 없", "no cookies", "does not use cookies", "do not use cookies"):
                self.assertNotIn(bad, text)

    def test_privacy_external_links_use_noopener_and_updated_field_matches_text(self):
        d = pages.load_page("privacy")
        for lang in ("ko", "en"):
            self.assertEqual(d[lang]["updated"], "2026-10-12")
            _, html = pages.simple_page(lang, "privacy")
            self.assertIn(d[lang]["updated"], html)
            for m in re.finditer(r'<a [^>]*href="https://[^"]*(adssettings|aboutads)[^"]*"[^>]*>', html):
                self.assertIn('rel="noopener"', m.group(0))
