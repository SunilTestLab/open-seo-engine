import json
import tempfile
import unittest
from pathlib import Path

from open_seo.brand_crisis import call_provider, compare_claims, official_evidence, parse_model_claims, run_brand_crisis
from open_seo.cli import main

HTML = '''<html><head><title>Acme Foods</title><meta name="description" content="Healthy meal subscriptions in Hyderabad">
<script type="application/ld+json">{"@type":"LocalBusiness","name":"Acme Foods","address":{"addressLocality":"Hyderabad"},"offers":{"price":"299"}}</script>
</head><body><h1>Acme Foods</h1><p>Healthy meal subscriptions in Hyderabad</p><a href="tel:+91123456789">Contact us</a></body></html>'''


class CrisisTests(unittest.TestCase):
    def test_reports_disagreement_and_unverified_without_claiming_false(self):
        outputs = {
            "m1": {"name": "Acme Foods", "offering": "Healthy meal subscriptions in Hyderabad", "location": "Hyderabad", "pricing": "299", "contact": None},
            "m2": {"name": "Acme Foods", "offering": "Online clothing", "location": "Mumbai", "pricing": None, "contact": None},
        }
        def fake(provider, model, prompt):
            self.assertIn('no browsing', prompt)
            return json.dumps(outputs[model])
        report = run_brand_crisis(HTML, "https://acme.example/", [("openai", "m1"), ("gemini", "m2")], invoke=fake)
        self.assertEqual(report["completed_models"], 2)
        self.assertIn("location", report["comparison"]["disagreement_fields"])
        location = next(c for c in report["comparison"]["fields"] if c["field"] == "location")
        self.assertEqual(location["checks"][0]["verdict"], "supported_by_metadata")
        self.assertEqual(location["checks"][1]["verdict"], "potential_conflict_review_needed")
        self.assertIn("unsupported does not mean false", report["disclaimer"])

    def test_evidence_reports_sources(self):
        ledger = official_evidence(HTML, "https://acme.example/")
        self.assertEqual(ledger["values"]["location"][0]["value"], "Hyderabad")
        self.assertTrue(ledger["values"]["contact"][0]["source"])

    def test_malformed_response_is_not_faked(self):
        def invoke(provider, model, prompt):
            return "not json" if provider == "gemini" else '{}'
        report = run_brand_crisis(HTML, "https://acme.example/", [("openai", "m1"), ("gemini", "m2")], invoke=invoke)
        self.assertIsNone(report["comparison"])
        self.assertEqual(report["completed_models"], 1)
        self.assertEqual(len(report["errors"]), 1)

    def test_no_key_no_call(self):
        with self.assertRaisesRegex(ValueError, "Missing required OPENAI_API_KEY"):
            call_provider("openai", "my-model", "prompt", environ={}, transport=lambda *args: self.fail("network called"))

    def test_three_provider_shapes(self):
        calls = []
        def fake(url, payload, headers):
            calls.append((url, payload, headers))
            if "openai" in url:
                return {"output": [{"content": [{"type": "output_text", "text": "{}"}]}]}
            if "googleapis" in url:
                return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}
            return {"content": [{"type": "text", "text": "{}"}]}
        for provider in ("openai", "gemini", "anthropic"):
            self.assertEqual(call_provider(provider, "model-1", "prompt", environ={"OPENAI_API_KEY": "x", "GEMINI_API_KEY": "x", "ANTHROPIC_API_KEY": "x"}, transport=fake), "{}")
        self.assertEqual(len(calls), 3)

    def test_cli_invalid_pairs_before_network(self):
        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / "page.html"
            page.write_text(HTML)
            with self.assertRaises(SystemExit) as exc:
                main(["--file", str(page), "--brand-crisis", "broken"])
            self.assertEqual(exc.exception.code, 2)

    def test_reject_non_scalar_claim(self):
        with self.assertRaises(ValueError):
            parse_model_claims('{"name": ["Acme"]}')


if __name__ == "__main__":
    unittest.main()
