import csv
import json
import tempfile
import unittest
from pathlib import Path

from open_seo import crawl_site, export_report, sitemap_urls


class CrawlTests(unittest.TestCase):
    def test_sitemap_and_index(self):
        urls, indexes = sitemap_urls('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://site.test/a</loc></url></urlset>')
        self.assertEqual(urls, ["https://site.test/a"])
        self.assertEqual(indexes, [])
        urls, indexes = sitemap_urls('<sitemapindex><sitemap><loc>https://site.test/one.xml</loc></sitemap></sitemapindex>')
        self.assertEqual(indexes, ["https://site.test/one.xml"])

    def test_reject_entities(self):
        with self.assertRaises(ValueError):
            sitemap_urls('<!DOCTYPE a [<!ENTITY x "no">]><urlset/>')

    def test_robots_disallow_broken_links_and_duplicates(self):
        root = "https://site.test"
        pages = {
            root + "/robots.txt": (200, "text/plain", "User-agent: *\nDisallow: /secret\nSitemap: https://site.test/sitemap.xml"),
            root + "/sitemap.xml": (200, "application/xml", "<urlset><url><loc>https://site.test/about</loc></url></urlset>"),
            root + "/": (200, "text/html", '<html lang="en"><title>Same</title><h1>Home</h1><a href="/broken">Broken</a><a href="/secret">Secret</a></html>'),
            root + "/about": (200, "text/html", '<html lang="en"><title>Same</title><h1>About</h1></html>'),
            root + "/broken": (404, "text/html", "Not found"),
        }
        fetched = []
        def fetch(url):
            fetched.append(url)
            return pages[url]
        result = crawl_site(root, max_pages=5, fetcher=fetch)
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["broken_links"]), 1)
        self.assertEqual(result["broken_links"][0]["status"], 404)
        self.assertEqual(len(result["duplicate_titles"]), 1)
        self.assertNotIn(root + "/secret", fetched)

    def test_fail_closed_robots(self):
        result = crawl_site("https://site.test/", fetcher=lambda _: (403, "text/plain", ""))
        self.assertEqual(result["stopped"], "robots_unavailable")
        self.assertEqual(result["pages"], [])

    def test_csv_json_export(self):
        report = crawl_site("https://site.test/", fetcher=lambda url: (404, "text/plain", ""), include_sitemaps=False)
        with tempfile.TemporaryDirectory() as folder:
            csv_path, json_path = Path(folder) / "report.csv", Path(folder) / "report.json"
            export_report(report, csv_path, "csv")
            export_report(report, json_path)
            with csv_path.open() as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(json_path.read_text())["count"], 1)

    def test_page_limit(self):
        def fetch(url):
            if url.endswith("robots.txt"):
                return 404, "text/plain", ""
            return 200, "text/html", '<a href="/next">next</a>'
        result = crawl_site("https://site.test/", fetcher=fetch, include_sitemaps=False, max_pages=1)
        self.assertEqual(result["stopped"], "page_limit")


if __name__ == "__main__":
    unittest.main()
