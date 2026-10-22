# Open SEO Engine

An independent, reusable technical SEO auditing and bounded site-crawling library written in Python. MIT licensed; no paid SEO data providers, tracking keys, or third-party Python runtime dependencies.

## Capabilities (v0.5)

- Inspect page titles and descriptions, H1 headings, canonical URLs and index directives.
- Detect missing image alt attributes, missing language, Open Graph titles, and malformed JSON-LD.
- Count internal/external links and return machine-readable findings with severity and a heuristic score.
- Audit local HTML offline or fetch a single public HTTPS page under a size and timeout limit.
- Integrate the pure `audit_html()` function into SaaS systems without bringing in business logic.
- Crawl one HTTPS origin with a page limit, throttling, robots.txt rules, sitemap discovery (including sitemap indexes), and no redirects.
- Report broken internal links encountered during a crawl and duplicate page titles/descriptions across fetched pages.
- Export site crawl reports as JSON or CSV.
- **SEO Glow-Up:** turn one evidence-based audit into three vertical 1080×1920 SVG Reel frames, a 15-second voiceover script, and editable JSON storyboard. Never fabricates rankings or promises traffic gains.
- **AI Answerability Challenge:** five buyer questions (identity, offer, contact, location, pricing) with exact on-page or JSON-LD evidence, missing-information recommendations and a transparent evidence-coverage metric.
- **AI Brand Identity Crisis (opt-in):** ask 2–5 explicitly selected OpenAI, Gemini, or Anthropic models the same five brand questions. Compare their responses with first-party HTML/JSON-LD evidence, surface omitted claims, model disagreements and possible conflicts for human review. This uses paid APIs only when explicitly invoked.

## Install and use

PyPI distribution is **not published yet**. Until the first verified release, install from a trusted local checkout as shown below. Maintainers: see [RELEASE.md](RELEASE.md) for the gated PyPI release process.

```bash
python -m pip install -e .
open-seo --file sample.html --base-url https://example.org/ --output report.json
open-seo --url https://example.org/ --output report.json
open-seo --crawl https://example.org/ --max-pages 25 --output audit.json
open-seo --crawl https://example.org/ --max-pages 25 --format csv --output audit.csv
open-seo --file sample.html --base-url https://example.org/ --glowup ./reel-assets
open-seo --file sample.html --base-url https://example.org/ --answerability --output challenge.json
open-seo --url https://example.org/ --answerability --output challenge.json
open-seo --url https://example.org/ --brand-crisis openai:YOUR_MODEL_ID,gemini:YOUR_MODEL_ID --output crisis.json
python -m unittest discover -s tests -v
```

Python integration:

```python
from open_seo import audit_html, crawl_site, export_glowup, answerability_challenge

report = audit_html('<html lang="en"><title>Hello</title><h1>Hello</h1></html>',
                    url='https://example.org/')
print(report['findings'])
site_report = crawl_site('https://example.org/', max_pages=10)
export_glowup(report, './reel-assets')
challenge = answerability_challenge('<html><title>Example</title></html>', 'https://example.org/')

# Programmatic use with a custom/injected provider callback:
from open_seo import run_brand_crisis
# run_brand_crisis(html, url, [('openai', 'selected-model'), ('gemini', 'selected-model')])
```

## Architecture and integration

`audit_html(html, url)` is a network-free core. `audit_url(url)` is a bounded single-page downloader. `crawl_site()` handles policy-aware same-origin discovery, with an injectable fetcher for testing, and `open-seo` is the CLI. Each report is a JSON-compatible Python dictionary, suitable for Shelfrank, Zapmetrics, SEO dashboards, CI checks, or an API adapter.

## Limitations and security

This is a **bounded static HTML crawler**, not a browser renderer, ranking tracker, GSC integration, or enterprise SEO platform. Broken links are reported only for internal URLs actually fetched during the bounded crawl; external link status is not tested. The 0–100 score is a heuristic, not a Google ranking metric. Suggested title and description ranges are editorial guidelines, not search-engine rules. Results reflect HTML source, not necessarily JavaScript-rendered output.

Glow-Up outputs **storyboard frames and a script**, not an encoded Instagram video or an Instagram upload. Import the SVG frames into a compatible editor to animate them. The "glow-up" is a list of proposed fixes; the tool never claims those fixes were applied.

AI Answerability Challenge examines only content evidence in the page HTML and JSON-LD. It **does not query ChatGPT, Gemini, Google AI Overviews or other models**, and its coverage percentage does not indicate AI visibility or citation likelihood. Presence of metadata or schema does not prove that a buyer question is correctly answered. Review the extracted evidence manually before acting.

### AI Brand Identity Crisis opt-in and privacy

The Crisis feature **does** call live APIs, but only with `--brand-crisis` or an explicit `run_brand_crisis()` call. Set API keys in `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `ANTHROPIC_API_KEY` as appropriate. Model IDs must be supplied by the operator, because availability and pricing change. The tool makes one call per selected model and can incur provider charges; API calls send the **brand URL**, not the sampled website's HTML. The model is prompted to answer from its existing knowledge without browsing or tools. Results depend on the provider's model and may be outdated or wrong. The official site HTML is compared locally afterwards. **Not verified on sampled page means unknown, not false**; metadata disagreement is only a potential conflict requiring human review. Never treat this as a measurement of how a live search system cites or recommends the brand.

For a real audit, obtain the brand owner's consent when appropriate, review each provider's data-handling policies, and respect the official website's access conditions. The network fetcher still requires hardening before production multi-tenant use.

The URL downloader rejects non-HTTPS endpoints, local/private IP addresses, redirects, and oversized HTML. It nevertheless remains vulnerable to potential DNS rebinding between validation and connection. **Do not expose arbitrary user-supplied URLs via these network functions in a public web service** without network-level egress controls, DNS pinning, and a queue/rate limit. The crawler honors robots.txt disallow rules and fails closed on blocked or unavailable robots policy, but is still not a hardened multi-tenant crawler. Request pacing, sitemap quotas, and robots error semantics should be reviewed for production usage.

## Open-source roadmap

1. Add persistent crawl checkpoints, URL canonicalization, richer duplicate-content checks and link graph analysis.
2. Provide plugin-based analyzers, accessibility metrics and HTML exporter.
3. Improve SSRF defenses with DNS-pinned transport and configurable crawl budgets.
4. Expand CI, issue templates, and release automation after the first gated PyPI release.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Automated tests run on multiple Python versions through GitHub Actions once this source is published.

## License

MIT. No proprietary Shelfrank or Zapmetrics product code is included.
