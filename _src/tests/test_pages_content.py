import json, pathlib, re, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_src"))
from sitegen import pages


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
        self.assertIn('<table class="works" aria-labelledby="works-title">', html)
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

    def test_missing_photos_leave_no_broken_images_or_empty_sections(self):
        for lang in ("ko", "en"):
            for name in ("studio", "about"):
                _, html = pages.simple_page(lang, name)
                for src in re.findall(r'<img[^>]+src="(/[^"]+)"', html):
                    self.assertTrue((ROOT / src.lstrip("/")).exists(), src)
        # 사진 파일이 아직 없는 동안에는 구역 전체(제목 포함)가 사라진다
        missing = [p for p in ("img/studio/room-01.jpg", "img/studio/room-02.jpg", "img/studio/room-03.jpg",
                               "img/about/profile.jpg") if not (ROOT / p).exists()]
        if len(missing) == 4:
            for lang, h2 in (("ko", "<h2>작업실</h2>"), ("en", "<h2>The studio</h2>")):
                _, html = pages.simple_page(lang, "studio")
                self.assertNotIn('class="shots"', html)
                self.assertNotIn(h2, html)
            for lang in ("ko", "en"):
                _, html = pages.simple_page(lang, "about")
                self.assertNotIn('class="shots"', html)

    def test_works_church_items_are_marked_and_few(self):
        _, html = pages.simple_page("ko", "studio")
        self.assertLessEqual(html.count("교회·찬양"), 5)
        self.assertGreaterEqual(html.count("교회·찬양"), 1)

    def test_no_invented_claims_and_no_leftover_placeholders(self):
        bad_words = ("최고", "No.1", "수상", "영업일", "24시간",
                     "best", "award", "business day", "24 hours", "24/7", "within")
        for lang in ("ko", "en"):
            for name in ("studio", "about", "contact"):
                _, html = pages.simple_page(lang, name)
                text = re.search(r"<main.*?</main>", html, re.S).group(0)
                for bad in bad_words:
                    self.assertNotIn(bad, text.lower() if bad.islower() else text, (lang, name, bad))
                self.assertNotRegex(text, r"\{\w+\}", (lang, name))

    def test_moon_studio_links_use_http_not_https(self):
        for lang in ("ko", "en"):
            _, html = pages.simple_page(lang, "studio")
            self.assertIn('href="http://moonstudiorecording.com/"', html)
            self.assertNotIn("https://moonstudiorecording.com", html)
            _, about = pages.simple_page(lang, "about")
            self.assertIn('href="http://moonstudiorecording.com/sub/team_HS.html"', about)
            self.assertNotIn("https://moonstudiorecording.com", about)

    def test_studio_shows_reservation_sentence_and_map_link(self):
        _, ko = pages.simple_page("ko", "studio")
        self.assertIn("운영 시간은 따로 없고 예약제입니다. 카카오톡으로 먼저 문의해 주세요.", ko)
        self.assertIn("map.naver.com", ko)
        _, en = pages.simple_page("en", "studio")
        self.assertIn("by appointment", en)
        self.assertIn("map.naver.com", en)


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

    @staticmethod
    def _site_files(exts):
        """_src/, .superpowers/, .git/ 밖의 사이트 파일들."""
        skip = {"_src", ".superpowers", ".git", "node_modules"}
        for f in ROOT.rglob("*"):
            rel = f.relative_to(ROOT).parts
            if f.is_file() and f.suffix in exts and not (set(rel[:-1]) & skip):
                yield f

    def test_privacy_analytics_sentence_matches_code(self):
        # 페이지는 분석 도구를 쓰지 않는다고 말한다. 분석 스니펫이 하나라도 생기면 이 테스트가 실패하므로 글을 고쳐야 한다.
        pat = re.compile(r"googletagmanager|google-analytics|gtag\(")
        hits = [str(f.relative_to(ROOT)) for f in self._site_files({".html", ".js"})
                if pat.search(f.read_text(encoding="utf-8", errors="ignore"))]
        self.assertEqual(hits, [], f"분석 스니펫이 생겼다: privacy 페이지의 '분석 도구' 문장을 고쳐야 한다 {hits}")
        d = pages.load_page("privacy")
        self.assertIn("방문 통계를 모으는 분석 도구(Google Analytics 등)도 쓰지 않습니다", " ".join(d["ko"]["sections"][0]["paragraphs"]))
        self.assertIn("광고 서비스는 자체적으로 정보를 수집할 수 있습니다", " ".join(d["ko"]["sections"][0]["paragraphs"]))
        _, html = pages.simple_page("ko", "privacy")
        self.assertIn("방문 통계를 모으는 분석 도구(Google Analytics 등)도 쓰지 않습니다", html)
        self.assertIn("광고 서비스는 자체적으로 정보를 수집할 수 있습니다", html)
        _, en = pages.simple_page("en", "privacy")
        self.assertIn("does not use an analytics tool (such as Google Analytics)", en)
        self.assertIn("may collect information on its own", en)

    def test_site_has_no_html_form_so_privacy_page_claim_holds(self):
        forms = [str(f.relative_to(ROOT)) for f in self._site_files({".html"})
                 if "<form" in f.read_text(encoding="utf-8", errors="ignore").lower()]
        self.assertEqual(forms, [], f"<form 이 생겼다: privacy 페이지의 '입력 양식 없음' 문장을 고쳐야 한다 {forms}")
        _, html = pages.simple_page("ko", "privacy")
        self.assertIn("회원가입이 없", html)
        self.assertNotIn("회원가입", html.replace("회원가입이 없", ""))

    def test_privacy_never_claims_no_cookies_or_no_third_party_processing(self):
        bad_ko = ("쿠키를 쓰지 않", "쿠키를 사용하지 않", "쿠키가 없", "제3자가 처리하지 않", "제3자에게 전달되지 않", "외부에서 처리하지 않")
        bad_en = ("no cookies", "does not use cookies", "do not use cookies", "no third part", "no data is processed", "not processed by third")
        for lang, bad in (("ko", bad_ko), ("en", bad_en)):
            _, html = pages.simple_page(lang, "privacy")
            text = re.sub(r"<[^>]+>", " ", html).lower()
            for b in bad:
                self.assertNotIn(b.lower(), text)

    def test_privacy_is_distinguished_from_policy_html(self):
        d = pages.load_page("privacy")
        self.assertEqual(d["ko"]["h1"], "사이트 개인정보·쿠키·광고 안내")
        self.assertEqual(d["en"]["h1"], "Site privacy, cookie and advertising notice")
        _, ko = pages.simple_page("ko", "privacy")
        _, en = pages.simple_page("en", "privacy")
        self.assertIn("별도 문서이며 작성일이 따로 있습니다", ko)
        self.assertIn("separate document with its own date", en)

    def test_privacy_external_links_use_noopener_and_updated_field_matches_text(self):
        d = pages.load_page("privacy")
        for lang in ("ko", "en"):
            self.assertEqual(d[lang]["updated"], "2026-10-12")
            _, html = pages.simple_page(lang, "privacy")
            self.assertIn(d[lang]["updated"], html)
            for m in re.finditer(r'<a [^>]*href="https://[^"]*(adssettings|aboutads)[^"]*"[^>]*>', html):
                self.assertIn('rel="noopener"', m.group(0))
