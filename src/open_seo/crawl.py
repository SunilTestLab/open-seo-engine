"""Bounded, same-origin crawling with robots and sitemap discovery."""
from __future__ import annotations

import collections
import csv
import json
import time
import urllib.parse
import urllib.request
import urllib.error
import urllib.robotparser
import xml.etree.ElementTree as ET
from pathlib import Path

from .audit import _NoRedirect, _public_https_target, audit_html

USER_AGENT = "OpenSEOEngine"


def normalize_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))


def same_origin(a: str, b: str) -> bool:
    x, y = urllib.parse.urlsplit(a), urllib.parse.urlsplit(b)
    return (x.scheme, x.hostname, x.port) == (y.scheme, y.hostname, y.port)


def http_fetch(url: str, max_bytes: int = 2_000_000, timeout: int = 10) -> tuple[int, str, str]:
    """Return (status, media_type, body); HTTP error statuses are not raised."""
    _public_https_target(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT + "/0.2"})
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        response = opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308):
            return exc.code, "", ""
        response = exc
    with response:
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Response exceeds size limit")
        media = response.headers.get_content_type()
        charset = response.headers.get_content_charset() or "utf-8"
        return response.status, media, data.decode(charset, errors="replace")


def sitemap_urls(xml: str, limit: int = 1000) -> tuple[list[str], list[str]]:
    """Parse URL sets and sitemap indexes without fetching nested resources."""
    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise ValueError("XML DTD/entities are prohibited")
    root = ET.fromstring(xml)
    local = lambda el: el.tag.rsplit("}", 1)[-1]
    urls, indexes = [], []
    for node in root:
        loc = next((c.text.strip() for c in node if local(c) == "loc" and c.text), None)
        if not loc:
            continue
        if local(node) == "url" and len(urls) < limit:
            urls.append(loc)
        if local(node) == "sitemap" and len(indexes) < limit:
            indexes.append(loc)
    return urls, indexes


def crawl_site(start_url: str, *, max_pages: int = 50, delay: float = 0.5,
               fetcher=None, include_sitemaps: bool = True) -> dict:
    """Crawl one HTTPS origin; fetcher(url)->(status, media_type, text) for tests.

    Defaults honor robots.txt, bound page count and sitemap discovery. No
    redirects or cross-origin crawling. Sitemaps don't override robots rules.
    """
    if not 1 <= max_pages <= 1000 or delay < 0:
        raise ValueError("max_pages must be 1–1000 and delay nonnegative")
    if urllib.parse.urlsplit(start_url).scheme != "https":
        raise ValueError("Crawler requires HTTPS")
    start_url = normalize_url(start_url)
    fetch = fetcher or http_fetch
    origin = urllib.parse.urlsplit(start_url)
    base = f"{origin.scheme}://{origin.netloc}"
    robots_url = base + "/robots.txt"
    errors = []
    robots = urllib.robotparser.RobotFileParser()
    robots.set_url(robots_url)
    sitemap_hints = []
    try:
        status, _, robots_text = fetch(robots_url)
        if status == 200:
            robots.parse(robots_text.splitlines())
            for line in robots_text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_hints.append(line.split(":", 1)[1].strip())
        elif status in (401, 403, 429) or status >= 500:
            raise ValueError(f"robots.txt returned {status}; crawl disallowed")
        else:
            robots.parse([])
    except Exception as exc:
        # Fail closed when a robots policy cannot be confirmed.
        return {"start_url": start_url, "pages": [], "broken_links": [], "duplicate_titles": [],
                "duplicate_descriptions": [], "errors": [{"url": robots_url, "error": str(exc)}],
                "count": 0, "stopped": "robots_unavailable"}

    def allowed(url):
        return same_origin(start_url, url) and robots.can_fetch(USER_AGENT, url)

    queue = collections.deque([start_url])
    seen = {start_url}
    if include_sitemaps:
        xml_queue = collections.deque(sitemap_hints or [base + "/sitemap.xml"])
        xml_seen = set()
        while xml_queue and len(xml_seen) < 5 and len(seen) < max_pages * 10:
            sitemap = normalize_url(xml_queue.popleft())
            if sitemap in xml_seen or not allowed(sitemap):
                continue
            xml_seen.add(sitemap)
            try:
                status, _, content = fetch(sitemap)
                if status != 200:
                    continue
                found, nested = sitemap_urls(content, limit=max_pages * 10)
                for link in found:
                    url = normalize_url(link)
                    if allowed(url) and url not in seen and len(seen) < max_pages * 10:
                        seen.add(url)
                        queue.append(url)
                for link in nested:
                    if same_origin(start_url, link):
                        xml_queue.append(link)
            except (ValueError, OSError, ET.ParseError) as exc:
                errors.append({"url": sitemap, "error": str(exc)})
            if fetcher is None and delay:
                time.sleep(delay)

    pages, statuses = [], {}
    while queue and len(pages) < max_pages:
        url = queue.popleft()
        if not allowed(url):
            continue
        try:
            status, media, body = fetch(url)
            statuses[url] = status
            report = audit_html(body, url) if status == 200 and media in ("text/html", "application/xhtml+xml") else None
            record = {"url": url, "status": status, "audit": report}
            pages.append(record)
            if report:
                for target in report["page"]["outgoing_links"]:
                    target = normalize_url(target)
                    if allowed(target) and target not in seen and len(seen) < max_pages * 10:
                        seen.add(target)
                        queue.append(target)
        except Exception as exc:
            errors.append({"url": url, "error": str(exc)})
        if fetcher is None and delay:
            time.sleep(delay)

    broken = []
    for page in pages:
        audit = page["audit"]
        if not audit:
            continue
        for link in audit["page"]["outgoing_links"]:
            target = normalize_url(link)
            if target in statuses and statuses[target] >= 400:
                broken.append({"source": page["url"], "target": target, "status": statuses[target]})
    duplicates = {}
    for field in ("title", "description"):
        groups = collections.defaultdict(list)
        for page in pages:
            if page["audit"]:
                value = page["audit"]["page"][field].strip()
                if value:
                    groups[value].append(page["url"])
        duplicates[field] = [{"value": value, "urls": urls} for value, urls in groups.items() if len(urls) > 1]
    return {"start_url": start_url, "count": len(pages), "pages": pages,
            "broken_links": broken, "duplicate_titles": duplicates["title"],
            "duplicate_descriptions": duplicates["description"], "errors": errors,
            "stopped": "page_limit" if queue and len(pages) == max_pages else "complete"}


def export_report(report: dict, path: str | Path, format: str = "json") -> None:
    path = Path(path)
    if format == "json":
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif format == "csv":
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["url", "status", "score", "title", "description", "issues"])
            writer.writeheader()
            for page in report["pages"]:
                audit = page["audit"]
                writer.writerow({"url": page["url"], "status": page["status"],
                                 "score": audit["score"] if audit else "",
                                 "title": audit["page"]["title"] if audit else "",
                                 "description": audit["page"]["description"] if audit else "",
                                 "issues": "; ".join(x["code"] for x in audit["findings"]) if audit else ""})
    else:
        raise ValueError("format must be json or csv")
