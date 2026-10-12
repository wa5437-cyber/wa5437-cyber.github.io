import csv, io, json, pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_src" / "tools"))
import career_stats

SAMPLE = "년도,날짜,가수/작품,제목,앨범/구분,역할\n2024,10.16,A,,EP,믹싱 마스터링\n2009,1.1,B,t,싱글,녹음\n2015,2.2,C,u,싱글,레코딩 믹싱\n"


class CareerTests(unittest.TestCase):
    def test_compute_counts_roles_and_range(self):
        rows = list(csv.DictReader(io.StringIO(SAMPLE)))
        out = career_stats.compute(rows)
        self.assertEqual(out["since"], 2009)
        self.assertEqual(out["total"], 3)
        self.assertEqual(out["roles"], {"마스터링": 1, "믹싱": 2, "녹음": 2})

    def test_career_json_matches_shape_and_rules(self):
        d = json.loads((ROOT / "_src" / "content" / "career.json").read_text(encoding="utf-8"))
        self.assertEqual(set(d), {"since", "total", "roles", "works"})
        self.assertTrue(20 <= len(d["works"]) <= 30)
        per = {}
        for w in d["works"]:
            self.assertEqual(set(w), {"year", "artist", "title", "album", "role", "church"})
            self.assertTrue(w["artist"] and w["role"])
            per[w["artist"]] = per.get(w["artist"], 0) + 1
        self.assertLessEqual(max(per.values()), 2)
        self.assertTrue(1 <= sum(1 for w in d["works"] if w["church"]) <= 5)
        self.assertEqual(d["since"], 2009)

    def test_career_json_numbers_match_the_csv_when_present(self):
        csv_path = pathlib.Path.home() / "Documents" / "홈페이지자료" / "경력_정리.csv"
        if not csv_path.exists():
            self.skipTest("경력_정리.csv 없음")
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            expect = career_stats.compute(list(csv.DictReader(f)))
        d = json.loads((ROOT / "_src" / "content" / "career.json").read_text(encoding="utf-8"))
        for k in ("since", "total", "roles"):
            self.assertEqual(d[k], expect[k])

    def test_every_work_exists_in_the_csv_when_present(self):
        csv_path = pathlib.Path.home() / "Documents" / "홈페이지자료" / "경력_정리.csv"
        if not csv_path.exists():
            self.skipTest("경력_정리.csv 없음")
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        d = json.loads((ROOT / "_src" / "content" / "career.json").read_text(encoding="utf-8"))
        have = {(int(r["년도"]), r["가수/작품"].strip(), (r["제목"] or "").strip() or None, (r["앨범/구분"] or "").strip() or None, r["역할"].strip()) for r in rows}
        for w in d["works"]:
            self.assertIn((w["year"], w["artist"], w["title"], w["album"], w["role"]), have, w)
