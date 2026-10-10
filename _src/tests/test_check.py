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


if __name__ == "__main__":
    unittest.main()
