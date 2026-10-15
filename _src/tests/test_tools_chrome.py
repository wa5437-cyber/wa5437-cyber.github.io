import pathlib, re, subprocess, sys, unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_src" / "tools"))
sys.path.insert(0, str(ROOT / "_src"))
import chrome_tools  # noqa: E402
from sitegen import check, kit, pages  # noqa: E402
from test_legacy import balanced_errors  # noqa: E402
from test_contrast import ratio  # noqa: E402

BEFORE = "947d6fe"     # 변환기를 처음 적용하기 직전 커밋(도구 9쪽 원본)
SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.S)
BLOCKS = (chrome_tools.HEAD_RE, chrome_tools.TOP_RE, chrome_tools.BOTTOM_RE)


def original(name):
    r = subprocess.run(["git", "show", f"{BEFORE}:{name}"], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        raise unittest.SkipTest(f"git show {BEFORE}:{name} 실패")
    return r.stdout


def disk(name):
    return (ROOT / name).read_text(encoding="utf-8")


def unchrome(text):
    """표시 사이 블록을 걷어내고 <style>·글꼴 링크를 빼서, 변환 전 본문과 비교할 수 있게."""
    for rx in BLOCKS:
        text = rx.sub("", text)
    text = chrome_tools.STYLE_BLOCK_RE.sub("<style></style>", text)
    return chrome_tools.FONT_LINK_RE.sub("<!-- fonts -->", text)


class ToolsChromeTests(unittest.TestCase):
    def test_every_tool_on_disk_is_transformed_and_idempotent(self):
        for name in chrome_tools.FILES:
            text = disk(name)
            self.assertEqual(chrome_tools.transform(text, name), text, name)
            raw = original(name)
            once = chrome_tools.transform(raw, name)
            self.assertEqual(once, text, name)
            self.assertEqual(chrome_tools.transform(once, name), once, name)

    def test_scripts_are_byte_identical(self):
        for name in chrome_tools.FILES:
            before, after = SCRIPT.findall(original(name)), SCRIPT.findall(disk(name))
            self.assertEqual(after, before, name)
            if name != "stage-sound-quiz.html":                    # 문제풀이는 언어 전환이 없다
                self.assertIn('<script src="i18n-core.js"></script>', disk(name))

    def test_only_head_style_and_marked_blocks_change(self):
        for name in chrome_tools.FILES:
            self.assertEqual(unchrome(disk(name)), unchrome(original(name)), name)

    def test_tags_stay_balanced(self):
        for name in chrome_tools.FILES:
            self.assertEqual(balanced_errors(disk(name)), balanced_errors(original(name)), name)
            for tag in ("header", "footer", "section", "details", "ul"):
                self.assertEqual(len(re.findall(r"<%s[\s>]" % tag, disk(name))), disk(name).count("</%s>" % tag), (name, tag))

    def test_no_old_home_anchors_and_links_resolve(self):
        for name in chrome_tools.FILES:
            text = disk(name)
            self.assertNotIn('href="/#', text, name)
            self.assertEqual(check.link_errors(ROOT, name, text), [], name)
        self.assertTrue(set(chrome_tools.FILES) <= set(check.PLAIN_LINK_FILES))

    def test_site_header_in_two_languages_without_language_menu(self):
        for name in chrome_tools.FILES:
            text = disk(name)
            for lang, label in (("ko", "웹 도구"), ("en", "Web Tools")):
                m = re.search(r'<header class="site-header chrome-%s"[^>]*>(.*?)</header>' % lang, text, re.S)
                self.assertTrue(m, (name, lang))
                wide = re.search(r'<ul class="nav nav-wide">(.*?)</ul>', m.group(1)).group(1)
                self.assertEqual(len(re.findall(r"<li>", wide)), 6, name)
                self.assertIn('aria-current="page">%s</a>' % label, wide)
                self.assertNotIn('class="lang"', m.group(1))           # 언어는 도구 자체의 선택기가 맡는다
            self.assertIn('<header class="site-header chrome-en" lang="en">', text)
            self.assertEqual(text.count('<footer class="site-footer chrome-'), 2, name)
            self.assertIn('<link rel="stylesheet" href="/assets/tools.css">', text)
            self.assertLess(text.index("</style>"), text.index("/assets/tools.css"))   # 도구 CSS 뒤에서 덮는다

    def test_related_app_strip_only_for_apps_with_detail_pages(self):
        items = chrome_tools._tool_items()
        for name in chrome_tools.FILES:
            text = disk(name)
            for lang in ("ko", "en"):
                it = items[lang]["/" + name]
                strip = re.search(r'<section class="tool-related chrome-%s".*?</section>' % lang, text, re.S)
                if it.get("app") and pages.has_detail(it["app"]):
                    self.assertTrue(strip, (name, lang))
                    self.assertIn('href="%s"' % kit.url(lang, "/apps/%s/" % it["app"]), strip.group(0))
                    self.assertRegex(strip.group(0), r'<img [^>]*width="\d+" height="\d+" loading="lazy">')
                else:
                    self.assertFalse(strip, (name, lang))

    def test_new_fonts_and_palette_in_style(self):
        for name in chrome_tools.FILES:
            text = disk(name)
            style = "".join(chrome_tools.STYLE_BLOCK_RE.findall(text)[0])
            for old in ("Space Grotesk", "#faf8f3", "#8c8677", "rgba(30,26,20,", "#f1ede3"):
                self.assertNotIn(old, style, (name, old))
                self.assertNotIn(old, text[:text.index("</head>")], (name, old))
            self.assertIn("family=Noto+Sans+KR", text)
            self.assertIn('<meta name="theme-color" content="%s">' % kit.THEME_COLOR, text)

    def test_style_map_targets_never_match_a_source_key(self):
        for target in chrome_tools.STYLE_MAP.values():
            for key in chrome_tools.STYLE_MAP:
                self.assertNotIn(key, target, (key, target))

    def test_new_tool_text_colors_meet_aa(self):
        m = chrome_tools.STYLE_MAP
        for fg in (m["#221f1a"], m["#5c574c"], m["#8c8677"], m["#2f6d4c"]):
            for bg in ("#ffffff", m["#faf8f3"], m["#f1ede3"]):
                self.assertGreaterEqual(ratio(fg, bg), 4.5, (fg, bg))

    def test_tools_css_hides_old_home_button_and_scopes_site_tokens(self):
        css = (ROOT / "assets" / "tools.css").read_text(encoding="utf-8")
        self.assertIn(".topbar .home-link{display:none}", css)
        self.assertIn("body>nav{display:none}", css)
        self.assertIn("html:not(:lang(ko)) .chrome-ko{display:none}", css)
        root = re.search(r":root\s*\{", css)
        self.assertIsNone(root)                                   # 도구 변수(--line 등)를 덮지 않는다

    def test_untouched_pages(self):
        proto = disk("eartrainer_prototype.html")
        self.assertNotIn("site-chrome", proto)
        self.assertEqual(proto, original("eartrainer_prototype.html"))

    def test_cli_check_exits_zero(self):
        r = subprocess.run([sys.executable, str(ROOT / "_src" / "tools" / "chrome_tools.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_missing_anchor_raises(self):
        raw = original("rta.html")
        for broken in (raw.replace("<body>\n", "<body class=x>\n"), chrome_tools.FONT_LINK_RE.sub("", raw),
                       raw.replace("<style>", "<style media=all>")):
            with self.assertRaises(ValueError):
                chrome_tools.transform(broken, "rta.html")
        with self.assertRaises(ValueError):
            chrome_tools.transform(raw, "other.html")


class ToolsIndexTests(unittest.TestCase):
    def test_cards_have_preview_image_name_text_and_app_link(self):
        data = pages.load("tools.json")
        for lang in ("ko", "en"):
            _, html = pages.tools(lang)
            cards = re.findall(r'<div class="tool-card">(.*?)</div></div>', html, re.S)
            n = sum(len(g["items"]) for g in data[lang]["groups"])
            self.assertEqual(len(cards), n, lang)
            for card in cards:
                img = re.search(r"<img [^>]+>", card).group(0)
                src = re.search(r'src="([^"]+)"', img).group(1)
                self.assertTrue(src.startswith("/img/tools/"), src)
                self.assertEqual(kit.img_size(src), (640, 400), src)
                self.assertIn('loading="lazy"', img)
                self.assertIn('class="tc-app"', card)
            for g in data[lang]["groups"]:
                self.assertIn("<h2>%s</h2>" % kit.esc(g["title"]), html)


if __name__ == "__main__":
    unittest.main()
