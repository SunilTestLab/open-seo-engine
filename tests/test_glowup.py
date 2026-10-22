import json
import tempfile
import unittest
from pathlib import Path

from open_seo import audit_html, export_glowup, glowup_story


class GlowupTests(unittest.TestCase):
    def test_roast_uses_real_issues_only(self):
        report = audit_html('<html><body><h2>Hi</h2></body></html>', 'https://brand.example/')
        story = glowup_story(report)
        self.assertTrue(story['problems'])
        self.assertEqual(story['score'], report['score'])
        self.assertEqual(set(x['code'] for x in story['problems']).difference(x['code'] for x in report['findings']), set())
        self.assertIn('No changes applied', story['disclaimer'])

    def test_clean_page_has_no_false_roast(self):
        report = {"url": "https://brand.example/", "score": 100, "findings": [], "page": {}}
        story = glowup_story(report)
        self.assertEqual(story['problems'], [])
        self.assertIn('No big SEO red flags', story['hook'])

    def test_svg_escapes_untrusted_host(self):
        report = {"url": "https://brand.example/", "score": 90, "findings": [], "page": {}}
        with tempfile.TemporaryDirectory() as folder:
            story = export_glowup(report, folder)
            svg_files = list(Path(folder).glob('frame-*.svg'))
            self.assertEqual(len(svg_files), 3)
            self.assertIn('width="1080" height="1920"', svg_files[0].read_text())
            self.assertEqual(json.loads((Path(folder) / 'story.json').read_text())['host'], story['host'])
            self.assertTrue((Path(folder) / 'reel-script.txt').exists())

    def test_reject_crawl_report(self):
        with self.assertRaises(ValueError):
            glowup_story({"pages": []})
