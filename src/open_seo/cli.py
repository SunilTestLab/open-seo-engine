"""Command line interface."""
import argparse
import json
import sys
from pathlib import Path

from .audit import audit_html, audit_url
from .crawl import crawl_site, export_report
from .glowup import export_glowup
from .answerability import answerability_challenge
from .crawl import http_fetch


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit a public HTTPS URL or local HTML file")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="Public HTTPS URL")
    source.add_argument("--file", type=Path, help="Local HTML document")
    source.add_argument("--crawl", help="Crawl public HTTPS website")
    parser.add_argument("--base-url", default="https://example.org/", help="Page URL when auditing a file")
    parser.add_argument("--output", type=Path, help="Write JSON report to this path")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--delay", type=float, default=0.5, help="Minimum pause between live requests")
    parser.add_argument("--glowup", type=Path, help="Export 3 vertical SVG frames and a Reel script (single-page audit only)")
    parser.add_argument("--answerability", action="store_true", help="Run AI Answerability Challenge against page evidence")
    args = parser.parse_args(argv)
    try:
        if args.answerability and args.crawl:
            parser.error("--answerability supports --url or --file, not --crawl")
        if args.answerability and args.glowup:
            parser.error("Run --answerability and --glowup separately")
        if args.answerability:
            if args.url:
                status, media, body = http_fetch(args.url)
                if status != 200 or media not in ("text/html", "application/xhtml+xml"):
                    raise ValueError(f"Expected HTML 200 response; received {status} {media}")
                result = answerability_challenge(body, args.url)
            else:
                result = answerability_challenge(args.file.read_text(encoding="utf-8"), args.base_url)
        elif args.crawl:
            result = crawl_site(args.crawl, max_pages=args.max_pages, delay=args.delay)
        else:
            result = audit_url(args.url) if args.url else audit_html(args.file.read_text(encoding="utf-8"), args.base_url)
        if args.glowup:
            if args.crawl:
                parser.error("--glowup requires --url or --file, not --crawl")
            export_glowup(result, args.glowup)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.exit(2, f"Audit failed: {exc}\n")
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        if args.crawl:
            export_report(result, args.output, format=args.format)
        elif args.format == "json":
            args.output.write_text(rendered + "\n", encoding="utf-8")
        else:
            parser.error("CSV export requires --crawl")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())

