import pathlib
import re
import unittest

CSS = (pathlib.Path(__file__).resolve().parents[2] / "assets" / "site.css").read_text(encoding="utf-8")


def rule(selector_start):
    """선택자가 정확히 selector_start 인 첫 규칙의 본문."""
    m = re.search(r"(?:^|\})\s*" + re.escape(selector_start) + r"\s*\{([^}]*)\}", CSS)
    return m.group(1) if m else ""


class KoreanWrapTests(unittest.TestCase):
    def test_body_keeps_korean_words_whole_and_long_latin_wraps(self):
        body = rule("body")
        self.assertIn("word-break:keep-all", body)
        self.assertIn("overflow-wrap:break-word", body)

    def test_headings_and_components_keep_words_whole(self):
        self.assertNotIn("word-break:break-all", CSS)
        # 자동 하이픈은 언어별 규칙(de·es·fr·pt-BR)에서만 쓴다. 기본(ko/en) 규칙에는 없어야 한다.
        self.assertNotIn("hyphens", re.sub(r"html:lang\([^)]*\)[^{]*\{[^}]*\}", "", CSS))
        wanted = ["h1", "h2", "h3", ".card", ".sub", ".pill", ".facts li", ".steps li", ".tool-list"]
        for sel_list, block in re.findall(r"([^{}]+)\{([^}]*)\}", CSS):
            if "word-break:keep-all" in block and all(w in [x.strip() for x in sel_list.split(",")] for w in wanted):
                return
        self.fail("no rule applies word-break:keep-all to headings, cards, pills, facts, steps and tool list")

    def test_cjk_languages_override_keep_all(self):
        compact = re.sub(r"\s+", "", CSS)
        self.assertIn("html:lang(ja)", compact)
        self.assertIn("html:lang(zh-Hans)", compact)
        # keep-all 을 되돌리는 규칙이 같은 블록 안에 있어야 한다
        self.assertRegex(compact, r"html:lang\(ja\)[^}]*word-break:normal")
        self.assertRegex(compact, r"html:lang\(ja\)[^}]*line-break:strict")
        self.assertIn("hyphens:auto", compact)

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
