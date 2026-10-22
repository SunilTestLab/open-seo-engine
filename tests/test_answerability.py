import json
import tempfile
import unittest
from pathlib import Path

from open_seo import answerability_challenge
from open_seo.cli import main


class AnswerabilityTests(unittest.TestCase):
    def test_full_evidence(self):
        html = '''<html><head><title>Acme Foods</title><meta name="description" content="We deliver healthy food to homes.">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"LocalBusiness","name":"Acme Foods","address":{"addressLocality":"Hyderabad"},"offers":{"price":"299"}}</script>
</head><body><a href="tel:+911234567890">Call</a><p>Fresh food ₹299</p></body></html>'''
        report = answerability_challenge(html, "https://acme.example/")
        self.assertEqual(report["evidence_coverage_percent"], 100)
        self.assertEqual(len(report["questions"]), 5)
        self.assertTrue(all(x["evidence"] for x in report["questions"]))

    def test_missing_evidence_not_hallucinated(self):
        report = answerability_challenge("<html><body><h1>Hello</h1></body></html>")
        self.assertEqual(report["coverage"], 0)
        self.assertTrue(all(x["evidence"] is None for x in report["questions"]))
        self.assertIn("not a live AI model test", report["disclaimer"])

    def test_script_text_not_counted_as_visible(self):
        report = answerability_challenge('<title>Example</title><script>var msg="pricing plans $25";</script>')
        pricing = next(q for q in report["questions"] if q["id"] == "pricing")
        self.assertEqual(pricing["status"], "not_found")

    def test_cli_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "page.html", Path(tmp) / "result.json"
            source.write_text('<html><title>Shop</title><a href="mailto:hi@example.org">Email</a></html>')
            self.assertEqual(main(["--file", str(source), "--answerability", "--output", str(output)]), 0)
            self.assertIn("questions", json.loads(output.read_text()))


if __name__ == "__main__":
    unittest.main()
