"""Getting items out of a source: feed first, HTML listing page as a fallback.

Resolution order per source:
  1. each candidate URL in `Source.feeds`
  2. autodiscovery — `<link rel="alternate" type=".../rss+xml">` on the homepage
  3. `Source.scrape` CSS rules against an HTML listing page
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from . import config, http
from .config import Source
from .models import Article

log = logging.getLogger(__name__)

FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/xml")


# ----------------------------------------------------------------- date logic


def parse_date(value) -> str | None:
    """Return an ISO-8601 UTC string, or None if unparseable."""
    if not value:
        return None
    if isinstance(value, tuple) or hasattr(value, "tm_year"):
        try:
            return datetime(*value[:6], tzinfo=timezone.utc).isoformat(
                timespec="seconds"
            )
        except (TypeError, ValueError):
            return None
    try:
        dt = dateparser.parse(str(value), dayfirst=True, fuzzy=True)
    except (ValueError, OverflowError, TypeError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=config.LONDON)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def is_recent(iso: str | None, hours: int = config.LOOKBACK_HOURS) -> bool:
    """Undated items are kept — better a stale headline than a silent gap."""
    if not iso:
        return True
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return True
    return dt >= datetime.now(timezone.utc) - timedelta(hours=hours)


# --------------------------------------------------------------- text helpers


def strip_html(value: str) -> str:
    if not value:
        return ""
    return " ".join(BeautifulSoup(value, "lxml").get_text(" ").split())


ENTITY_STOPWORDS = {
    "The", "This", "That", "There", "It", "In", "On", "At", "By", "For", "New",
    "UK", "England", "Wales", "Scotland", "Northern", "Ireland", "Government",
    "Council", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday", "January", "February", "March", "April", "May",
    "June", "July", "August", "September", "October", "November", "December",
}

# Capitalised runs, optionally ending in a corporate suffix. A cheap first pass:
# the model does the real entity work, this just gives it a hint and powers the
# fallback view when the API is unavailable.
ENTITY_RE = re.compile(
    r"\b([A-Z][A-Za-z&'’.-]+(?:\s+(?:of|and|de|van|der)?\s*[A-Z][A-Za-z&'’.-]+){0,3}"
    r"(?:\s+(?:Group|Homes|Living|Capital|Partners|Properties|Property|Estates|"
    r"Developments|Investments|Housing|Association|Trust|REIT|plc|PLC|Ltd|LLP))?)\b"
)


def guess_entities(text: str, limit: int = 8) -> list[str]:
    found: list[str] = []
    for match in ENTITY_RE.finditer(text or ""):
        name = match.group(1).strip(" .,'’-")
        if len(name) < 4 or name in ENTITY_STOPWORDS:
            continue
        if name.split()[0] in ENTITY_STOPWORDS and len(name.split()) == 1:
            continue
        if name not in found:
            found.append(name)
        if len(found) >= limit:
            break
    return found


def relevant(source: Source, text: str) -> bool:
    if source.residential_only:
        return True
    haystack = (text or "").lower()
    return any(term in haystack for term in config.RESIDENTIAL_TERMS)


# ---------------------------------------------------------------- feed reading


def read_feed(source: Source, url: str) -> list[Article]:
    resp = http.get(url, expect="feed")
    if resp is None:
        return []
    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        log.info("%s parsed as malformed with no entries", url)
        return []
    out: list[Article] = []
    for entry in parsed.entries[:40]:
        title = strip_html(entry.get("title", ""))
        link = entry.get("link") or ""
        if not title or not link:
            continue
        summary = strip_html(
            entry.get("summary")
            or (entry.get("content") or [{}])[0].get("value", "")
            or ""
        )
        published = parse_date(
            entry.get("published_parsed")
            or entry.get("updated_parsed")
            or entry.get("published")
            or entry.get("updated")
        )
        if not is_recent(published):
            continue
        blob = f"{title}. {summary}"
        if not relevant(source, blob):
            continue
        out.append(
            Article(
                source_key=source.key,
                source_name=source.name,
                title=title,
                url=urljoin(source.homepage, link),
                published=published,
                excerpt=config.excerpt(summary),
                entities=guess_entities(blob),
                kind=source.kind,
            )
        )
    return out


def discover_feed(source: Source) -> str | None:
    """Look for a declared feed on the homepage."""
    resp = http.get(source.homepage)
    if resp is None:
        return None
    soup = BeautifulSoup(resp.text, "lxml")
    for link in soup.find_all("link", rel=lambda v: v and "alternate" in v):
        if (link.get("type") or "").lower() in FEED_TYPES and link.get("href"):
            return urljoin(source.homepage, link["href"])
    return None


# ------------------------------------------------------------ HTML fallback


def scrape_listing(source: Source) -> list[Article]:
    rule = source.scrape
    if rule is None:
        return []
    resp = http.get(rule.list_url)
    if resp is None:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    out: list[Article] = []
    for node in soup.select(rule.item)[:40]:
        anchor = node.select_one(rule.link)
        if anchor is None or not anchor.get("href"):
            continue
        title = (
            strip_html(node.select_one(rule.title).get_text())
            if rule.title and node.select_one(rule.title)
            else strip_html(anchor.get_text())
        )
        if len(title) < 20:  # nav links, tags, "read more"
            continue
        url = urljoin(rule.list_url, anchor["href"])
        summary = ""
        if rule.summary and node.select_one(rule.summary):
            summary = strip_html(node.select_one(rule.summary).get_text())
        else:  # fall back to the longest paragraph in the card
            paras = [strip_html(p.get_text()) for p in node.find_all("p")]
            summary = max(paras, key=len, default="")
        published = None
        time_el = node.select_one(rule.date) if rule.date else None
        if time_el is not None:
            published = parse_date(
                time_el.get("datetime") or time_el.get("content") or time_el.get_text()
            )
        if not is_recent(published):
            continue
        blob = f"{title}. {summary}"
        if not relevant(source, blob):
            continue
        out.append(
            Article(
                source_key=source.key,
                source_name=source.name,
                title=title,
                url=url,
                published=published,
                excerpt=config.excerpt(summary),
                entities=guess_entities(blob),
                kind=source.kind,
            )
        )
    return out


def fetch_source(source: Source, resolved: dict[str, str] | None = None) -> dict:
    """Try every route for one source. Always returns a report, never raises."""
    resolved = resolved or {}
    attempts: list[str] = []
    candidates: list[str] = []
    if resolved.get(source.key):
        candidates.append(resolved[source.key])
    candidates += [u for u in source.feeds if u not in candidates]

    for url in candidates:
        try:
            items = read_feed(source, url)
        except Exception as exc:  # a bad feed must not kill the run
            log.warning("%s: feed error on %s: %s", source.key, url, exc)
            attempts.append(f"feed error {url}")
            continue
        attempts.append(f"feed {url} -> {len(items)}")
        if items:
            return {
                "source": source.key,
                "route": "feed",
                "url": url,
                "articles": items,
                "attempts": attempts,
            }

    try:
        discovered = discover_feed(source)
    except Exception as exc:
        log.warning("%s: discovery error: %s", source.key, exc)
        discovered = None
    if discovered and discovered not in candidates:
        try:
            items = read_feed(source, discovered)
            attempts.append(f"discovered {discovered} -> {len(items)}")
            if items:
                return {
                    "source": source.key,
                    "route": "discovered",
                    "url": discovered,
                    "articles": items,
                    "attempts": attempts,
                }
        except Exception as exc:
            log.warning("%s: discovered feed failed: %s", source.key, exc)

    try:
        items = scrape_listing(source)
    except Exception as exc:
        log.warning("%s: scrape error: %s", source.key, exc)
        items = []
    attempts.append(
        f"scrape {source.scrape.list_url if source.scrape else '-'} -> {len(items)}"
    )
    return {
        "source": source.key,
        "route": "scrape" if items else "failed",
        "url": source.scrape.list_url if source.scrape else source.homepage,
        "articles": items,
        "attempts": attempts,
    }
