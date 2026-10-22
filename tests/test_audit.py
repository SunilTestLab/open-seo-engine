import unittest
from unittest.mock import patch

from open_seo import audit_html
from open_seo.audit import _public_https_target


GOOD = '''<!doctype html><html lang="en"><head>
<title>Practical SEO Tools for Modern Websites and Teams</title>
<meta name="description" content="Audit technical SEO elements, inspect structured data, analyze links, and identify opportunities to improve search visibility using open tools.">
<meta property="og:title" content="Practical SEO Tools">
<link rel="canonical" href="https://example.org/"><script type="application/ld+json">{"@type":"WebPage"}</script>
</head><body><h1>SEO Tools</h1><img src="a.png" alt="Chart"><a href="/docs">Docs</a>
<a href="https://other.example/">Elsewhere</a></body></html>'''


class AuditTests(unittest.TestCase):
    def test_clean_page(self):
        report = audit_html(GOOD)
        self.assertEqual(report["score"], 100)
        self.assertEqual(report["page"]["internal_links"], 1)
        self.assertEqual(report["page"]["external_links"], 1)
        self.assertEqual(report["page"]["jsonld_valid"], 1)

    def test_empty_page(self):
        issues = {f["code"] for f in audit_html("<html><body></body></html>")["findings"]}
        self.assertTrue({"missing_title", "missing_description", "missing_h1", "missing_lang", "missing_canonical"}.issubset(issues))

    def test_noindex_and_invalid_jsonld(self):
        report = audit_html('<meta name="robots" content="noindex"><script type="application/ld+json">oops</script>')
        codes = {f["code"] for f in report["findings"]}
        self.assertIn("noindex", codes)
        self.assertIn("invalid_jsonld", codes)

    def test_block_private_hosts(self):
        for url in ("http://example.com", "https://127.0.0.1", "https://localhost", "https://user:pass@example.com"):
            with self.assertRaises(ValueError):
                _public_https_target(url)

    @patch("open_seo.audit.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.1", 443))])
    def test_block_private_dns(self, _):
        with self.assertRaises(ValueError):
            _public_https_target("https://internal.example")


if __name__ == "__main__":
    unittest.main()

