import pathlib
import re
import unittest

CSS = pathlib.Path(__file__).resolve().parents[2] / "assets" / "site.css"


def lum(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def ratio(a, b):
    hi, lo = sorted([lum(a), lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def tokens():
    """assets/site.css 의 :root 색 토큰(--이름:#hex)을 읽는다."""
    css = CSS.read_text(encoding="utf-8")
    return {name: "#" + hexv for name, hexv in re.findall(r"--([a-z0-9-]+):\s*#([0-9a-fA-F]{6})", css)}


GUIDE_CSS = CSS.parent / "guide.css"


def guide_tokens():
    css = GUIDE_CSS.read_text(encoding="utf-8")
    return {name: "#" + hexv for name, hexv in re.findall(r"--([a-z0-9-]+):\s*#([0-9a-fA-F]{6})", css)}


class GuideContrastTests(unittest.TestCase):
    def test_guide_text_pairs_meet_wcag_aa(self):
        t = guide_tokens()
        for fg in ("text-primary", "text-secondary", "text-tertiary", "teal"):
            for bg in ("bg", "bg-alt", "panel", "soft"):
                self.assertGreaterEqual(ratio(t[fg], t[bg]), 4.5, f"guide --{fg} on --{bg}")
        self.assertGreaterEqual(ratio("#ffffff", t["teal"]), 4.5, "white on guide --teal")

    def test_old_low_contrast_grey_is_gone(self):
        self.assertNotIn("#8c8677", GUIDE_CSS.read_text(encoding="utf-8").lower())

    def test_guide_tokens_follow_site_tokens(self):
        g, s = guide_tokens(), tokens()
        for gk, sk in (("bg", "bg"), ("panel", "panel"), ("line", "line"), ("teal", "accent"),
                       ("text-primary", "ink"), ("text-secondary", "ink2")):
            self.assertEqual(g[gk].lower(), s[sk].lower(), gk)


class ContrastTests(unittest.TestCase):
    def test_documented_tokens_match_plan(self):
        t = tokens()
        expected = {"bg": "#f4f5f3", "panel": "#ffffff", "ink": "#202426", "ink2": "#5b6468",
                    "accent": "#23695c", "accent-hover": "#194e45", "accent-ink": "#23695c",
                    "line": "#d5dadb", "control": "#7a858a",
                    "dark": "#171d20", "dark-ink": "#f4f5f3", "dark-muted": "#b5c0c4", "dark-link": "#8dd7bd"}
        for name, value in expected.items():
            self.assertEqual(t.get(name, "").lower(), value, f"--{name}")

    def test_text_pairs_meet_wcag_aa(self):
        t = tokens()
        pairs = [("ink", "bg"), ("ink2", "bg"), ("ink2", "panel"), ("ink2", "stage"), ("ink2", "soft"),
                 ("accent-ink", "bg"), ("accent-ink", "panel"), ("accent-ink", "soft"), ("accent-hover", "bg"),
                 ("ink", "soft"), ("ink", "stage"),
                 # 어두운 띠(녹음실): 본문·보조문자·링크
                 ("dark-ink", "dark"), ("dark-muted", "dark"), ("dark-link", "dark")]
        for fg, bg in pairs:
            self.assertGreaterEqual(ratio(t[fg], t[bg]), 4.5, f"--{fg} on --{bg}")
        self.assertGreaterEqual(ratio("#ffffff", t["accent"]), 4.5, "white on --accent")
        self.assertGreaterEqual(ratio("#ffffff", t["accent-hover"]), 4.5, "white on --accent-hover")

    def test_control_borders_meet_non_text_contrast(self):
        # 조작 경계(버튼·메뉴 테두리)는 WCAG 1.4.11 의 3:1. 장식 경계 --line 은 조작 경계에 쓰지 않는다.
        t = tokens()
        for bg in ("bg", "panel", "dark"):
            self.assertGreaterEqual(ratio(t["control"], t[bg]), 3.0, f"--control on --{bg}")

    def test_photo_hero_text_uses_solid_dark_background(self):
        # 글과 사진을 분리했으므로 사진 밝기 대신 단색 배경의 실제 토큰 쌍을 검사한다.
        css = CSS.read_text(encoding="utf-8")
        hero = re.search(r"\.photo-hero\{([^}]+)\}", css).group(1)
        self.assertIn("background:var(--dark)", hero)
        for selector, fg in ((".photo-hero h1", "dark-ink"), (".photo-hero .sub", "dark-muted")):
            block = re.search(re.escape(selector) + r"\{([^}]+)\}", css).group(1)
            self.assertIn("color:var(--%s)" % fg, block)
            self.assertGreaterEqual(ratio(tokens()[fg], tokens()["dark"]), 4.5)

    def test_dark_hero_pill_contrast(self):
        self.assertGreaterEqual(ratio(tokens()["dark-link"], "#24302f"), 4.5)

    def test_theme_color_matches_background(self):
        import sys
        sys.path.insert(0, str(CSS.parents[1] / "_src"))
        from sitegen import kit
        self.assertEqual(kit.THEME_COLOR.lower(), tokens()["bg"])


if __name__ == "__main__":
    unittest.main()
