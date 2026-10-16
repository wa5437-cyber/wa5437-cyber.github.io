import json, pathlib, re, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_src"))
from sitegen import pages


# 화면·메타에 나오면 안 되는 경력 건수·기간(사용자 지시). 작업 페이지의 접힌 역할 표(연도별 줄)는 따로 뺀다.
CAREER_NUMBERS = re.compile(r"\b111\b|\b66\b|\b49\b|기록된 작업|기록한 작업|2009|2024년까지|through 2024|"
                            r"recorded credits|credits on record|\{(since|total|mastering|mixing|recording)\}")


def page_text(html):
    """사람이 보는 글: <title>·메타 content 값·본문 글·alt. 스크립트(JSON-LD 포함)는 따로 본다."""
    head = html[:html.index("<body>")]
    head_text = " ".join(re.findall(r"<title>(.*?)</title>", head) + re.findall(r'content="([^"]*)"', head))
    body = re.sub(r"<script\b.*?</script>", "", html[html.index("<body>"):], flags=re.S)
    alts = " ".join(re.findall(r'\salt="([^"]*)"', body))
    return head_text + " " + re.sub(r"<[^>]+>", " ", body) + " " + alts


class StudioAboutContactTests(unittest.TestCase):
    def test_pages_exist_in_both_languages_with_hreflang_pairs(self):
        for name in ("studio", "about", "contact"):
            for lang, prefix in (("ko", ""), ("en", "/en")):
                path, html = pages.simple_page(lang, name)
                self.assertEqual(path, f"{prefix}/{name}/")
                self.assertIn('hreflang="ko"', html)
                self.assertIn('hreflang="en"', html)

    def test_studio_has_photo_hero_gallery_gear_fields_posters_and_dark_contact(self):
        _, html = pages.simple_page("ko", "studio")
        hero = re.search(r'<section class="photo-hero">.*?</section>', html, re.S).group(0)
        self.assertIn('src="/img/studio/control-room.jpg"', hero)
        self.assertIn('fetchpriority="high"', hero)
        gallery = re.search(r'<div class="gallery bento">(.*?)</div></div></section>', html, re.S).group(1)
        self.assertEqual(re.findall(r"<figcaption>(.*?)</figcaption>", gallery),
                         ["녹음 부스", "마이크 프리앰프 클로즈업", "마이크 보관함", "프리앰프와 컴프레서", "모니터 컨트롤러", "녹음 부스 안쪽"])
        # bento: 세로·가로·세로·가로·가로·가로 — 2번(프리앰프 클로즈업)은 옆으로 돌린 가로 사진(사용자 지시 10/16).
        # site.css 의 nth-child 자리와 짝이 맞아야 3칸·2칸 격자 모두 빈칸이 없다
        self.assertEqual(re.findall(r'<figure class="pic (\w+)', gallery), ["port", "land", "port", "land", "land", "land"])
        self.assertIn('src="/img/studio/preamp-closeup.jpg" alt="Neve 1073DPA 마이크 프리앰프 1채널의 빨간 게인 노브, +48V·위상 버튼, 트림 노브와 클립 LED" width="840" height="560"', gallery)
        # 부스 쇼크 마운트는 비어 있다 — 마이크가 꽂힌 것처럼 쓰지 않는다. 마이크만 찍은 사진은 뺐다(사용자 지시)
        self.assertNotIn("부스의 마이크", html)
        self.assertNotIn("microphones.jpg", html)
        for img in re.findall(r"<img [^>]+>", gallery):
            self.assertNotRegex(re.search(r'alt="([^"]*)"', img).group(1), r"마이크와|마이크를 단")
        for img in re.findall(r"<img [^>]+>", gallery):
            self.assertIn('loading="lazy"', img)
            self.assertRegex(img, r'width="\d+" height="\d+"')
            self.assertNotRegex(img, r'alt=""')
        self.assertIn("작업실에서 쓰는 장비입니다.", html)
        gear = re.search(r'<div class="gear-groups">(.*?)</div></div>(?:<p|</div>)', html, re.S).group(0)
        self.assertEqual(re.findall(r"<h3>(.*?)</h3>", gear), ["마이크", "프리앰프·컴프레서", "인터페이스·컨트롤러", "모니터"])
        self.assertEqual(re.findall(r"<li>(.*?)</li>", gear),
                         ["Neumann U87 빈티지 마이크", "Telefunken 마이크", "Grace Design m201 마이크 프리앰프", "Neve 1073DPA",
                          "Lydkraft Tube-Tech CL 1B 컴프레서", "Avid HD I/O", "Grace Design m905 모니터 컨트롤러",
                          "Focal Solo6 Be 모니터", "Dynaudio 모니터"])
        chips = re.search(r'<ul class="chips">(.*?)</ul>', html).group(1)
        self.assertEqual(re.findall(r"<li>(.*?)</li>", chips), ["음반", "영화", "연극", "뮤지컬", "방송", "행사", "오디오북"])
        self.assertIn('class="covers strip-4"', html)
        self.assertIn('href="/work/"', html)
        dark = html[html.index('<section class="band dark">'):]
        self.assertIn("<h2>위치·문의</h2>", dark)
        self.assertIn("원효로4가 120-3", dark)
        self.assertIn("open.kakao.com/o/sQhjCeZb", dark)
        self.assertIn("wa547@hanmail.net", dark)
        self.assertIn("map.naver.com", dark)
        self.assertNotIn("10:00", html)             # 운영시간 지어내지 않음
        _, en = pages.simple_page("en", "studio")
        self.assertIn("The equipment used in the studio.", en)   # 사진에 안 보이는 장비(m201·HD I/O)도 있어 "사진에 보이는" 이라 하지 않는다
        self.assertNotIn("visible in the studio photos", en)
        self.assertIn("Wonhyo-ro", en)
        self.assertIn("<li>Grace Design m201 microphone preamp</li>", en)
        self.assertIn("<li>Neumann U87 (vintage) microphone</li>", en)
        self.assertIn("<h3>Preamps &amp; compressor</h3>", en)
        self.assertIn("<figcaption>Recording booth</figcaption>", en)
        self.assertNotIn("Microphone in the booth", en)
        self.assertNotIn("microphones.jpg", en)

    def test_studio_photos_are_unique_in_both_languages(self):
        for lang in ("ko", "en"):
            _, html = pages.simple_page(lang, "studio")
            photos = re.findall(r'<img[^>]+src="(/img/studio/[^"]+)"', html)
            self.assertEqual(len(photos), 7, lang)       # 히어로 1 + 갤러리 6
            self.assertEqual(len(set(photos)), len(photos), lang)
            self.assertEqual(photos.count("/img/studio/control-room.jpg"), 1, lang)

    def test_studio_gallery_is_bento_of_six_without_head_on_rack_shots(self):
        # 정면으로 찍은 랙 사진(rack·랙 전체)은 빼고, 비스듬한 부스·클로즈업 위주 6장(사용자 지시 10/16)
        for lang in ("ko", "en"):
            _, html = pages.simple_page(lang, "studio")
            self.assertIn('<div class="gallery bento">', html)
            gal = html[html.index('<div class="gallery bento">'):]
            gal = gal[:gal.index("</section>")]
            self.assertEqual(re.findall(r'<img src="/img/studio/([^"]+)"', gal),
                             ["vocal-booth.jpg", "preamp-closeup.jpg", "mic-cabinet.jpg",
                              "preamp-compressor.jpg", "monitor-controller.jpg", "booth-corner.jpg"], lang)
            self.assertNotIn("rack.jpg", html)
            for alt in re.findall(r'<img src="/img/studio/[^"]+" alt="([^"]+)"', gal):
                self.assertTrue(alt.strip(), lang)
        _, ko = pages.simple_page("ko", "studio")
        self.assertIn("작업실에서 쓰는 장비입니다.", ko)
        self.assertNotIn("사진에 보이는 장비", ko)

    def test_studio_photo_files_are_web_sized_and_no_stale_files_remain(self):
        root = pages.ROOT / "img" / "studio"
        used = set()
        for lang in ("ko", "en"):
            _, html = pages.simple_page(lang, "studio")
            used |= set(re.findall(r'(?:src|srcset)="(/img/studio/[^" ]+)', html))
            used |= set(re.findall(r'(/img/studio/[^" ]+) \d+w', html))
        files = {p.name for p in root.glob("*.jpg")}
        self.assertEqual(files, {u.rsplit("/", 1)[1] for u in used})   # 쓰지 않는 사진 파일이 남지 않는다
        for name in files:
            cap = 300_000 if name.startswith("control-room") else 280_000
            self.assertLessEqual((root / name).stat().st_size, cap, name)
        # 프리앰프 클로즈업은 원본(768x1024)을 옆으로 돌린 가로 3:2 — 원본보다 키우지 않는다
        self.assertEqual(pages.kit.img_size("/img/studio/preamp-closeup.jpg"), (840, 560))

    def test_studio_generic_copy_is_gone(self):
        # 녹음실이 하는 일 4칸·4단계 진행 방법 같은 누구나 아는 글은 지웠다(사용자 지시)
        for lang in ("ko", "en"):
            _, html = pages.simple_page(lang, "studio")
            self.assertNotIn('class="steps"', html)
            self.assertNotIn('class="cards', html)
            for gone in ("하는 일", "진행 방법", "악기와 보컬을 녹음합니다", "What we do", "How it works"):
                self.assertNotIn(gone, html)

    def test_studio_reservation_sentence(self):
        _, ko = pages.simple_page("ko", "studio")
        self.assertIn("예약제 — 카카오톡으로 먼저 문의해 주세요.", ko)
        _, en = pages.simple_page("en", "studio")
        self.assertIn("By appointment", en)

    def test_no_moon_studio_anywhere_on_generated_site(self):
        bad = re.compile(r"moonstudio|moon studio", re.I)
        for name in pages.SIMPLE_PAGES:
            for lang in ("ko", "en"):
                self.assertNotRegex(pages.simple_page(lang, name)[1], bad, (name, lang))
        for fn in (pages.home, pages.work, pages.tools, pages.apps_index):
            for lang in ("ko", "en"):
                self.assertNotRegex(fn(lang)[1], bad, (fn.__name__, lang))
        for name in ("about", "studio"):
            self.assertNotRegex(json.dumps(pages.load_page(name), ensure_ascii=False), bad, name)

    def test_no_career_counts_or_ranges_on_pages(self):
        for name in pages.SIMPLE_PAGES:
            for lang in ("ko", "en"):
                html = pages.simple_page(lang, name)[1]
                self.assertNotRegex(page_text(html), CAREER_NUMBERS, (name, lang))
                for ld in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
                    self.assertNotRegex(ld, CAREER_NUMBERS, (name, lang))
        for lang in ("ko", "en"):
            html = pages.work(lang)[1]
            without_table = re.sub(r'<details class="roles">.*?</details>', "", html, flags=re.S)
            self.assertNotRegex(page_text(without_table), CAREER_NUMBERS, lang)
            self.assertNotIn('class="facts"', pages.simple_page(lang, "about")[1])

    def test_about_has_portrait_links_and_no_works_table(self):
        for lang, pre in (("ko", ""), ("en", "/en")):
            _, html = pages.simple_page(lang, "about")
            hero = re.search(r'<section class="hero portrait-hero">.*?</section>', html, re.S).group(0)
            self.assertIn('src="/img/about/profile.png"', hero)
            self.assertIn(f'href="{pre}/work/"', hero)
            self.assertIn(f'href="{pre}/studio/"', hero)
            self.assertNotIn('<table class="works"', html)
            for src in re.findall(r'<img[^>]+src="(/[^"]+)"', html):
                self.assertTrue((ROOT / src.lstrip("/")).exists(), src)

    def test_no_invented_claims_and_no_leftover_placeholders(self):
        bad_words = ("최고", "No.1", "수상", "영업일", "24시간",
                     "best", "award", "business day", "24 hours", "24/7", "within")
        for lang in ("ko", "en"):
            for name in ("studio", "about", "contact", "plugins"):
                _, html = pages.simple_page(lang, name)
                text = re.search(r"<main.*?</main>", html, re.S).group(0)
                for bad in bad_words:
                    self.assertNotIn(bad, text.lower() if bad.islower() else text, (lang, name, bad))
                self.assertNotRegex(text, r"\{\w+\}", (lang, name))

    def test_about_wording_and_no_separate_principle_section(self):
        d = pages.load_page("about")
        for lang in ("ko", "en"):
            titles = [x.get("title") for x in d[lang]["sections"]]
            self.assertNotIn("원칙", titles)
            self.assertNotIn("Principle", titles)
        _, ko = pages.simple_page("ko", "about")
        self.assertIn("현장에서 바로 쓰이는 것을 만듭니다.", ko)
        _, en = pages.simple_page("en", "about")
        self.assertIn("I make things that can be used on the spot, at the venue.", en)

    def test_contact_and_privacy_reuse_the_dark_contact_band(self):
        for name in ("contact", "privacy", "about", "studio"):
            for lang in ("ko", "en"):
                html = pages.simple_page(lang, name)[1]
                dark = re.search(r'<section class="band dark">(.*?)</section>', html, re.S)
                self.assertTrue(dark, (name, lang))
                self.assertIn("open.kakao.com", dark.group(1))

    def test_plugins_is_a_dark_hero_page_without_invented_features(self):
        for lang in ("ko", "en"):
            _, html = pages.simple_page(lang, "plugins")
            hero = re.search(r'<section class="hero dark-hero">(.*?)</section>', html, re.S).group(1)
            self.assertIn("VST3 · AU", hero)
            self.assertIn("open.kakao.com", hero)
            self.assertIn("mailto:wa547@hanmail.net", hero)
        self.assertIn("개발 중", pages.simple_page("ko", "plugins")[1])


class WorkPageTests(unittest.TestCase):
    def test_paths_hreflang_and_h1(self):
        for lang, path, h1 in (("ko", "/work/", "작업"), ("en", "/en/work/", "Work")):
            p, html = pages.work(lang)
            self.assertEqual(p, path)
            self.assertIn(f"<h1>{h1}</h1>", html)
            self.assertIn('hreflang="ko" href="https://mlmusicstudio.co.kr/work/"', html)
            self.assertIn('hreflang="en" href="https://mlmusicstudio.co.kr/en/work/"', html)

    def test_every_poster_once_with_alt_size_and_lazy(self):
        posters = pages.load("work_posters.json")
        for lang in ("ko", "en"):
            _, html = pages.work(lang)
            imgs = re.findall(r'<figure class="cover"[^>]*><img [^>]+>', html)
            self.assertEqual(len(imgs), len(posters), lang)
            for p in posters:
                self.assertEqual(html.count(f'src="{p["img"]}"'), 1, p["img"])
            for img in imgs:
                self.assertIn('loading="lazy"', img)
                self.assertRegex(img, r'width="324" height="324"')
                self.assertRegex(img, r'alt="[^"]+"')

    def test_category_chips_jump_to_existing_anchors_without_js(self):
        w = pages.load("work.json")
        have = {p["category"] for p in pages.load("work_posters.json")}
        for lang in ("ko", "en"):
            _, html = pages.work(lang)
            nav = re.search(r'<nav class="work-nav"[^>]*>(.*?)</nav>', html, re.S).group(1)
            targets = re.findall(r'href="#([^"]+)"', nav)
            self.assertEqual(targets, ["c-" + c["id"] for c in w["categories"] if c["key"] in have])
            for t in targets:
                self.assertEqual(html.count(f'id="{t}"'), 1, t)
            main = re.search(r"<main.*?</main>", html, re.S).group(0)
            self.assertNotIn("<script", main)
        _, en = pages.work("en")
        for label in ("Albums", "Film", "Theatre", "Musical", "Broadcast", "Events", "Audiobook"):
            self.assertIn(f">{label}</a>", en)

    def test_roles_table_is_collapsed_details_without_totals_note(self):
        for lang in ("ko", "en"):
            _, html = pages.work(lang)
            det = re.search(r'<details class="roles"><summary>(.*?)</summary>(.*?)</details>', html, re.S)
            self.assertTrue(det)
            self.assertIn('<table class="works">', det.group(2))
            self.assertNotIn('class="note"', html)
            self.assertNotIn("<details open", html)
        self.assertIn("<summary>역할이 기록된 작업</summary>", pages.work("ko")[1])
        self.assertLessEqual(pages.work("ko")[1].count("교회·찬양"), 5)
        self.assertGreaterEqual(pages.work("ko")[1].count("교회·찬양"), 1)

    def test_en_work_page_marks_korean_names(self):
        _, en = pages.work("en")
        main = re.search(r"<main.*?</main>", en, re.S).group(0)
        main = re.sub(r'\salt="[^"]*"', "", main)               # 대체 글의 고유명사는 그대로 둔다
        self.assertNotRegex(re.sub(r'<span lang="ko">.*?</span>', "", main), r"[가-힣]")

    def test_header_and_footer_link_to_work(self):
        _, html = pages.home("ko")
        self.assertIn('<li><a href="/work/">작업</a></li>', html)
        self.assertIn('href="/about/"', html)


class LegalPageLinkTests(unittest.TestCase):
    def test_legal_pages_have_no_old_home_anchors_and_policy_anchors_exist(self):
        policy = (ROOT / "policy.html").read_text(encoding="utf-8")
        self.assertIn('id="policy"', policy)
        for name in ("nora", "patchio", "sheetscope", "yul"):
            text = (ROOT / f"{name}_legal.html").read_text(encoding="utf-8")
            self.assertNotIn('href="/#', text, name)
            # I18N JSON 안의 이스케이프된 형태(\")도 남으면 안 된다
            self.assertNotIn('href=\\"/#', text, name)
            self.assertIn('href="/policy.html#policy"', text, name)
            self.assertIn('href="/apps/"', text, name)


class PrivacyPageTests(unittest.TestCase):
    def test_privacy_page_has_ads_cookie_notice_and_optout_links(self):
        _, html = pages.simple_page("ko", "privacy")
        for needle in ("Google", "쿠키", "adssettings.google.com", "aboutads.info", "/policy.html#policy", "2026-10-12"):
            self.assertIn(needle, html)
        _, en = pages.simple_page("en", "privacy")
        for needle in ("cookies", "adssettings.google.com", "aboutads.info"):
            self.assertIn(needle, en)

    def test_privacy_adsense_required_statement_and_partner_link(self):
        _, ko = pages.simple_page("ko", "privacy")
        self.assertIn("Google을 포함한 제3자 광고 공급업체는 쿠키를 사용해, 이 사이트나 다른 웹사이트에 대한 사용자의 이전 방문 기록을 바탕으로 광고를 게재합니다.", ko)
        self.assertIn("이 사이트 대부분의 페이지에는", ko)
        self.assertNotIn("이 사이트의 대부분의 페이지에는", ko)
        self.assertIn("Google이 파트너 사이트의 데이터를 사용하는 방법", ko)
        _, en = pages.simple_page("en", "privacy")
        self.assertIn("Third-party vendors, including Google, use cookies to serve ads based on a user&#x27;s prior visits to this website or other websites.", en)
        self.assertIn("How Google uses data from partner sites", en)
        for html in (ko, en):
            m = re.search(r'<a [^>]*href="https://policies\.google\.com/technologies/partner-sites"[^>]*>', html)
            self.assertTrue(m)
            self.assertIn('rel="noopener"', m.group(0))

    def test_privacy_inquiry_hosting_and_localstorage_statements(self):
        _, ko = pages.simple_page("ko", "privacy")
        self.assertIn("보내시는 분의 이메일 주소 또는 카카오톡 표시 이름과 메시지 내용을 운영자가 받게 됩니다", ko)
        self.assertIn("문의에 답하는 목적으로만", ko)
        self.assertIn("개인정보 관련 책임자: 이효섭, 연락처는 이 페이지 아래의 문의 방법.", ko)
        self.assertIn("이 사이트는 GitHub Pages에서 제공되며, 호스팅 업체가 접속 기록(IP 주소 등)을 보관할 수 있습니다.", ko)
        self.assertIn("일부 페이지(웹 도구와 정책 페이지)는", ko)
        self.assertNotIn("보관 기간", ko)           # 보관 기간은 운영자가 정할 일이라 쓰지 않는다
        _, en = pages.simple_page("en", "privacy")
        self.assertIn("the site owner receives your email address or KakaoTalk display name and the content of your message", en)
        self.assertIn("Person responsible for personal information: Hyoseop Lee, via the contact methods below.", en)
        self.assertIn("This site is served from GitHub Pages, and the hosting provider may keep access logs (such as IP addresses).", en)
        self.assertIn("some pages (the web tools and the policy pages)", en)
        self.assertNotIn("retain", en.lower())

    def test_privacy_updated_date_is_visible_in_both_languages(self):
        d = pages.load_page("privacy")
        for lang, label in (("ko", "최종 수정일: 2026-10-12"), ("en", "Last updated: 2026-10-12")):
            self.assertEqual(d[lang]["updated"], "2026-10-12")
            _, html = pages.simple_page(lang, "privacy")
            self.assertIn(label, html)

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
