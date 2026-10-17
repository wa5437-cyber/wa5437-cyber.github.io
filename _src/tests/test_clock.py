"""온라인 타이머·메트로놈 페이지(8개 언어 × 2), 번역 사전, 순수 계산 모듈(node) 점검."""
import json
import pathlib
import re
import shutil
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_src"))
from sitegen import check, clock, kit, pages  # noqa: E402

LANGS = kit.LANGS
TOOLS = clock.TOOLS
ASSETS = ROOT / "assets"


def content(tool, lang):
    return clock.load(tool, lang)


def text_len(c):
    return len(re.sub(r"\s", "", clock.article_text(c)))


class ContentTests(unittest.TestCase):
    def test_every_language_has_every_ui_key(self):
        for tool in TOOLS:
            ko = set(content(tool, "ko")["ui"])
            for lang in LANGS:
                c = content(tool, lang)
                self.assertEqual(set(c["ui"]), ko, (tool, lang))
                self.assertTrue(all(isinstance(v, str) and (v.strip() or k == "dur_sep") for k, v in c["ui"].items()), (tool, lang))
                self.assertEqual(set(c["related"]["items"]), set(content(tool, "ko")["related"]["items"]), (tool, lang))
                for k in ("title", "description", "h1", "sub"):
                    self.assertTrue(c["meta"][k].strip(), (tool, lang, k))

    def test_ui_keys_used_by_scripts_and_templates_exist(self):
        for tool, js in (("timer", "timer.js"), ("metronome", "metronome.js")):
            keys = set(re.findall(r"\btr\('([a-z_0-9]+)'", (ASSETS / js).read_text(encoding="utf-8")))
            keys |= set(re.findall(r"\bui\.([a-z_0-9]+)", (ASSETS / js).read_text(encoding="utf-8")))
            src = pathlib.Path(clock.__file__).read_text(encoding="utf-8")
            shell = src[src.index(f"def {tool}_shell"):]
            shell = shell[:shell.index("\ndef ", 5)] if "\ndef " in shell[5:] else shell
            keys |= set(re.findall(r'\be\("([a-z_0-9]+)"\)', shell)) | set(re.findall(r'\bu\["([a-z_0-9]+)"\]', shell))
            keys |= {"noscript", "tool_name"}
            keys = {k for k in keys if not k.endswith("_")}      # tab_ + mode 처럼 이어 붙여 쓰는 접두사는 아래에서 따로
            if tool == "timer":
                keys |= {"tab_" + m for m in ("countdown", "stopwatch", "range", "interval", "booking")}
                keys |= {"preset_" + m for m in ("mix", "pomodoro", "practice", "custom")}
                keys |= {"sound_" + m for m in ("bell", "beep", "chime")}
            else:
                keys |= {"term_" + t for t in ("largo", "larghetto", "adagio", "andante", "moderato", "allegro", "vivace", "presto")}
                keys |= {"sub_" + m for m in ("quarter", "eighth", "triplet", "sixteenth")}
                keys |= {"sound_" + m for m in ("click", "wood", "beep")}
            for lang in LANGS:
                missing = keys - set(content(tool, lang)["ui"])
                self.assertEqual(missing, set(), (tool, lang))

    def test_article_length_ko_en_and_proportional_others(self):
        for tool in TOOLS:
            ko = text_len(content(tool, "ko"))
            self.assertGreaterEqual(ko, 3000, tool)
            self.assertGreaterEqual(len(clock.article_text(content(tool, "en")).split()), 500, tool)
            for lang in LANGS:
                self.assertGreaterEqual(text_len(content(tool, lang)), ko * 0.7, (tool, lang))

    def test_faq_has_three_to_five_questions_and_steps(self):
        for tool in TOOLS:
            for lang in LANGS:
                blocks = [b for s in content(tool, lang)["article"] for b in s["blocks"]]
                faq = [b for b in blocks if "faq" in b]
                self.assertEqual(len(faq), 1, (tool, lang))
                self.assertTrue(3 <= len(faq[0]["faq"]) <= 5, (tool, lang))
                self.assertTrue(any("ol" in b and len(b["ol"]) >= 5 for b in blocks), (tool, lang))

    def test_no_hangul_outside_ko_and_meta_lengths(self):
        for tool in TOOLS:
            for lang in LANGS:
                c = content(tool, lang)
                raw = json.dumps(c, ensure_ascii=False)
                if lang != "ko":
                    self.assertIsNone(re.search(r"[가-힣]", raw), (tool, lang))
                self.assertLessEqual(len(c["meta"]["title"]), 80, (tool, lang))
                lo = 80 if lang in ("ja", "zh-Hans") else 110
                self.assertTrue(lo <= len(c["meta"]["description"]) <= 165, (tool, lang, len(c["meta"]["description"])))


class PageTests(unittest.TestCase):
    def test_pages_exist_for_every_language_with_pairs_canonical_ads_and_jsonld(self):
        for tool in TOOLS:
            alts = clock.tool_alts(tool)
            self.assertEqual(list(alts), list(LANGS))
            for lang in LANGS:
                path, html = clock.page(lang, tool)
                self.assertEqual(path, kit.url(lang, f"/{tool}/"))
                self.assertIn(f'<html lang="{lang}">', html)
                self.assertIn(f'<link rel="canonical" href="{kit.BASE}{path}">', html)
                hrefs = dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', html))
                self.assertEqual(set(hrefs), set(LANGS) | {"x-default"}, (tool, lang))
                for code, p in alts.items():
                    self.assertEqual(hrefs[code], kit.BASE + p)
                self.assertEqual(hrefs["x-default"], kit.BASE + alts["ko"])
                self.assertIn(kit.ADS, html)
                self.assertNotIn("noindex", html)
                ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
                self.assertEqual(len(ld), 1)
                data = json.loads(ld[0])
                self.assertEqual(data["@type"], "WebApplication")
                self.assertEqual(data["offers"]["price"], "0")
                self.assertEqual(data["inLanguage"], lang)
                self.assertEqual(data["operatingSystem"], "Any")
                self.assertEqual(data["url"], kit.BASE + path)
                self.assertNotIn("aggregateRating", ld[0])
                self.assertNotIn("review", ld[0].lower())
                i18n = re.search(r'<script type="application/json" id="i18n">(.*?)</script>', html, re.S)
                d = json.loads(i18n.group(1))
                self.assertEqual(d["lang"], lang)
                self.assertEqual(d["ui"], content(tool, lang)["ui"])

    def test_assets_are_versioned_by_content_hash(self):
        _, html = clock.page("en", "timer")
        for name in ("timer-core.js", "timer.js", "tools-clock.css"):
            self.assertRegex(html, re.escape(f"/assets/{name}?v=") + r"[0-9a-f]{10}")
        self.assertLess(html.index("timer-core.js"), html.index("timer.js?v="))

    def test_non_korean_pages_label_korean_guides_and_link_real_files(self):
        for lang in LANGS:
            _, html = clock.page(lang, "metronome")
            self.assertIn('href="/guides/bpm-to-delay-time.html"', html)
            self.assertIn('href="/tempo-pitch-calculator.html"', html)
            self.assertIn(f'href="{kit.url(lang, "/apps/temposcope/")}"', html)
            self.assertIn(f'href="{kit.url(lang, "/timer/")}"', html)
            self.assertEqual("ck-tag" in html, lang != "ko")
            _, th = clock.page(lang, "timer")
            self.assertIn('href="/trainer.html"', th)
            self.assertIn(f'href="{kit.url(lang, "/metronome/")}"', th)
        for rel in ("guides/bpm-to-delay-time.html", "guides/gain-staging-basics.html", "guides/pink-noise-eq-ear-training.html"):
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_shell_has_tab_roles_labels_and_live_region_policy(self):
        _, html = clock.page("en", "timer")
        self.assertEqual(html.count('role="tab"'), 5)
        self.assertEqual(html.count('role="tabpanel"'), 5)
        self.assertIn('role="timer" aria-live="off"', html)
        self.assertIn('id="sr-live" class="sr-only" aria-live="polite"', html)
        self.assertNotIn("<button type=\"button\" id=\"btn-main\" class=\"btn primary ck-big\"></button>", html)
        ids = re.findall(r'\sid="([^"]+)"', html)
        self.assertEqual(len(ids), len(set(ids)))
        _, mh = clock.page("en", "metronome")
        ids = re.findall(r'\sid="([^"]+)"', mh)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn('id="bpm-range"', mh)

    def test_generated_files_sitemap_and_site_check(self):
        sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        for p in clock.all_paths():
            self.assertTrue((ROOT / p.lstrip("/") / "index.html").exists(), p)
            self.assertIn(f"<loc>{kit.BASE}{p}</loc>", sm)
        self.assertEqual(len(clock.all_paths()), 16)
        self.assertEqual(len(set(clock.all_paths())), 16)
        for prefix in ("timer/", "metronome/"):
            self.assertIn(prefix, check.GENERATED_PREFIXES)
        self.assertEqual(check.run(ROOT), [])

    def test_tools_list_has_time_and_practice_group_in_ko_and_en(self):
        data = pages.load("tools.json")
        for lang, title, pre in (("ko", "시간·연습", ""), ("en", "Time & practice", "/en")):
            g = [g for g in data[lang]["groups"] if g["title"] == title]
            self.assertEqual(len(g), 1)
            self.assertEqual([it["href"] for it in g[0]["items"]], [pre + "/timer/", pre + "/metronome/"])
            _, html = pages.tools(lang)
            for it in g[0]["items"]:
                self.assertEqual(html.count(f'<h3><a href="{it["href"]}">'), 1)
            self.assertNotIn("app", g[0]["items"][0])
            self.assertEqual(g[0]["items"][1]["app"], "temposcope")

    def test_temposcope_page_links_the_metronome_in_its_own_language(self):
        for lang in LANGS:
            html = pages.app_page(lang, "temposcope")[1]
            self.assertIn(f'href="{kit.url(lang, "/metronome/")}"', html, lang)

    def test_privacy_page_mentions_timer_and_metronome_local_storage(self):
        _, ko = pages.simple_page("ko", "privacy")
        _, en = pages.simple_page("en", "privacy")
        self.assertIn("온라인 타이머와 메트로놈도 같은 방식으로", ko)
        self.assertIn("The online timer and metronome work the same way", en)
        self.assertIn("일부 페이지(웹 도구와 정책 페이지)는", ko)


class ScriptTests(unittest.TestCase):
    def test_metronome_scheduler_uses_settimeout_lookahead_not_setinterval_for_sound(self):
        js = (ASSETS / "metronome.js").read_text(encoding="utf-8")
        self.assertIn("POLL = 25", js)
        self.assertIn("LOOK = 0.1", js)
        self.assertIn("setTimeout(poll, POLL)", js)
        self.assertIn("ctx.currentTime", js)
        for m in re.finditer(r"setInterval\(([^,]+),", js):
            self.assertEqual(m.group(1).strip(), "updatePractice")      # 화면 표시용만

    def test_timer_never_counts_down_by_decrementing(self):
        js = (ASSETS / "timer.js").read_text(encoding="utf-8") + (ASSETS / "timer-core.js").read_text(encoding="utf-8")
        self.assertIn("Date.now()", js)
        self.assertNotIn("setInterval(", js)
        self.assertNotIn("innerHTML", js)

    @unittest.skipUnless(shutil.which("node"), "node 가 없어 순수 계산 단위 테스트를 건너뜀")
    def test_node_unit_tests_for_core_modules(self):
        files = sorted(str(f) for f in (ROOT / "_src" / "tests" / "js").glob("*.test.js"))   # node 24 는 디렉터리를 모듈로 읽으므로 파일을 직접 넘긴다
        r = subprocess.run(["node", "--test", *files], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertNotIn("✖", r.stdout)       # node 버전에 따라 요약 형식이 달라 통과·실패 표시로 판단한다
        self.assertIn("✔", r.stdout)


if __name__ == "__main__":
    unittest.main()
