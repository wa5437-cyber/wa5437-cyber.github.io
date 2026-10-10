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


class ContrastTests(unittest.TestCase):
    def test_documented_tokens_match_plan(self):
        t = tokens()
        expected = {"bg": "#f6f0e6", "ink": "#13363a", "ink2": "#47605f",
                    "accent": "#b8501a", "accent-ink": "#9c430f"}
        for name, value in expected.items():
            self.assertEqual(t.get(name, "").lower(), value, f"--{name}")

    def test_text_pairs_meet_wcag_aa(self):
        t = tokens()
        pairs = [("ink", "bg"), ("ink2", "bg"), ("ink2", "panel"), ("accent-ink", "bg"),
                 ("accent-ink", "soft"), ("ink", "soft")]
        for fg, bg in pairs:
            self.assertGreaterEqual(ratio(t[fg], t[bg]), 4.5, f"--{fg} on --{bg}")
        self.assertGreaterEqual(ratio("#ffffff", t["accent"]), 4.5, "white on --accent")


if __name__ == "__main__":
    unittest.main()
