"""Document-level regressions across generated, guide and legacy tool pages.

These inspect the actual output, including label references and landmark targets.
They do not substitute for browser layout or assistive-technology testing.
"""
import pathlib
import re
import sys
import unittest
from collections import Counter
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '_src'))
sys.path.insert(0, str(ROOT / '_src' / 'tools'))
from sitegen import check  # noqa: E402
import chrome_tools  # noqa: E402


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.nodes = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


def reviewed_files():
    for f in ROOT.rglob('*.html'):
        rel = f.relative_to(ROOT).as_posix()
        if rel in check.PLAIN_LINK_FILES and rel not in chrome_tools.FILES:   # policy.html 과 그 영어판(옛 모양 그대로)
            continue
        if rel.startswith(check.GENERATED_PREFIXES + ('guides/',)) or rel in chrome_tools.FILES:
            yield f


class DocumentAccessibilityTests(unittest.TestCase):
    def test_every_page_has_one_main_one_h1_and_a_working_skip_target(self):
        for f in reviewed_files():
            doc = Document(f.read_text(encoding='utf-8'))
            with self.subTest(page=str(f.relative_to(ROOT))):
                main = [a for t, a in doc.nodes if t == 'main' or a.get('role') == 'main']
                self.assertEqual(len(main), 1)
                self.assertEqual(sum(t == 'h1' for t, a in doc.nodes), 1)
                self.assertTrue(any(t == 'nav' and a.get('class') == 'site-nav' for t, a in doc.nodes))
                self.assertEqual(main[0].get('id'), 'main')
                self.assertTrue(any(t == 'a' and a.get('href') == '#main' for t, a in doc.nodes))
                ids = Counter(a['id'] for t, a in doc.nodes if a.get('id'))
                self.assertEqual([key for key, n in ids.items() if n > 1], [])

    def test_heading_levels_never_skip_forward(self):
        for f in reviewed_files():
            levels = [int(t[1]) for t, a in Document(f.read_text(encoding='utf-8')).nodes
                      if re.fullmatch(r'h[1-6]', t)]
            for before, after in zip(levels, levels[1:]):
                self.assertLessEqual(after, before + 1, str(f.relative_to(ROOT)))

    def test_legacy_static_inputs_have_resolving_labels_and_allow_zoom(self):
        for name in chrome_tools.FILES:
            text = (ROOT / name).read_text(encoding='utf-8')
            doc = Document(text)
            ids = {a['id'] for t, a in doc.nodes if a.get('id')}
            labels = {a['for'] for t, a in doc.nodes if t == 'label' and a.get('for')}
            with self.subTest(page=name):
                viewport = next(a['content'] for t, a in doc.nodes if t == 'meta' and a.get('name') == 'viewport')
                self.assertNotIn('maximum-scale', viewport)
                self.assertNotIn('user-scalable=no', viewport)
                for t, a in doc.nodes:
                    if a.get('aria-labelledby'):
                        self.assertTrue(set(a['aria-labelledby'].split()) <= ids, a)
                    if t not in ('input', 'select', 'textarea') or a.get('type') == 'hidden' or 'display:none' in a.get('style', ''):
                        continue
                    self.assertTrue(a.get('id') in labels or a.get('aria-label') or a.get('aria-labelledby'), a)
                self.assertTrue(labels <= ids)

    def test_legacy_tool_search_metadata_identifies_each_document(self):
        descriptions = []
        for name in chrome_tools.FILES:
            doc = Document((ROOT / name).read_text(encoding='utf-8'))
            canonical = [a['href'] for t, a in doc.nodes if t == 'link' and a.get('rel') == 'canonical']
            self.assertEqual(canonical, [check.BASE + '/' + name], name)
            desc = [a['content'] for t, a in doc.nodes if t == 'meta' and a.get('name') == 'description']
            self.assertEqual(len(desc), 1, name)
            self.assertTrue(desc[0].strip(), name)
            descriptions += desc
        self.assertEqual(len(descriptions), len(set(descriptions)))


if __name__ == '__main__':
    unittest.main()
