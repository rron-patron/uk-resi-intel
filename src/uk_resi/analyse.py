"""Send the morning's articles to Claude and validate what comes back.

Two guarantees for the caller:
  * `analyse()` always returns a usable analysis dict, or raises a single
    AnalysisError with a clear reason.
  * `fallback_analysis()` produces a keyword-derived briefing so the dashboard
    still publishes if the API is unavailable. It is labelled as such in the UI.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from datetime import datetime, timezone

from . import config
from .prompts import REPAIR, SYSTEM, build_user_prompt

log = logging.getLogger(__name__)

REQUIRED_KEYS = (
    "executive_summary",
    "sentiment",
    "themes",
    "companies",
    "projects",
    "policy",
    "investor_view",
    "regions",
    "articles",
)


class AnalysisError(RuntimeError):
    pass


# ---------------------------------------------------------------- JSON parsing


def extract_json(text: str) -> dict:
    """Pull the JSON object out of a model response, fences and all."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in response")
    return json.loads(text[start : end + 1])


def _as_int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip().replace("+", ""))
    except (TypeError, ValueError):
        return default


def validate(payload: dict, article_ids: set[str]) -> dict:
    """Coerce the model's output into exactly the shape the dashboard expects."""
    missing = [k for k in REQUIRED_KEYS if k not in payload]
    if missing:
        raise AnalysisError(f"analysis missing keys: {', '.join(missing)}")

    out: dict = {}
    out["executive_summary"] = str(payload["executive_summary"]).strip()

    sentiment = payload.get("sentiment") or {}
    overall = str(sentiment.get("overall", "neutral")).lower()
    out["sentiment"] = {
        "overall": overall if overall in {"positive", "neutral", "negative"} else "neutral",
        "score": max(-100, min(100, _as_int(sentiment.get("score"), 0))),
        "rationale": str(sentiment.get("rationale", "")).strip(),
        "positive_signals": [str(s) for s in sentiment.get("positive_signals", [])][:6],
        "neutral_signals": [str(s) for s in sentiment.get("neutral_signals", [])][:6],
        "negative_signals": [str(s) for s in sentiment.get("negative_signals", [])][:6],
    }

    themes = []
    for theme in payload.get("themes", []):
        name = str(theme.get("name", "")).strip()
        if name not in config.THEMES:
            continue  # keep the theme axis stable across days
        direction = str(theme.get("direction", "steady")).lower()
        themes.append(
            {
                "name": name,
                "count": _as_int(theme.get("count"), 0),
                "direction": direction
                if direction in {"rising", "steady", "cooling"}
                else "steady",
                "summary": str(theme.get("summary", "")).strip(),
                "article_ids": [i for i in theme.get("article_ids", []) if i in article_ids],
            }
        )
    out["themes"] = sorted(themes, key=lambda t: -t["count"])

    out["companies"] = [
        {
            "name": str(c.get("name", "")).strip(),
            "type": str(c.get("type", "Other")).strip() or "Other",
            "mentions": _as_int(c.get("mentions"), 1),
            "context": str(c.get("context", "")).strip(),
        }
        for c in payload.get("companies", [])
        if str(c.get("name", "")).strip()
    ][:20]

    out["projects"] = [
        {
            "name": str(p.get("name", "")).strip(),
            "location": str(p.get("location", "")).strip(),
            "developers": [str(d) for d in p.get("developers", [])][:5],
            "homes": str(p.get("homes", "") or ""),
            "value": str(p.get("value", "") or ""),
            "summary": str(p.get("summary", "")).strip(),
            "article_ids": [i for i in p.get("article_ids", []) if i in article_ids],
        }
        for p in payload.get("projects", [])
        if str(p.get("name", "")).strip()
    ][:12]

    out["policy"] = [
        {
            "headline": str(p.get("headline", "")).strip(),
            "kind": str(p.get("kind", "government")).strip().lower(),
            "body": str(p.get("body", "")).strip(),
            "article_ids": [i for i in p.get("article_ids", []) if i in article_ids],
        }
        for p in payload.get("policy", [])
        if str(p.get("headline", "")).strip()
    ][:10]

    view = payload.get("investor_view") or {}

    def points(key: str) -> list[dict]:
        result = []
        for item in view.get(key, [])[:6]:
            if isinstance(item, dict):
                result.append(
                    {
                        "point": str(item.get("point", "")).strip(),
                        "reasoning": str(item.get("reasoning", "")).strip(),
                    }
                )
            else:
                result.append({"point": str(item).strip(), "reasoning": ""})
        return [p for p in result if p["point"]]

    out["investor_view"] = {
        "opportunities": points("opportunities"),
        "risks": points("risks"),
        "capital_flows": [str(s) for s in view.get("capital_flows", [])][:6],
        "watch_next": [str(s) for s in view.get("watch_next", [])][:6],
    }

    out["regions"] = [
        {
            "name": str(r.get("name", "")).strip(),
            "mentions": _as_int(r.get("mentions"), 1),
            "note": str(r.get("note", "")).strip(),
        }
        for r in payload.get("regions", [])
        if str(r.get("name", "")).strip()
    ][:12]

    ratings = {}
    for entry in payload.get("articles", []):
        aid = str(entry.get("id", "")).strip()
        if aid not in article_ids:
            continue
        importance = str(entry.get("importance", "Medium")).strip().title()
        ratings[aid] = {
            "id": aid,
            "importance": importance
            if importance in config.IMPORTANCE_ORDER
            else "Medium",
            "summary": str(entry.get("summary", "")).strip(),
            "why_it_matters": str(entry.get("why_it_matters", "")).strip(),
            "themes": [t for t in entry.get("themes", []) if t in config.THEMES],
            "companies": [str(c) for c in entry.get("companies", [])][:6],
            "locations": [str(l) for l in entry.get("locations", [])][:6],
        }
    if not ratings:
        raise AnalysisError("analysis returned no usable article ratings")
    out["articles"] = ratings

    unrated = article_ids - set(ratings)
    if unrated:
        log.warning("%d article(s) came back unrated", len(unrated))
    out["meta"] = {
        "rated": len(ratings),
        "unrated": len(unrated),
        "degraded": False,
    }
    return out


# ------------------------------------------------------------------- API call


def call_model(articles: list[dict], date_label: str) -> tuple[dict, dict]:
    """Returns (parsed_json, usage). Raises AnalysisError on hard failure."""
    try:
        from anthropic import Anthropic
    except ImportError as exc:  # pragma: no cover
        raise AnalysisError("the `anthropic` package is not installed") from exc

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise AnalysisError("ANTHROPIC_API_KEY is not set")

    client = Anthropic(api_key=api_key, max_retries=4)
    user_prompt = build_user_prompt(articles, date_label)
    messages = [{"role": "user", "content": user_prompt}]

    for attempt in (1, 2):
        try:
            response = client.messages.create(
                model=config.MODEL,
                max_tokens=config.MAX_OUTPUT_TOKENS,
                system=SYSTEM,
                messages=messages,
            )
        except Exception as exc:
            raise AnalysisError(f"Anthropic API call failed: {exc}") from exc

        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        usage = {
            "model": config.MODEL,
            "input_tokens": getattr(response.usage, "input_tokens", None),
            "output_tokens": getattr(response.usage, "output_tokens", None),
            "stop_reason": response.stop_reason,
        }
        if response.stop_reason == "max_tokens":
            log.warning("response hit max_tokens — output may be truncated")
        try:
            return extract_json(text), usage
        except (ValueError, json.JSONDecodeError) as exc:
            log.warning("attempt %d: unparseable JSON (%s)", attempt, exc)
            if attempt == 2:
                raise AnalysisError(f"model did not return valid JSON: {exc}") from exc
            messages = messages + [
                {"role": "assistant", "content": text[:4000]},
                {"role": "user", "content": REPAIR},
            ]
    raise AnalysisError("unreachable")


def analyse(articles: list[dict], date_label: str) -> dict:
    selected = articles[: config.MAX_ARTICLES_TO_MODEL]
    if not selected:
        raise AnalysisError("no articles to analyse")
    payload, usage = call_model(selected, date_label)
    analysis = validate(payload, {a["id"] for a in selected})
    analysis["meta"].update(usage)
    analysis["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    analysis["date_label"] = date_label
    return analysis


# --------------------------------------------------------------- offline mode


def fallback_analysis(articles: list[dict], date_label: str, reason: str) -> dict:
    """Keyword-only briefing. Publishes something honest when the API is down."""
    selected = articles[: config.MAX_ARTICLES_TO_MODEL]
    theme_hits: Counter = Counter()
    per_article: dict[str, dict] = {}
    theme_terms = {
        "Build-to-rent": ("build-to-rent", "build to rent", "btr", "co-living"),
        "Housebuilders": ("housebuilder", "barratt", "taylor wimpey", "persimmon",
                          "bellway", "vistry", "berkeley", "redrow"),
        "Planning policy": ("planning", "local plan", "green belt", "grey belt",
                            "section 106", "nppf", "appeal"),
        "Housing supply": ("supply", "completions", "starts", "delivery", "target",
                           "shortage", "pipeline"),
        "Interest rates & mortgages": ("interest rate", "bank of england", "mortgage",
                                       "base rate", "inflation", "gilt"),
        "Residential investment": ("investment", "acquisition", "portfolio", "funding",
                                   "forward fund", "deal", "£"),
        "Affordable housing": ("affordable", "social rent", "shared ownership",
                               "housing association", "registered provider"),
        "Student housing": ("student", "pbsa"),
        "Later living": ("later living", "retirement", "senior living", "care home"),
        "Regional development": ("regeneration", "masterplan", "devolution",
                                 "levelling up", "combined authority"),
    }
    for article in selected:
        blob = f"{article['title']} {article.get('excerpt','')}".lower()
        found = [t for t, terms in theme_terms.items() if any(x in blob for x in terms)]
        for theme in found:
            theme_hits[theme] += 1
        per_article[article["id"]] = {
            "id": article["id"],
            "importance": "Medium",
            "summary": article.get("excerpt", "")[:220],
            "why_it_matters": "",
            "themes": found[:3],
            "companies": article.get("entities", [])[:4],
            "locations": [],
        }

    entities: Counter = Counter()
    for article in selected:
        for entity in article.get("entities", []):
            entities[entity] += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "date_label": date_label,
        "executive_summary": (
            "AI analysis did not run for this edition, so the briefing below is "
            f"unanalysed. Reason: {reason}\n\n"
            f"{len(selected)} items were collected and are listed under Top "
            "stories with their original headlines and links. Themes and "
            "companies are keyword counts, not analysis."
        ),
        "sentiment": {
            "overall": "neutral",
            "score": 0,
            "rationale": "No sentiment reading — analysis unavailable.",
            "positive_signals": [],
            "neutral_signals": [],
            "negative_signals": [],
        },
        "themes": [
            {
                "name": name,
                "count": count,
                "direction": "steady",
                "summary": "",
                "article_ids": [],
            }
            for name, count in theme_hits.most_common()
        ],
        "companies": [
            {"name": name, "type": "Other", "mentions": count, "context": ""}
            for name, count in entities.most_common(20)
        ],
        "projects": [],
        "policy": [],
        "investor_view": {
            "opportunities": [],
            "risks": [],
            "capital_flows": [],
            "watch_next": [],
        },
        "regions": [],
        "articles": per_article,
        "meta": {
            "rated": 0,
            "unrated": len(selected),
            "degraded": True,
            "degraded_reason": reason,
            "model": None,
        },
    }
