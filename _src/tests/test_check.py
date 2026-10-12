import pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sitegen import check


def touch(root, rel, text="x"):
    p = root / rel.lstrip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class CheckTests(unittest.TestCase):
    def test_missing_preserved_files_are_reported(self):
        with tempfile.TemporaryDirectory() as td:
            errors = check.run(pathlib.Path(td))
            self.assertTrue(any("/guides/" in e or "ads.txt" in e for e in errors))

    def test_broken_internal_link_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            for p in check.PRESERVED:
                touch(root, p if not p.endswith("/") else p + "index.html")
            touch(root, "/index.html", '<a href="/nope/">x</a>')
            errors = check.run(root)
            self.assertTrue(any("/nope/" in e for e in errors))

    def test_store_link_without_campaign_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            for p in check.PRESERVED:
                touch(root, p if not p.endswith("/") else p + "index.html")
            touch(root, "/index.html", '<a href="https://apps.apple.com/app/id1?mt=8">x</a>')
            errors = check.run(root)
            self.assertTrue(any("ct=homepage" in e for e in errors))

    # --- 새 점검 ---
    def base(self, td):
        root = pathlib.Path(td)
        for p in check.PRESERVED:
            touch(root, p if not p.endswith("/") else p + "index.html")
        return root

    @staticmethod
    def html(path, alts=(), body=""):
        """canonical 과 hreflang 을 가진 최소 페이지."""
        b = check.BASE
        tags = "".join(f'<link rel="alternate" hreflang="{c}" href="{b}{p}">' for c, p in alts)
        return f'<link rel="canonical" href="{b}{path}">{tags}{body}'

    def test_store_link_without_mt8_is_reported_and_full_link_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.base(td)
            ok = f"https://apps.apple.com/app/id1?pt={check.PT}&amp;ct=homepage&amp;mt=8"
            touch(root, "/index.html", self.html("/", body=f'<a href="{ok}">x</a>'))
            self.assertEqual(check.run(root), [])
            bad = f"https://apps.apple.com/app/id1?pt={check.PT}&amp;ct=homepage"
            touch(root, "/index.html", self.html("/", body=f'<a href="{bad}">x</a>'))
            self.assertTrue(any("mt=8" in e for e in check.run(root)))

    def test_broken_src_is_reported_but_external_and_protocol_relative_are_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.base(td)
            touch(root, "/img/ok.png")
            touch(root, "/index.html", self.html("/", body=(
                '<img src="/img/ok.png"><img src="//cdn.example/x.png"><img src="https://e.com/y.png">')))
            self.assertEqual(check.run(root), [])
            touch(root, "/index.html", self.html("/", body='<img src="/img/missing.png">'))
            self.assertTrue(any("깨진 src /img/missing.png" in e for e in check.run(root)))

    def test_reciprocal_hreflang_pair_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.base(td)
            alts = [("ko", "/"), ("en", "/en/"), ("x-default", "/")]
            touch(root, "/index.html", self.html("/", alts))
            touch(root, "/en/index.html", self.html("/en/", alts))
            self.assertEqual(check.run(root), [])

    def test_hreflang_target_missing_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.base(td)
            touch(root, "/index.html", self.html("/", [("ko", "/"), ("en", "/en/")]))
            errors = check.run(root)
            self.assertTrue(any(e.startswith("hreflang 짝 불일치") and "/en/" in e for e in errors))

    def test_hreflang_without_return_link_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.base(td)
            touch(root, "/index.html", self.html("/", [("ko", "/"), ("en", "/en/")]))
            touch(root, "/en/index.html", self.html("/en/", [("en", "/en/")]))
            errors = check.run(root)
            self.assertTrue(any(e.startswith("hreflang 짝 불일치: index.html -> /en/") for e in errors))

    def test_en_page_without_ko_alternate_is_orphan(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.base(td)
            touch(root, "/en/index.html", self.html("/en/", [("en", "/en/")]))
            self.assertTrue(any("ko 페이지" in e for e in check.run(root)))

    def test_missing_or_wrong_canonical_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.base(td)
            touch(root, "/index.html", "<p>x</p>")
            self.assertTrue(any("canonical 없음" in e for e in check.run(root)))
            touch(root, "/index.html", self.html("/other/"))
            self.assertTrue(any("canonical 불일치" in e for e in check.run(root)))


if __name__ == "__main__":
    unittest.main()
