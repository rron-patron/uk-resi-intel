"""Join raw articles to their AI ratings and write docs/data/dashboard.json.

The frontend reads exactly one file. Everything it needs to render is resolved
here, so the browser does no joining and no date maths.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone

from . import config
from .collect import load_json, save_json

log = logging.getLogger(__name__)

IMPORTANCE_RANK = {name: i for i, name in enumerate(config.IMPORTANCE_ORDER)}


def london_now() -> datetime:
    return datetime.now(config.LONDON)


def build_dashboard(raw: dict, analysis: dict) -> dict:
    articles = raw.get("articles", [])
    if not articles:  # nothing new today — reuse the pooled set the analysis saw
        articles = raw.get("pooled_articles", [])
    ratings = analysis.get("articles", {})

    stories = []
    for article in articles:
        rating = ratings.get(article["id"], {})
        stories.append(
            {
                "id": article["id"],
                "title": article["title"],
                "source": article["source_name"],
                "source_key": article["source_key"],
                "url": article["url"],
                "published": article.get("published"),
                "kind": article.get("kind", "news"),
                "excerpt": article.get("excerpt", ""),
                "importance": rating.get("importance", "Low"),
                "summary": rating.get("summary", ""),
                "why_it_matters": rating.get("why_it_matters", ""),
                "themes": rating.get("themes", []),
                "companies": rating.get("companies", []),
                "locations": rating.get("locations", []),
            }
        )

    # Highest importance first; newest first within a band. Python's sort is
    # stable, so the date pass survives the importance pass.
    stories.sort(key=lambda s: s["published"] or "", reverse=True)
    stories.sort(key=lambda s: IMPORTANCE_RANK.get(s["importance"], 9))

    counts = Counter(s["importance"] for s in stories)
    by_source = Counter(s["source"] for s in stories)

    now = london_now()
    return {
        "schema": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generated_at_london": now.isoformat(timespec="minutes"),
        "date_label": now.strftime("%d %B %Y").lstrip("0"),
        "time_label": now.strftime("%H:%M %Z"),
        "executive_summary": analysis.get("executive_summary", ""),
        "sentiment": analysis.get("sentiment", {}),
        "themes": analysis.get("themes", []),
        "companies": analysis.get("companies", []),
        "projects": analysis.get("projects", []),
        "policy": analysis.get("policy", []),
        "investor_view": analysis.get("investor_view", {}),
        "regions": analysis.get("regions", []),
        "stories": stories,
        "stats": {
            "stories": len(stories),
            "critical": counts.get("Critical", 0),
            "high": counts.get("High", 0),
            "medium": counts.get("Medium", 0),
            "low": counts.get("Low", 0),
            "sources_live": raw.get("counts", {}).get("sources_live", 0),
            "sources_total": raw.get("counts", {}).get("sources_total", len(config.SOURCES)),
            "by_source": [{"name": n, "count": c} for n, c in by_source.most_common()],
        },
        "sources": [
            {"key": s.key, "name": s.name, "homepage": s.homepage, "kind": s.kind}
            for s in config.SOURCES
        ],
        "source_health": raw.get("source_health", []),
        "meta": analysis.get("meta", {}),
    }


def write_dashboard(dashboard: dict) -> None:
    save_json(config.DOCS_DATA / "dashboard.json", dashboard)
    day = dashboard["generated_at_london"][:10]
    save_json(config.DOCS_ARCHIVE / f"{day}.json", dashboard)

    index_path = config.DOCS_ARCHIVE / "index.json"
    index = load_json(index_path, [])
    entry = {
        "date": day,
        "file": f"archive/{day}.json",
        "stories": dashboard["stats"]["stories"],
        "sentiment": dashboard.get("sentiment", {}).get("overall", "neutral"),
        "score": dashboard.get("sentiment", {}).get("score", 0),
    }
    index = [e for e in index if e.get("date") != day] + [entry]
    index.sort(key=lambda e: e["date"], reverse=True)
    save_json(index_path, index[:180])
    log.info(
        "wrote dashboard.json (%d stories) and archive/%s.json",
        dashboard["stats"]["stories"],
        day,
    )
