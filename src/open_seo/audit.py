"""Single-page SEO analysis and bounded public URL retrieval."""
from __future__ import annotations

import ipaddress
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.in_title = False
        self.headings = []
        self.heading_level = None
        self.heading_parts = []
        self.meta = []
        self.links = []
        self.images = []
        self.html_lang = ""
        self.scripts = []
        self.in_jsonld = False
        self.jsonld_parts = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.html_lang = a.get("lang", "") or ""
        elif tag == "title":
            self.in_title = True
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.heading_level = tag
            self.heading_parts = []
        elif tag == "meta":
            self.meta.append(a)
        elif tag == "link":
            self.links.append(a)
        elif tag == "img":
            self.images.append(a)
        elif tag == "a":
            self.links.append({"href": a.get("href", ""), "_anchor": True})
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self.in_jsonld = True
            self.jsonld_parts = []

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if self.heading_level:
            self.heading_parts.append(data)
        if self.in_jsonld:
            self.jsonld_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == self.heading_level:
            self.headings.append({"level": tag, "text": " ".join(" ".join(self.heading_parts).split())})
            self.heading_level = None
        if tag == "script" and self.in_jsonld:
            raw = "".join(self.jsonld_parts).strip()
            try:
                self.scripts.append({"valid": True, "data": json.loads(raw)})
            except ValueError:
                self.scripts.append({"valid": False})
            self.in_jsonld = False


def audit_html(html: str, url: str = "https://example.org/") -> dict:
    """Analyze HTML content without network access; return JSON-serializable findings."""
    p = PageParser()
    p.feed(html)
    title = " ".join(" ".join(p.title_parts).split())
    def meta(name, field="name"):
        return next((m.get("content", "").strip() for m in p.meta if m.get(field, "").lower() == name), "")
    description = meta("description")
    robots = meta("robots").lower()
    canonical = next((x.get("href", "") for x in p.links if "canonical" in x.get("rel", "").lower().split()), "")
    h1s = [h for h in p.headings if h["level"] == "h1"]
    missing_alt = [i.get("src", "") for i in p.images if "alt" not in i]
    anchors = [x.get("href", "") for x in p.links if x.get("_anchor")]
    host = urllib.parse.urlsplit(url).hostname or ""
    internal = sum(1 for href in anchors if href and (not urllib.parse.urlsplit(urllib.parse.urljoin(url, href)).hostname or urllib.parse.urlsplit(urllib.parse.urljoin(url, href)).hostname == host))
    external = sum(1 for href in anchors if href and urllib.parse.urlsplit(urllib.parse.urljoin(url, href)).hostname not in (None, host))
    findings = []
    def issue(code, severity, message):
        findings.append({"code": code, "severity": severity, "message": message})
    if not title: issue("missing_title", "critical", "Page has no title element")
    elif not 30 <= len(title) <= 60: issue("title_length", "warning", "Title is outside the suggested 30–60 characters")
    if not description: issue("missing_description", "warning", "Meta description is missing")
    elif not 70 <= len(description) <= 160: issue("description_length", "notice", "Description is outside the suggested 70–160 characters")
    if not h1s: issue("missing_h1", "warning", "Page has no H1")
    elif len(h1s) > 1: issue("multiple_h1", "notice", "Page has multiple H1 headings")
    if not p.html_lang: issue("missing_lang", "warning", "HTML lang attribute is missing")
    if not canonical: issue("missing_canonical", "warning", "Canonical URL is missing")
    if missing_alt: issue("missing_alt", "warning", f"{len(missing_alt)} images have no alt attribute")
    if "noindex" in robots: issue("noindex", "critical", "Robots directive prevents indexing")
    if not meta("og:title", "property"): issue("missing_og_title", "notice", "Open Graph title is missing")
    if any(not s["valid"] for s in p.scripts): issue("invalid_jsonld", "warning", "One or more JSON-LD blocks are invalid JSON")
    weights = {"critical": 25, "warning": 10, "notice": 3}
    score = max(0, 100 - sum(weights[x["severity"]] for x in findings))
    return {"url": url, "score": score, "findings": findings,
            "page": {"title": title, "title_length": len(title), "description": description,
                     "description_length": len(description), "canonical": canonical,
                     "robots": robots, "lang": p.html_lang, "headings": p.headings,
                     "images": len(p.images), "images_missing_alt": len(missing_alt),
                     "internal_links": internal, "external_links": external,
                     "outgoing_links": [urllib.parse.urljoin(url, href) for href in anchors if href],
                     "jsonld_blocks": len(p.scripts), "jsonld_valid": sum(s["valid"] for s in p.scripts)}}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirects are disabled for network safety")


def _public_https_target(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError("Only public HTTPS URLs on port 443 are permitted")
    host = parts.hostname
    if host.lower() == "localhost" or host.endswith(".local"):
        raise ValueError("Local hosts are prohibited")
    for entry in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        addr = ipaddress.ip_address(entry[4][0])
        if not addr.is_global:
            raise ValueError("Private or reserved network addresses are prohibited")


def audit_url(url: str, max_bytes: int = 2_000_000, timeout: int = 10) -> dict:
    """Fetch a public HTTPS page and audit it. For trusted execution environments only.

    DNS rebinding remains possible between validation and urllib's connection;
    do not expose this network function as an unrestricted public API endpoint.
    """
    _public_https_target(url)
    opener = urllib.request.build_opener(_NoRedirect())
    req = urllib.request.Request(url, headers={"User-Agent": "OpenSEOEngine/0.1 (+technical SEO audit)", "Accept": "text/html"})
    with opener.open(req, timeout=timeout) as response:
        media_type = response.headers.get_content_type()
        if media_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"Expected HTML, got {media_type}")
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("HTML exceeds configured size limit")
        charset = response.headers.get_content_charset() or "utf-8"
    return audit_html(data.decode(charset, errors="replace"), url=url)

