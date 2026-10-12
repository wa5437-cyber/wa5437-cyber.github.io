import pathlib
import re
import unittest

CSS = (pathlib.Path(__file__).resolve().parents[2] / "assets" / "site.css").read_text(encoding="utf-8")


def rule(selector_start):
    """선택자가 정확히 selector_start 인 첫 규칙의 본문."""
    m = re.search(r"(?:^|\})\s*" + re.escape(selector_start) + r"\s*\{([^}]*)\}", CSS)
    return m.group(1) if m else ""


def rules():
    """(선택자 목록, 본문) 쌍을 차례로. 주석은 빼고, 선택자는 쉼표로 나눠 공백을 정리한다."""
    plain = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    for sel_text, block in re.findall(r"([^{}]+)\{([^}]*)\}", plain):
        yield [s.strip() for s in sel_text.split(",") if s.strip()], block


class KoreanWrapTests(unittest.TestCase):
    def test_body_keeps_korean_words_whole_and_long_latin_wraps(self):
        body = rule("body")
        self.assertIn("word-break:keep-all", body)
        self.assertIn("overflow-wrap:break-word", body)

    def test_headings_and_components_keep_words_whole(self):
        self.assertNotIn("word-break:break-all", CSS)
        wanted = ["h1", "h2", "h3", ".card", ".sub", ".pill", ".facts li", ".steps li", ".tool-list"]
        for sel_list, block in re.findall(r"([^{}]+)\{([^}]*)\}", CSS):
            if "word-break:keep-all" in block and all(w in [x.strip() for x in sel_list.split(",")] for w in wanted):
                return
        self.fail("no rule applies word-break:keep-all to headings, cards, pills, facts, steps and tool list")

    def test_cjk_override_covers_every_keep_all_selector(self):
        # 기본 keep-all 규칙(h1 을 담은 목록)의 선택자 전부에, ja·zh-Hans 되돌림 짝이 있어야 한다.
        base = [sels for sels, block in rules()
                if "h1" in sels and "word-break:keep-all" in block]
        self.assertEqual(len(base), 1)
        targets = base[0] + ["body"]
        override = set()
        for sels, block in rules():
            if "word-break:normal" in block:
                self.assertIn("line-break:strict", block)
                override.update(sels)
        for sel in targets:
            for lang in ("ja", "zh-Hans"):
                self.assertIn(f"html:lang({lang}) {sel}", override, (lang, sel))

    def test_cjk_languages_have_own_font_stacks(self):
        compact = re.sub(r"\s+", "", CSS)
        self.assertIn("html:lang(ja){--sans:", compact)
        self.assertIn("html:lang(zh-Hans){--sans:", compact)

    def test_hyphens_only_in_de_es_fr_ptbr_rules(self):
        seen = set()
        for sels, block in rules():
            if "hyphens" not in block:
                continue
            for sel in sels:
                m = re.match(r"html:lang\((de|es|fr|pt-BR)\)(?:\s|$)", sel)
                self.assertTrue(m, f"hyphens 는 de/es/fr/pt-BR 규칙에만: {sel}")
                seen.add(m.group(1))
        self.assertEqual(seen, {"de", "es", "fr", "pt-BR"})

    def test_pill_can_wrap_inside_its_container(self):
        pill = rule(".pill")
        self.assertIn("display:inline-block", pill)
        self.assertIn("max-width:100%", pill)


class HeaderNarrowTests(unittest.TestCase):
    def test_brand_and_buttons_never_wrap_vertically(self):
        self.assertIn("white-space:nowrap", rule(".brand"))
        self.assertRegex(CSS, r"\.menu summary,\.lang summary\{[^}]*white-space:nowrap")

    def test_bar_is_positioned_and_mobile_menu_is_full_width_panel(self):
        self.assertIn("position:relative", rule(".bar"))
        self.assertRegex(CSS, r"\.menu\{[^}]*position:static")
        self.assertRegex(CSS, r"\.menu \.nav\{[^}]*left:20px;right:20px;top:100%")


if __name__ == "__main__":
    unittest.main()
