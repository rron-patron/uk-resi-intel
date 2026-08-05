"""Run every source, drop what's already been seen, write today's raw JSON."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from . import config, feeds
from .models import Article, dedupe, title_fingerprint

log = logging.getLogger(__name__)


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def prune_ledger(ledger: dict) -> dict:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=config.SEEN_RETENTION_DAYS)
    ).isoformat()
    return {k: v for k, v in ledger.items() if v >= cutoff}


def collect(force: bool = False) -> dict:
    """Collect from all sources. `force` ignores the seen-ledger (useful locally)."""
    ledger = prune_ledger(load_json(config.SEEN_LEDGER, {}))
    resolved = load_json(config.RESOLVED_FEEDS, {})
    now = datetime.now(timezone.utc)

    fresh: list[Article] = []
    health: list[dict] = []

    for source in config.SOURCES:
        report = feeds.fetch_source(source, resolved)
        found = report["articles"]
        health.append(
            {
                "source": source.key,
                "name": source.name,
                "route": report["route"],
                "url": report["url"],
                "found": len(found),
                "attempts": report["attempts"],
            }
        )
        log.info("%-22s %-11s %d item(s)", source.key, report["route"], len(found))
        if report["route"] in {"feed", "discovered"}:
            resolved[source.key] = report["url"]
        fresh.extend(found)

    fresh = dedupe(fresh)

    if not force:
        kept = []
        for article in fresh:
            url_key, title_key = article.dedupe_keys
            if url_key in ledger or title_key in ledger:
                continue
            kept.append(article)
        new_articles = kept
    else:
        new_articles = fresh

    stamp = now.astimezone(config.LONDON).date().isoformat()
    payload = {
        "collected_at": now.isoformat(timespec="seconds"),
        "date_london": stamp,
        "counts": {
            "seen_in_feeds": len(fresh),
            "new": len(new_articles),
            "sources_live": sum(1 for h in health if h["found"] > 0),
            "sources_total": len(health),
        },
        "source_health": health,
        "articles": [a.to_dict() for a in new_articles],
    }

    save_json(config.RAW / f"{stamp}.json", payload)

    for article in new_articles:
        url_key, title_key = article.dedupe_keys
        ledger[url_key] = now.isoformat(timespec="seconds")
        ledger[title_key] = now.isoformat(timespec="seconds")
    save_json(config.SEEN_LEDGER, ledger)
    save_json(config.RESOLVED_FEEDS, resolved)

    return payload


def recent_articles(days: int = 3) -> list[dict]:
    """Pool the last few days so a quiet morning still has a briefing."""
    pool: dict[str, dict] = {}
    seen_titles: set[str] = set()
    today = datetime.now(config.LONDON).date()
    for offset in range(days):
        day = (today - timedelta(days=offset)).isoformat()
        payload = load_json(config.RAW / f"{day}.json", None)
        if not payload:
            continue
        for raw in payload.get("articles", []):
            fp = title_fingerprint(raw.get("title", ""))
            if raw["id"] in pool or fp in seen_titles:
                continue
            seen_titles.add(fp)
            pool[raw["id"]] = raw
    return sorted(
        pool.values(), key=lambda a: a.get("published") or "", reverse=True
    )
