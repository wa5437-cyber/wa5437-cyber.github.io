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

    def test_photo_hero_scrim_keeps_text_aa_even_over_white(self):
        # 사진 위 글: --scrim 이 사진의 가장 밝은 점(흰색)을 덮어도 제목·부제(--dark-ink)와 보조글(--dark-muted)이 4.5:1 이상
        css = CSS.read_text(encoding="utf-8")
        m = re.search(r"--scrim:rgba\((\d+),(\d+),(\d+),([.\d]+)\)", css)
        self.assertTrue(m)
        r, g, b, a = int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))
        worst = "#%02x%02x%02x" % tuple(round(a * c + (1 - a) * 255) for c in (r, g, b))
        t = tokens()
        self.assertEqual("#%02x%02x%02x" % (r, g, b), t["dark"])
        for fg in ("dark-ink", "dark-muted"):
            self.assertGreaterEqual(ratio(t[fg], worst), 4.5, f"--{fg} on scrim over white ({worst})")
        # 글이 놓이는 왼쪽 640px 까지는 scrim 이 그대로(그 뒤에서만 옅어진다)
        self.assertIn("var(--scrim) max(640px,calc(100% - 360px))", css)
        self.assertIn(".ph-copy>*{max-width:560px}", css)

    def test_dark_hero_pill_contrast(self):
        self.assertGreaterEqual(ratio(tokens()["dark-link"], "#24302f"), 4.5)

    def test_theme_color_matches_background(self):
        import sys
        sys.path.insert(0, str(CSS.parents[1] / "_src"))
        from sitegen import kit
        self.assertEqual(kit.THEME_COLOR.lower(), tokens()["bg"])


if __name__ == "__main__":
    unittest.main()
