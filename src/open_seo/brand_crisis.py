"""Opt-in multi-model brand identity comparison against first-party evidence."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from .answerability import ContentParser, _schema_values, answerability_challenge


FIELDS = ("name", "offering", "location", "pricing", "contact")
KEY_NAMES = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 30) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", **headers}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read(1_000_001).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Never echo the response body, headers, or authentication material.
        raise ValueError(f"Model provider returned HTTP {exc.code}") from None


def call_provider(provider: str, model: str, prompt: str, *, environ=None,
                  transport: Callable = _post_json) -> str:
    """Call one explicitly chosen remote model. No calls occur without an API key."""
    environ = os.environ if environ is None else environ
    if provider not in KEY_NAMES or not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", model):
        raise ValueError("Unsupported provider or invalid model identifier")
    key = environ.get(KEY_NAMES[provider], "")
    if not key:
        raise ValueError(f"Missing required {KEY_NAMES[provider]}")
    if provider == "openai":
        output = transport("https://api.openai.com/v1/responses",
                           {"model": model, "input": prompt, "max_output_tokens": 650},
                           {"Authorization": f"Bearer {key}"})
        return "".join(block.get("text", "") for item in output.get("output", [])
                       for block in item.get("content", []) if block.get("type") == "output_text")
    if provider == "gemini":
        output = transport(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                           {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 650}},
                           {"x-goog-api-key": key})
        return "".join(part.get("text", "") for candidate in output.get("candidates", [])
                       for part in candidate.get("content", {}).get("parts", []))
    output = transport("https://api.anthropic.com/v1/messages",
                       {"model": model, "max_tokens": 650, "messages": [{"role": "user", "content": prompt}]},
                       {"x-api-key": key, "anthropic-version": "2023-06-01"})
    return "".join(block.get("text", "") for block in output.get("content", []) if block.get("type") == "text")


def parse_model_claims(raw: str) -> dict:
    """Strictly parse only five scalar claim fields, avoiding freeform model output."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("Model response must be a JSON object")
    parsed = {}
    for field in FIELDS:
        value = obj.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Model response field {field} must be a string or null")
        parsed[field] = (value.strip()[:240] or None) if isinstance(value, str) else None
    return parsed


def official_evidence(html: str, url: str) -> dict:
    """Extract a cautious source-of-truth ledger with traceable HTML evidence."""
    p = ContentParser()
    p.feed(html)
    challenge = answerability_challenge(html, url)
    schema = p.schema
    title = " ".join(p.title)
    values = {
        "name": [(s, "JSON-LD name") for s in _schema_values(schema, "name")] + ([(title, "title")] if title else []),
        "offering": [(s, "JSON-LD description") for s in _schema_values(schema, "description")],
        "location": [(s, "JSON-LD location") for k in ("addressLocality", "areaServed", "streetAddress") for s in _schema_values(schema, k)],
        "pricing": [(s, "JSON-LD price") for k in ("price", "lowPrice", "highPrice") for s in _schema_values(schema, k)],
        "contact": [(s, "JSON-LD contact") for k in ("email", "telephone") for s in _schema_values(schema, k)]
                    + [(s, "HTML contact link") for s in p.links if s.startswith(("mailto:", "tel:"))],
    }
    description = next((m.get("content", "") for m in p.meta if m.get("name", "").lower() == "description"), "")
    if description:
        values["offering"].append((description, "meta description"))
    # Visible page snippets are usable as evidence, but only exact string support is asserted.
    visible = " ".join(p.text)
    return {"url": url, "values": {k: [{"value": v[:250], "source": s} for v, s in entries[:12] if v]
                                    for k, entries in values.items()},
            "visible_excerpt": visible[:6000], "answerability": challenge}


def _norm(value: str) -> str:
    return " ".join(re.findall(r"[\w]+", value.casefold(), flags=re.UNICODE))


def compare_claims(evidence: dict, responses: list[dict]) -> dict:
    """Compare without treating absence of evidence as proof of falsehood."""
    if len(responses) < 2:
        raise ValueError("At least two valid model responses are required")
    comparisons = []
    visible = _norm(evidence["visible_excerpt"])
    for field in FIELDS:
        claimed = [(r["provider"], r["model"], r["claims"].get(field)) for r in responses]
        present = [(p, m, v) for p, m, v in claimed if v]
        variants = sorted({_norm(v) for _, _, v in present})
        official = evidence["values"][field]
        checks = []
        for provider, model, claim in claimed:
            if not claim:
                verdict = "omitted"
            elif any(_norm(claim) in _norm(s["value"]) or _norm(s["value"]) in _norm(claim)
                     for s in official if _norm(s["value"])):
                verdict = "supported_by_metadata"
            elif _norm(claim) in visible:
                verdict = "supported_by_visible_text"
            elif official and field in {"name", "location", "pricing", "contact"}:
                verdict = "potential_conflict_review_needed"
            else:
                verdict = "not_verified_on_sampled_page"
            checks.append({"provider": provider, "model": model, "claim": claim, "verdict": verdict})
        comparisons.append({"field": field, "models_disagree": len(variants) > 1,
                            "models_omitting": sum(v is None for _, _, v in claimed),
                            "official_evidence": official, "checks": checks})
    return {"fields": comparisons, "disagreement_fields": [x["field"] for x in comparisons if x["models_disagree"]],
            "review_flags": sum(x["verdict"] in ("potential_conflict_review_needed", "not_verified_on_sampled_page")
                                for field in comparisons for x in field["checks"])}


def run_brand_crisis(html: str, url: str, models: list[tuple[str, str]], *,
                     invoke: Callable = call_provider) -> dict:
    """Run independently prompted models; intended to be explicitly opt-in."""
    if not 2 <= len(models) <= 5 or len(set(models)) != len(models):
        raise ValueError("Choose 2–5 distinct provider/model pairs")
    for provider, model in models:
        if provider not in KEY_NAMES or not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", model):
            raise ValueError("Invalid provider/model pair")
    prompt = (f"Describe the brand at {url}. Based only on your existing knowledge (no browsing), "
              "return ONLY one JSON object with exactly five keys: name, offering, location, pricing, contact. "
              "Each value must be a short string or null if unknown. Never invent details or include explanations.")
    evidence = official_evidence(html, url)
    responses, errors = [], []
    for provider, model in models:
        try:
            claims = parse_model_claims(invoke(provider, model, prompt))
            responses.append({"provider": provider, "model": model, "claims": claims})
        except (ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError) as exc:
            errors.append({"provider": provider, "model": model, "error": str(exc)[:180]})
    comparison = compare_claims(evidence, responses) if len(responses) >= 2 else None
    return {"brand_url": url, "opt_in": True, "requested_models": len(models), "completed_models": len(responses),
            "evidence": evidence, "responses": responses, "comparison": comparison, "errors": errors,
            "disclaimer": "Models were not given site content and did not browse. Comparisons reflect answers and sampled HTML only; unsupported does not mean false. No live search ranking/citation inference."}
