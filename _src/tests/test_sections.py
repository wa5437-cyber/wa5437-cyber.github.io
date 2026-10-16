import pathlib, re, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sitegen import sections, pages

CTX = {"contact": {"kakao": "https://open.kakao.com/o/x", "email": "a@b.kr"},
       "img_exists": lambda p: p == "/img/ok.jpg", "career": None}


class SectionTests(unittest.TestCase):
    def test_prose_escapes_and_renders_paragraphs(self):
        html = sections.render([{"type": "prose", "title": "T & U", "paragraphs": ["a <b>", "c"]}], "ko", CTX)
        self.assertIn("<h2>T &amp; U</h2>", html)
        self.assertIn("<p>a &lt;b&gt;</p>", html)
        self.assertEqual(html.count("<p>"), 2)

    def test_contact_has_kakao_and_email(self):
        html = sections.render([{"type": "contact", "title": "문의", "text": None}], "ko", CTX)
        self.assertIn('href="https://open.kakao.com/o/x"', html)
        self.assertIn('href="mailto:a@b.kr"', html)

    def test_photos_skip_missing_files_and_hide_empty_section(self):
        one = sections.render([{"type": "photos", "title": "사진", "items": [
            {"src": "/img/ok.jpg", "alt": "a"}, {"src": "/img/missing.jpg", "alt": "b"}]}], "ko", CTX)
        self.assertIn("/img/ok.jpg", one)
        self.assertNotIn("missing.jpg", one)
        none = sections.render([{"type": "photos", "title": "사진", "items": [
            {"src": "/img/missing.jpg", "alt": "b"}]}], "ko", CTX)
        self.assertEqual(none.strip(), "")

    def test_new_sections_gallery_gear_chips_posters(self):
        ctx = dict(CTX, img_exists=lambda p: p != "/img/missing.jpg", gear={"ko": ["A <b>"], "en": ["B"]},
                   work={"categories": [{"key": "음반", "id": "album", "ko": "음반", "en": "Albums"},
                                        {"key": "영화", "id": "film", "ko": "영화", "en": "Film"}]},
                   posters=[{"img": "/img/work/01_00.jpg", "artist": "가수", "title": None, "category": "음반"},
                            {"img": "/img/work/02_08.jpg", "artist": None, "title": "작품 & <x>", "category": "영화"}])
        html = sections.render([
            {"type": "gallery", "title": "G", "items": [{"src": "/img/a.jpg", "caption": "C1", "feature": True, "alt": "A1"},
                                                       {"src": "/img/missing.jpg", "caption": "C2"}]},
            {"type": "gear", "title": "장비"}, {"type": "chips", "title": "분야"},
            {"type": "posters", "title": "P", "items": ["/img/work/02_08.jpg", "/img/work/01_00.jpg"],
             "more": {"text": "더", "href": "/work/"}}], "ko", ctx)
        self.assertIn('<figure class="pic land feature"><img src="/img/a.jpg" alt="A1"', html)   # 크기 모름 → land
        self.assertIn("<figcaption>C1</figcaption>", html)
        self.assertNotIn("missing.jpg", html)
        self.assertIn('<div class="gear-groups"><div class="gear-group"><ul class="gear"><li>A &lt;b&gt;</li></ul></div></div>', html)
        self.assertIn("<li>음반</li><li>영화</li>", html)
        self.assertIn('alt="작품 &amp; &lt;x&gt;"', html)
        self.assertIn('alt="가수 — 음반"', html)                 # 제목이 없으면 "아티스트 — 분야"
        self.assertIn('class="covers strip-', html)
        self.assertIn('<a class="more" href="/work/">더 →</a>', html)
        en = sections.render([{"type": "chips", "title": "F"}], "en", ctx)
        self.assertIn("<li>Albums</li><li>Film</li>", en)

    def test_cover_cols_avoid_lonely_last_row(self):
        self.assertEqual(sections.cover_cols(10), 5)
        self.assertEqual(sections.cover_cols(8), 4)
        self.assertEqual(sections.cover_cols(6), 6)
        self.assertEqual(sections.cover_cols(7), 4)

    def test_works_without_career_is_hidden(self):
        self.assertEqual(sections.render([{"type": "works", "title": "대표작"}], "ko", CTX).strip(), "")

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            sections.render([{"type": "nope"}], "ko", CTX)


class PluginsPageTests(unittest.TestCase):
    def test_plugins_page_ko_en(self):
        path, html = pages.simple_page("ko", "plugins")
        self.assertEqual(path, "/plugins/")
        self.assertIn('<html lang="ko">', html)
        self.assertIn("VST3", html)
        self.assertIn("open.kakao.com", html)
        path_en, html_en = pages.simple_page("en", "plugins")
        self.assertEqual(path_en, "/en/plugins/")
        self.assertIn('hreflang="ko"', html_en)

    def test_about_html_is_a_stub_pointing_to_new_about(self):
        text = (pages.ROOT / "about.html").read_text(encoding="utf-8")
        self.assertIn('rel="canonical" href="https://mlmusicstudio.co.kr/about/"', text)
        self.assertIn('http-equiv="refresh"', text)
        self.assertIn('href="/about/"', text)
        self.assertNotIn("adsbygoogle", text)       # 넘기기만 하는 페이지에는 광고를 넣지 않는다
        self.assertNotIn("noindex", text)           # 옛 주소의 색인을 새 주소로 넘기려면 noindex 가 없어야 한다

    def test_plugins_is_noindex_without_ads_and_not_in_sitemap(self):
        self.assertTrue(pages.is_noindex("plugins"))
        for lang in ("ko", "en"):
            _, html = pages.simple_page(lang, "plugins")
            self.assertIn('<meta name="robots" content="noindex,follow">', html)
            self.assertNotIn("adsbygoogle", html)
            self.assertIn('rel="canonical"', html)
        sm = (pages.ROOT / "sitemap.xml").read_text(encoding="utf-8")
        self.assertNotIn("/plugins/<", sm)
        self.assertNotIn("/en/plugins/<", sm)

    def test_other_pages_stay_indexable_without_ads(self):
        for name in ("studio", "about", "contact", "privacy"):
            self.assertFalse(pages.is_noindex(name), name)
            for lang in ("ko", "en"):
                _, html = pages.simple_page(lang, name)
                self.assertNotIn('name="robots"', html, (lang, name))
                self.assertNotIn("adsbygoogle", html, (lang, name))     # 광고는 가이드·웹 도구에만
                self.assertIn('name="google-adsense-account"', html, (lang, name))

    def test_noindex_flag_is_top_level_and_shared_by_both_languages(self):
        d = pages.load_page("plugins")
        self.assertIs(d["noindex"], True)
        self.assertNotIn("noindex", d["ko"])
        self.assertNotIn("noindex", d["en"])

    def test_about_profile_page_json_ld(self):
        import json, re
        guide = (pages.ROOT / "guides" / "gain-staging-basics.html").read_text(encoding="utf-8")
        author = json.loads(re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', guide, re.S).group(1))["author"]
        for lang, job in (("ko", "사운드 엔지니어"), ("en", "Sound engineer")):
            _, html = pages.simple_page(lang, "about")
            raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
            ld = json.loads(raw)
            self.assertEqual(ld["@type"], "ProfilePage")
            person = ld["mainEntity"]
            self.assertEqual(person["@type"], "Person")
            self.assertEqual(person["name"], author["name"])
            self.assertEqual(person["alternateName"], "Hyoseop Lee")
            self.assertEqual(person["jobTitle"], job)
            self.assertEqual(person["url"], "https://mlmusicstudio.co.kr/about/")
            self.assertNotIn("sameAs", person)                  # 외부 팀 페이지로 잇지 않는다(사용자 지시)
            self.assertEqual(person["image"], "https://mlmusicstudio.co.kr/img/about/profile.png")
        for name in ("studio", "contact", "privacy", "plugins"):
            _, html = pages.simple_page("ko", name)
            self.assertNotIn("ProfilePage", html, name)

    def test_profile_ld_escapes_script_end(self):
        out = pages.profile_ld("ko", {"name": "a</script>", "alternateName": "b", "jobTitle": {"ko": "c"}})
        self.assertEqual(out.count("</script>"), 1)


CAREER = {"works": [
    {"year": 2020, "artist": "A", "title": "T1", "album": None, "role": "믹싱", "church": False},
    {"year": 2021, "artist": "B", "title": None, "album": None, "role": "녹음", "church": True},
    {"year": 2022, "artist": "C <b>&", "title": "X <b>&", "album": None, "role": "마스터링", "church": False},
]}


class MoreSectionTests(unittest.TestCase):
    def test_list_cards_steps_facts_escape(self):
        e = "<i>&"
        html = sections.render([
            {"type": "list", "title": "L", "items": [e]},
            {"type": "cards", "title": None, "items": [{"title": e, "text": e}]},
            {"type": "steps", "title": "S", "items": [{"t": e, "d": e}]},
            {"type": "facts", "items": [e]}], "ko", CTX)
        self.assertNotIn("<i>", html)
        self.assertEqual(html.count("&lt;i&gt;&amp;"), 6)
        for cls in ('class="bullets"', 'class="cards c3"', 'class="steps"', 'class="facts"'):
            self.assertIn(cls, html)

    def test_contact_address_ko_en_and_map(self):
        ctx = dict(CTX, contact=dict(CTX["contact"], address={"ko": "서울 가", "en": "Seoul A"},
                                     map="https://map.example/x"))
        sec = [{"type": "contact", "title": "c", "text": "t"}]
        ko = sections.render(sec, "ko", ctx)
        en = sections.render(sec, "en", ctx)
        self.assertIn("서울 가", ko)
        self.assertNotIn("Seoul A", ko)
        self.assertIn("Seoul A", en)
        self.assertIn('href="https://map.example/x"', ko)
        self.assertIn("<p>t</p>", ko)
        self.assertNotIn("addr", sections.render(sec, "ko", CTX))

    def test_works_rows_escape_pill_and_labels(self):
        ctx = dict(CTX, career=CAREER)
        sec = [{"type": "works", "title": "대표작", "note": "n <b>"}]
        ko = sections.render(sec, "ko", ctx)
        self.assertIn('<h2 id="works-title">대표작</h2>', ko)
        self.assertIn('<table class="works" aria-labelledby="works-title">', ko)
        self.assertNotIn("<caption", ko)
        for label in ("연도", "아티스트", "작품", "역할"):
            self.assertIn(f"<th>{label}</th>", ko)
        for v in ("2020", "2021", "2022", "T1", "믹싱", "녹음", "마스터링"):
            self.assertIn(v, ko)
        self.assertNotIn("<b>", ko)
        self.assertIn("C &lt;b&gt;&amp;", ko)
        self.assertIn("X &lt;b&gt;&amp;", ko)
        self.assertEqual(ko.count('class="pill"'), 1)
        self.assertIn("B <span class=\"pill\">교회·찬양</span>", ko)
        self.assertIn('<td data-label="작품"></td>', ko)
        self.assertIn('<p class="note">n &lt;b&gt;</p>', ko)
        en = sections.render(sec, "en", ctx)
        for label in ("Year", "Artist", "Work", "Role"):
            self.assertIn(f"<th>{label}</th>", en)
        self.assertIn("Worship", en)


def _en_roles(html):
    return re.findall(r'<td data-label="Role">(.*?)</td>', html)


def _strip_ko_spans(html):
    return re.sub(r'<span lang="ko">.*?</span>', "", html)


class EnglishWorksTableTests(unittest.TestCase):
    def _render(self, lang, *rows):
        base = {"year": 2020, "artist": "A", "title": None, "album": None, "role": "믹싱", "church": False}
        ctx = dict(CTX, career={"works": [dict(base, **r) for r in rows]})
        return sections.render([{"type": "works", "title": "t"}], lang, ctx)

    def test_role_mapping_single_multi_and_phrases(self):
        roles = ["마스터링", "믹싱", "녹음", "레코딩", "음악믹싱", "음악 믹싱", "믹싱 스튜디오",
                 "믹싱 마스터링", "녹음 믹싱 마스터링", "레코딩 믹싱 마스터링"]
        html = self._render("en", *[{"role": r} for r in roles])
        self.assertEqual(_en_roles(html), [
            "Mastering", "Mixing", "Recording", "Recording", "Score mixing", "Score mixing", "Mixing (studio)",
            "Mixing, Mastering", "Recording, Mixing, Mastering", "Recording, Mixing, Mastering"])

    def test_unknown_role_token_kept_in_ko_span(self):
        html = self._render("en", {"role": "믹싱 편곡"})
        self.assertEqual(_en_roles(html), ['Mixing, <span lang="ko">편곡</span>'])

    def test_albums_and_korean_names_are_marked(self):
        html = self._render("en",
                            {"title": "곡명", "album": "싱글"},
                            {"title": None, "album": "EP 첫 번째"},
                            {"title": None, "album": "EP 두 번째"},
                            {"artist": "배이성", "title": "Walk", "album": "성장통"})
        self.assertIn('<span lang="ko">곡명</span> <span class="album">Single</span>', html)
        self.assertIn('<td data-label="Work">EP no.1</td>', html)
        self.assertIn('<td data-label="Work">EP no.2</td>', html)
        self.assertIn('<td data-label="Artist"><span lang="ko">배이성</span></td>', html)
        self.assertIn('<span class="album"><span lang="ko">성장통</span></span>', html)

    def test_no_hangul_outside_ko_spans_in_the_real_english_table(self):
        import json
        career = json.loads((pages.ROOT / "_src" / "content" / "career.json").read_text(encoding="utf-8"))
        html = sections.render([{"type": "works", "title": "t"}], "en", dict(CTX, career=career))
        self.assertNotRegex(_strip_ko_spans(html), r"[가-힣]")
        for cell in _en_roles(html):
            self.assertNotRegex(_strip_ko_spans(cell), r"[가-힣]")
        for lang in ("en",):
            for name in ("studio", "about"):
                _, page = pages.simple_page(lang, name)
                main = re.search(r"<main.*?</main>", page, re.S).group(0)
                main = re.sub(r'\salt="[^"]*"', "", main)       # 포스터 대체 글의 한글 고유명사는 그대로 둔다
                self.assertNotRegex(_strip_ko_spans(main), r"[가-힣]", name)

    def test_ko_table_is_unchanged(self):
        html = self._render("ko", {"role": "음악 믹싱 마스터링"}, {"title": "곡", "album": "싱글"})
        self.assertIn('<td data-label="역할">음악 믹싱 마스터링</td>', html)
        self.assertIn('<td data-label="작품">곡 <span class="album">싱글</span></td>', html)
        self.assertNotIn('lang="ko"', html)

    def test_title_contained_in_artist_shows_dash_or_album(self):
        for lang in ("ko", "en"):
            html = self._render(lang, {"artist": "영화 극한직업", "title": "극한직업"})
            self.assertIn("—</td>", html, lang)
            self.assertEqual(html.count("극한직업"), 1, lang)      # 아티스트 칸에만
            html = self._render(lang, {"artist": "뮤지컬 보이A", "title": "보이A", "album": "OST"})
            self.assertNotIn("—", html, lang)
            self.assertIn("OST</td>", html, lang)
            self.assertEqual(html.count("보이"), 1, lang)
        html = self._render("ko", {"artist": "A", "title": "T"})          # 겹치지 않으면 그대로
        self.assertIn('<td data-label="작품">T</td>', html)


class WorksAlbumAndLinksTests(unittest.TestCase):
    def _works(self, *rows):
        base = {"year": 2020, "artist": "A", "title": None, "album": None, "role": "믹싱", "church": False}
        ctx = dict(CTX, career={"works": [dict(base, **r) for r in rows]})
        return sections.render([{"type": "works", "title": "t"}], "ko", ctx)

    def test_works_without_title_has_no_label_link(self):
        ctx = dict(CTX, career=CAREER)
        html = sections.render([{"type": "works"}], "ko", ctx)
        self.assertIn('<table class="works">', html)
        self.assertNotIn("aria-labelledby", html)

    def test_title_and_album_both_shown_with_album_span(self):
        html = self._works({"title": "곡명", "album": "앨범 <i>&"})
        self.assertIn('<td data-label="작품">곡명 <span class="album">앨범 &lt;i&gt;&amp;</span></td>', html)

    def test_album_only_row_shows_album_alone(self):
        html = self._works({"title": None, "album": "EP 첫 번째"})
        self.assertIn('<td data-label="작품">EP 첫 번째</td>', html)
        self.assertNotIn('class="album"', html)      # 작품명 자리의 앨범은 작은 보조 글씨가 아니다

    def test_title_only_and_neither(self):
        html = self._works({"title": "T"}, {"title": None, "album": None})
        self.assertIn('<td data-label="작품">T</td>', html)
        self.assertIn('<td data-label="작품"></td>', html)

    def test_prose_links_escape_and_card_href(self):
        html = sections.render([
            {"type": "prose", "title": None, "paragraphs": ["p"],
             "links": [{"text": "A <b>", "href": "http://x.example/?a=1&b=2"}]},
            {"type": "cards", "title": None, "items": [
                {"title": "C1", "text": "t1", "href": "/apps/"}, {"title": "C2", "text": "t2"}]}], "ko", CTX)
        self.assertIn('<a href="http://x.example/?a=1&amp;b=2" rel="noopener">A &lt;b&gt;</a>', html)
        self.assertIn('<a class="card" href="/apps/"><h3>C1</h3><p>t1</p></a>', html)
        self.assertIn('<div class="card"><h3>C2</h3><p>t2</p></div>', html)


class SitemapAndBuildTests(unittest.TestCase):
    def _sitemap(self, root):
        (root / "sitemap.xml").write_text(
            '<urlset>\n  <url><loc>https://mlmusicstudio.co.kr/about.html</loc></url>\n</urlset>\n', encoding="utf-8")
        return root / "sitemap.xml"

    def test_about_swap_only_when_new_page_built(self):
        with tempfile.TemporaryDirectory() as d:
            f = self._sitemap(pathlib.Path(d))
            pages.update_sitemap(d, ["/", "/plugins/"])
            t = f.read_text(encoding="utf-8")
            self.assertIn("/about.html<", t)
            self.assertNotIn("/about/<", t)
            pages.update_sitemap(d, ["/", "/about/"])
            pages.update_sitemap(d, ["/", "/about/"])
            t = f.read_text(encoding="utf-8")
            self.assertNotIn("/about.html<", t)
            self.assertEqual(t.count("/about/<"), 1)

    def test_noindex_paths_are_removed_and_never_added(self):
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "sitemap.xml"
            f.write_text('<urlset>\n<url><loc>https://mlmusicstudio.co.kr/plugins/</loc></url>\n'
                         '<url><loc>https://mlmusicstudio.co.kr/studio/</loc></url>\n</urlset>\n', encoding="utf-8")
            for _ in range(2):
                pages.update_sitemap(d, ["/studio/", "/plugins/", "/en/plugins/"], (), ["/plugins/", "/en/plugins/"])
            t = f.read_text(encoding="utf-8")
            self.assertNotIn("plugins", t)
            self.assertEqual(t.count("/studio/<"), 1)

    def test_build_all_writes_noindex_page_but_keeps_it_out_of_sitemap(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "sitemap.xml").write_text("<urlset>\n</urlset>\n", encoding="utf-8")
            with mock.patch.object(pages, "SIMPLE_PAGES", ("plugins", "studio")):
                pages.build_all(d)
            t = (pathlib.Path(d) / "sitemap.xml").read_text(encoding="utf-8")
            self.assertTrue((pathlib.Path(d) / "plugins" / "index.html").exists())
            self.assertNotIn("/plugins/", t)
            self.assertIn("/studio/<", t)
            self.assertIn("/en/studio/<", t)

    def test_build_all_skips_page_without_json(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(pages, "SIMPLE_PAGES", ("plugins", "nonexistent")):
                pages.build_all(d)
            root = pathlib.Path(d)
            self.assertTrue((root / "plugins" / "index.html").exists())
            self.assertTrue((root / "en" / "plugins" / "index.html").exists())
            self.assertFalse((root / "nonexistent").exists())
