"""Evidence-based AI Answerability Challenge (no LLM, no invented answers)."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit


class ContentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.in_jsonld = False
        self.json_parts = []
        self.schema = []
        self.text = []
        self.links = []
        self.meta = []
        self.title = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("style", "noscript", "svg"):
            self.skip += 1
        elif tag == "script":
            self.skip += 1
            if attrs.get("type", "").lower() == "application/ld+json":
                self.in_jsonld = True
                self.json_parts = []
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            self.meta.append(attrs)
        elif tag == "a":
            self.links.append(attrs.get("href", ""))

    def handle_endtag(self, tag):
        if tag in ("style", "noscript", "svg"):
            self.skip = max(0, self.skip - 1)
        elif tag == "script":
            self.skip = max(0, self.skip - 1)
            if self.in_jsonld:
                try:
                    self.schema.append(json.loads("".join(self.json_parts)))
                except ValueError:
                    pass
                self.in_jsonld = False
        elif tag == "title":
            self.in_title = False

    def handle_data(self, data):
        value = " ".join(data.split())
        if self.in_jsonld:
            self.json_parts.append(data)
        elif self.in_title:
            self.title.append(value)
        elif not self.skip and value:
            self.text.append(value)


def _schema_values(node, key: str) -> list[str]:
    values = []
    if isinstance(node, list):
        for entry in node:
            values.extend(_schema_values(entry, key))
    elif isinstance(node, dict):
        for k, value in node.items():
            if k == key:
                if isinstance(value, (str, int, float)):
                    values.append(str(value))
            if isinstance(value, (list, dict)):
                values.extend(_schema_values(value, key))
    return values


def _evidence_from_text(chunks: list[str], pattern: str) -> str | None:
    compiled = re.compile(pattern, re.IGNORECASE)
    return next((part[:180] for part in chunks if compiled.search(part)), None)


def answerability_challenge(html: str, url: str = "https://example.org/") -> dict:
    """Assess five buyer-question answer gaps using visible HTML and structured data.

    This is a deterministic content completeness diagnostic. It does *not* test
    any external AI service, citations, rankings, or actual recommendations.
    """
    p = ContentParser()
    p.feed(html)
    schema_names = _schema_values(p.schema, "name")
    schema_descriptions = _schema_values(p.schema, "description")
    meta_description = next((m.get("content", "") for m in p.meta if m.get("name", "").lower() == "description"), "")
    title = " ".join(p.title)
    visible = p.text

    def answer(identifier, question, candidates, recommendation):
        # Each candidate is (evidence, source) where source is a real HTML field.
        entry = next(((value, source) for value, source in candidates if value), None)
        return {"id": identifier, "question": question, "status": "evidence_found" if entry else "not_found",
                "evidence": entry[0][:180] if entry else None,
                "source": entry[1] if entry else None,
                "recommendation": recommendation if not entry else None}

    host = urlsplit(url).hostname or "website"
    business = schema_names[0] if schema_names else (title or host)
    questions = [
        answer("identity", "Who is this business or website?",
               [(schema_names[0] if schema_names else "", "JSON-LD name"), (title, "HTML title")],
               "State your organization or brand name clearly on the page."),
        answer("offer", "What does it offer?",
               [(schema_descriptions[0] if schema_descriptions else "", "JSON-LD description"),
                (meta_description, "meta description"),
                (_evidence_from_text(visible, r"\b(we (offer|provide|sell)|our (services|products)|services include)\b"), "visible text")],
               "Clearly describe your services or products in accessible visible text."),
        answer("contact", "How can a customer contact it?",
               [(link, "contact link") for link in p.links if link.lower().startswith(("mailto:", "tel:"))] +
               [(value, "JSON-LD email/telephone") for field in ("email", "telephone") for value in _schema_values(p.schema, field)],
               "Add a usable email address or telephone contact link."),
        answer("location", "Where does it operate?",
               [(value, "JSON-LD address/locality") for field in ("addressLocality", "streetAddress", "areaServed") for value in _schema_values(p.schema, field)] +
               [(_evidence_from_text(visible, r"\b(located in|based in|serving customers in)\b"), "visible text")],
               "State the service area or address when relevant to customers."),
        answer("pricing", "Can customers find pricing?",
               [(value, "JSON-LD price") for field in ("price", "lowPrice", "highPrice") for value in _schema_values(p.schema, field)] +
               [(_evidence_from_text(visible, r"(?:₹|\$|€|£)\s?\d|\b(?:price starts|starting at|pricing plans)\b"), "visible text")],
               "Add transparent price details or a clear quote-request pathway when appropriate."),
    ]
    found = sum(q["status"] == "evidence_found" for q in questions)
    return {"url": url, "business": business, "coverage": found, "total": len(questions),
            "evidence_coverage_percent": found * 100 // len(questions), "questions": questions,
            "missing": [q["id"] for q in questions if q["status"] == "not_found"],
            "disclaimer": "Content evidence audit only; not a live AI model test or a prediction of AI citations/rankings."}
