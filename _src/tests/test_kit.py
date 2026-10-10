import pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sitegen import kit


class KitTests(unittest.TestCase):
    def test_esc_escapes_quotes_and_amp(self):
        self.assertEqual(kit.esc('a & "b" <c>'), "a &amp; &quot;b&quot; &lt;c&gt;")

    def test_url_ko_is_unchanged_and_en_gets_prefix(self):
        self.assertEqual(kit.url("ko", "/apps/"), "/apps/")
        self.assertEqual(kit.url("en", "/apps/"), "/en/apps/")
        self.assertEqual(kit.url("en", "/"), "/en/")

    def test_write_folder_url_creates_index_html(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            kit.write(root, "/en/apps/", "<p>x</p>")
            self.assertEqual((root / "en/apps/index.html").read_text(encoding="utf-8"), "<p>x</p>")
            kit.write(root, "/policy.html", "<p>y</p>")
            self.assertTrue((root / "policy.html").exists())


if __name__ == "__main__":
    unittest.main()
