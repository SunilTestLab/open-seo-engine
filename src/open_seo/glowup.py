"""Evidence-based, vertical social storytelling from an SEO audit."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

SUGGESTIONS = {
    "missing_title": ("Your page has no title", "Write a clear, unique page title"),
    "title_length": ("Your title needs a rethink", "Make the title concise and descriptive"),
    "missing_description": ("Your snippet has no description", "Add a helpful meta description"),
    "description_length": ("Your snippet could be sharper", "Rewrite for clarity and search intent"),
    "missing_h1": ("Your headline is missing", "Add one descriptive H1 heading"),
    "multiple_h1": ("Your headings need structure", "Clarify your page heading hierarchy"),
    "missing_canonical": ("Search engines need a canonical hint", "Declare the preferred canonical URL"),
    "missing_lang": ("Your page language is unspecified", "Set the HTML language attribute"),
    "missing_alt": ("Some images lack alt text", "Describe meaningful images accessibly"),
    "noindex": ("Your page says DO NOT INDEX", "Review the noindex directive intentionally"),
    "invalid_jsonld": ("Your structured data is broken", "Fix JSON-LD syntax and validate it"),
    "missing_og_title": ("Social previews need polish", "Add an Open Graph title"),
}


def _short(value: str, maximum: int = 47) -> str:
    value = " ".join(value.split())
    return value if len(value) <= maximum else value[:maximum - 1].rstrip() + "…"


def glowup_story(audit: dict) -> dict:
    """Build a truthful 3-beat storyboard from the real audited findings."""
    if "findings" not in audit or "page" not in audit:
        raise ValueError("Expected single-page audit result from audit_html/audit_url")
    host = urlsplit(audit.get("url", "")).hostname or "website"
    issues = [f for f in audit["findings"] if f.get("code") in SUGGESTIONS]
    priority = {"critical": 0, "warning": 1, "notice": 2}
    issues.sort(key=lambda f: (priority.get(f.get("severity"), 3), f["code"]))
    selected = issues[:3]
    problems = [{"code": f["code"], "severity": f["severity"],
                 "hook": SUGGESTIONS[f["code"]][0], "fix": SUGGESTIONS[f["code"]][1]}
                for f in selected]
    score = min(100, max(0, int(audit["score"])))
    primary = problems[0] if problems else None
    if primary:
        hook = primary["hook"] + " 😬"
        reveal = "Here's what I'd fix first"
        fixes = [p["fix"] for p in problems]
    else:
        hook = "No big SEO red flags 👀"
        reveal = "Your next move: keep monitoring"
        fixes = ["Maintain helpful, original content", "Review search performance", "Re-audit after major changes"]
    return {"brand": "SEO GLOW-UP", "host": host, "score": score,
            "score_label": "Heuristic on-page audit score — not a Google ranking",
            "hook": hook, "reveal": reveal, "problems": problems, "fixes": fixes,
            "disclaimer": "Fix recommendations only · No changes applied · No ranking gains promised",
            "reel_script": [
                {"seconds": "0–3", "voiceover": f"I checked {host}. {hook}"},
                {"seconds": "3–8", "voiceover": f"Its on-page audit scored {score} out of 100. This is an audit score, not a Google ranking."},
                {"seconds": "8–15", "voiceover": reveal + ": " + "; ".join(fixes[:3]) + ". Save this checklist."},
            ]}


def _lines(values: list[str], x: int, y: int, gap: int = 98, font: int = 36, color: str = "#eefcf7") -> str:
    return "".join(f'<text x="{x}" y="{y+i*gap}" font-size="{font}" fill="{color}">{escape(_short(value, 37))}</text>' for i, value in enumerate(values))


def _frame(story: dict, beat: int) -> str:
    heading = ["WAIT. LOOK AT THIS.", "THE SEO X-RAY", "THE GLOW-UP PLAN"][beat]
    subheading = [story["hook"], f'{story["score"]}/100', story["reveal"]][beat]
    footer = ["REAL PAGE AUDIT", "NOT A GOOGLE RANKING", "SAVE THIS CHECKLIST"][beat]
    middle = (
        '<text x="92" y="990" fill="#aff6d4" font-size="36">One real audit. Three actionable fixes.</text>' if beat == 0 else
        '<text x="540" y="1110" text-anchor="middle" font-size="45" fill="#c6f8dc">HEURISTIC AUDIT SCORE</text>' if beat == 1 else
        _lines([f"{i+1:02d}  {fix}" for i, fix in enumerate(story["fixes"])], 92, 900, 158, 39)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920" role="img" aria-label="SEO Glow-Up frame {beat+1}">
<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#082e38"/><stop offset="1" stop-color="#101c2f"/></linearGradient>
<radialGradient id="orb"><stop stop-color="#ff725e" stop-opacity=".9"/><stop offset="1" stop-color="#ff725e" stop-opacity="0"/></radialGradient></defs>
<rect width="1080" height="1920" fill="url(#bg)"/>
<circle cx="890" cy="420" r="500" fill="url(#orb)" opacity=".32"/>
<circle cx="140" cy="1550" r="480" fill="#39daa8" opacity=".08"/>
<g font-family="Arial,Helvetica,sans-serif">
<rect x="74" y="106" width="400" height="76" rx="38" fill="#ff725e"/>
<text x="108" y="157" font-weight="bold" font-size="32" fill="#092b34">{escape(story['brand'])}</text>
<text x="85" y="345" fill="#adead0" font-size="43" letter-spacing="4">{heading}</text>
<text x="85" y="530" font-size="59" font-weight="bold" fill="#ffffff">{escape(_short(subheading, 28))}</text>
<text x="85" y="645" font-size="36" fill="#d9e9e5">{escape(_short(story['host'], 39))}</text>
{middle}
<rect x="74" y="1510" width="932" height="176" rx="36" fill="#e7f7f1"/>
<text x="109" y="1594" font-size="42" font-weight="bold" fill="#103b43">{footer}</text>
<text x="109" y="1645" font-size="24" fill="#28646b">No ranking improvements implied</text>
<text x="80" y="1805" font-size="26" fill="#bdcfca">{beat+1} / 3   •   Original SEO analysis</text>
</g></svg>'''


def export_glowup(audit: dict, directory: str | Path) -> dict:
    """Write 3 story frames (SVG), script, and machine-readable manifest."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    story = glowup_story(audit)
    for beat in range(3):
        (directory / f"frame-{beat+1}.svg").write_text(_frame(story, beat), encoding="utf-8")
    script = "\n".join(f"{item['seconds']}s: {item['voiceover']}" for item in story["reel_script"])
    (directory / "reel-script.txt").write_text(script + "\n", encoding="utf-8")
    (directory / "story.json").write_text(json.dumps(story, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return story
