import pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sitegen import pages


class HomeTests(unittest.TestCase):
    def test_home_ko_and_en_paths_and_hash_redirect(self):
        path, html = pages.home("ko")
        self.assertEqual(path, "/")
        self.assertIn("location.replace('/policy.html'", html)
        self.assertIn("(policy|privacy)", html)
        path_en, html_en = pages.home("en")
        self.assertEqual(path_en, "/en/")
        self.assertIn('<html lang="en">', html_en)

    def test_home_has_three_cards_and_contact_links_free_of_made_up_hours(self):
        _, html = pages.home("ko")
        for word in ("앱", "플러그인", "녹음실", "웹 도구"):
            self.assertIn(word, html)
        self.assertNotIn("10:00", html)

    def test_home_links_point_to_existing_site_areas(self):
        _, html = pages.home("ko")
        for href in ('href="/apps/"', 'href="/studio/"', 'href="/tools/"'):
            self.assertIn(href, html)

    def test_build_all_writes_home_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            pages.build_all(root)
            self.assertTrue((root / "index.html").exists())
            self.assertTrue((root / "en/index.html").exists())


if __name__ == "__main__":
    unittest.main()
