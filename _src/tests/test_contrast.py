import unittest


def lum(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def ratio(a, b):
    hi, lo = sorted([lum(a), lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class ContrastTests(unittest.TestCase):
    def test_text_pairs_meet_wcag_aa(self):
        pairs = [("#13363a", "#f6f0e6"), ("#47605f", "#f6f0e6"), ("#ffffff", "#b8501a"),
                 ("#9c430f", "#f6f0e6"), ("#13363a", "#ffffff")]
        for fg, bg in pairs:
            self.assertGreaterEqual(ratio(fg, bg), 4.5, f"{fg} on {bg}")


if __name__ == "__main__":
    unittest.main()
