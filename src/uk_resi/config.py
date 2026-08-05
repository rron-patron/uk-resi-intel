"""Source registry and runtime settings.

Feed URLs drift. Every source below carries a *list* of candidate feed URLs and,
where a feed may not exist at all, an HTML listing page to fall back to. The
collector tries candidates in order, then attempts autodiscovery from the
homepage, then the HTML listing. Run `python -m uk_resi.cli verify` to see which
route currently resolves for each source and to write the winners to
`data/resolved_feeds.json`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------- paths / env

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
ANALYSIS = DATA / "analysis"
DOCS = ROOT / "docs"
DOCS_DATA = DOCS / "data"
DOCS_ARCHIVE = DOCS_DATA / "archive"
SEEN_LEDGER = DATA / "seen.json"
RESOLVED_FEEDS = DATA / "resolved_feeds.json"

LONDON = ZoneInfo("Europe/London")

# Identify the bot honestly so publishers can contact you or block you.
USER_AGENT = os.getenv(
    "UK_RESI_USER_AGENT",
    "uk-resi-intel/1.0 (+https://github.com/YOUR-USERNAME/uk-resi-intel; "
    "daily headline aggregator; contact via repo issues)",
)

REQUEST_TIMEOUT = int(os.getenv("UK_RESI_TIMEOUT", "25"))
CRAWL_DELAY = float(os.getenv("UK_RESI_CRAWL_DELAY", "1.5"))  # seconds per host
RESPECT_ROBOTS = os.getenv("UK_RESI_RESPECT_ROBOTS", "1") != "0"

# How far back an item can be published and still count as "current".
LOOKBACK_HOURS = int(os.getenv("UK_RESI_LOOKBACK_HOURS", "48"))
# Dedupe memory.
SEEN_RETENTION_DAYS = int(os.getenv("UK_RESI_SEEN_RETENTION_DAYS", "60"))

# Only ever store a short excerpt. The dashboard links out; it does not
# republish. Keep this small.
EXCERPT_CHARS = int(os.getenv("UK_RESI_EXCERPT_CHARS", "400"))

# Model + budget. See README for cost maths.
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
MAX_ARTICLES_TO_MODEL = int(os.getenv("UK_RESI_MAX_ARTICLES", "60"))
MAX_OUTPUT_TOKENS = int(os.getenv("UK_RESI_MAX_OUTPUT_TOKENS", "12000"))

# --------------------------------------------------------------- source model


@dataclass(frozen=True)
class ScrapeRule:
    """CSS-selector fallback for sources without a working feed."""

    list_url: str
    item: str  # container for one story
    link: str = "a"  # anchor inside the container
    title: str = ""  # defaults to anchor text
    date: str = "time"  # element carrying a datetime attribute or text
    summary: str = ""  # optional standfirst/teaser


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    homepage: str
    kind: str = "news"  # "news" | "data"
    # Residential-only titles skip keyword filtering; mixed-sector titles do not.
    residential_only: bool = False
    feeds: tuple[str, ...] = ()
    scrape: ScrapeRule | None = None
    note: str = ""


SOURCES: tuple[Source, ...] = (
    Source(
        key="bisnow_uk",
        name="Bisnow UK",
        homepage="https://www.bisnow.com/london",
        feeds=(
            "https://www.bisnow.com/london/rss",
            "https://www.bisnow.com/rss",
            "https://www.bisnow.com/london/feed",
        ),
        scrape=ScrapeRule(
            list_url="https://www.bisnow.com/london",
            item="article, div[class*='card'], li[class*='story']",
        ),
        note="Mixed sector — keyword filter applies.",
    ),
    Source(
        key="inside_housing",
        name="Inside Housing",
        homepage="https://www.insidehousing.co.uk",
        residential_only=True,
        feeds=(
            "https://www.insidehousing.co.uk/rss",
            "https://www.insidehousing.co.uk/feed",
            "https://www.insidehousing.co.uk/news/rss",
        ),
        scrape=ScrapeRule(
            list_url="https://www.insidehousing.co.uk/news",
            item="article, div[class*='teaser'], div[class*='card']",
        ),
        note="Headlines are ungated; article bodies are largely subscriber-only. "
        "Store headline + link only.",
    ),
    Source(
        key="property_week_resi",
        name="Property Week — Residential",
        homepage="https://www.propertyweek.com",
        feeds=(
            "https://www.propertyweek.com/rss",
            "https://www.propertyweek.com/residential/rss",
            "https://www.propertyweek.com/feed",
        ),
        scrape=ScrapeRule(
            list_url="https://www.propertyweek.com/residential",
            item="article, div[class*='teaser'], div[class*='listing']",
        ),
        note="Largely paywalled. Headline + link only.",
    ),
    Source(
        key="place_north_west",
        name="Place North West",
        homepage="https://www.placenorthwest.co.uk",
        feeds=(
            "https://www.placenorthwest.co.uk/feed/",
            "https://www.placenorthwest.co.uk/category/residential/feed/",
        ),
        scrape=ScrapeRule(
            list_url="https://www.placenorthwest.co.uk/news/",
            item="article, div[class*='post']",
        ),
        note="WordPress. Mixed sector — keyword filter applies.",
    ),
    Source(
        key="placetech",
        name="PlaceTech",
        homepage="https://placetech.net",
        feeds=(
            "https://placetech.net/feed/",
            "https://www.placetech.net/feed/",
        ),
        scrape=ScrapeRule(
            list_url="https://placetech.net/news/",
            item="article, div[class*='post']",
        ),
        note="Proptech focus. Keyword filter applies.",
    ),
    Source(
        key="estate_agent_today",
        name="Estate Agent Today",
        homepage="https://www.estateagenttoday.co.uk",
        residential_only=True,
        feeds=(
            "https://www.estateagenttoday.co.uk/newsfeeds",
            "https://www.estateagenttoday.co.uk/rss",
            "https://www.estateagenttoday.co.uk/feed/",
        ),
        scrape=ScrapeRule(
            list_url="https://www.estateagenttoday.co.uk/breaking-news/",
            item="article, div[class*='story'], div[class*='card']",
        ),
        note="Feed confirmed serving application/xml at /newsfeeds.",
    ),
    Source(
        key="landlordzone",
        name="LandlordZONE",
        homepage="https://www.landlordzone.co.uk",
        residential_only=True,
        feeds=(
            "https://www.landlordzone.co.uk/feed/",
            "https://landlordzone.co.uk/feed/",
            "https://www.landlordzone.co.uk/news/feed/",
        ),
        scrape=ScrapeRule(
            list_url="https://www.landlordzone.co.uk/news/",
            item="article, div[class*='post']",
        ),
        note="WordPress. PRS / landlord regulation.",
    ),
    Source(
        key="hm_land_registry",
        name="HM Land Registry — UK HPI",
        homepage="https://www.gov.uk/government/organisations/land-registry",
        kind="data",
        residential_only=True,
        feeds=(
            "https://www.gov.uk/government/organisations/land-registry.atom",
            "https://www.gov.uk/search/research-and-statistics.atom"
            "?organisations%5B%5D=land-registry&order=updated-newest",
        ),
        scrape=ScrapeRule(
            list_url="https://www.gov.uk/government/collections/uk-house-price-index-reports",
            item="li, article",
        ),
        note="GOV.UK exposes Atom by appending .atom to org and search pages.",
    ),
    Source(
        key="ons_housing",
        name="ONS — Housing & Prices",
        homepage="https://www.ons.gov.uk/peoplepopulationandcommunity/housing",
        kind="data",
        residential_only=True,
        feeds=(
            "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/rss",
            "https://www.ons.gov.uk/economy/inflationandpriceindices/rss",
        ),
        scrape=ScrapeRule(
            list_url="https://www.ons.gov.uk/peoplepopulationandcommunity/housing/publications",
            item="div[class*='search-result'], li[class*='result'], article",
        ),
        note="ONS exposes /rss on topic listing pages.",
    ),
)

SOURCES_BY_KEY = {s.key: s for s in SOURCES}

# ------------------------------------------------------- relevance filtering

# Mixed-sector titles (Bisnow, Place, PlaceTech, Property Week) publish office,
# retail and logistics stories too. An item needs at least one hit to survive.
RESIDENTIAL_TERMS: tuple[str, ...] = (
    "residential", "housing", "homes", "housebuild", "house build", "home build",
    "build-to-rent", "build to rent", "btr", "prs", "private rented",
    "single family", "sfr", "affordable", "social rent", "shared ownership",
    "student accommodation", "pbsa", "student housing", "later living",
    "retirement living", "senior living", "care home", "co-living", "coliving",
    "apartment", "flats", "tenant", "landlord", "renter", "leasehold",
    "freehold", "mortgage", "house price", "first-time buyer", "first time buyer",
    "planning permission", "planning reform", "local plan", "green belt",
    "grey belt", "section 106", "s106", "cil", "right to buy",
    "housing association", "registered provider", "homelessness",
    "temporary accommodation", "modular hous", "mmc", "regeneration estate",
    "dwelling", "bedroom", "beds", "renters' rights", "renters rights",
    "awaab", "decent homes", "cladding", "building safety", "epc",
)

# Canonical theme list the model must map onto (keeps the dashboard stable).
THEMES: tuple[str, ...] = (
    "Build-to-rent",
    "Housebuilders",
    "Planning policy",
    "Housing supply",
    "Interest rates & mortgages",
    "Residential investment",
    "Affordable housing",
    "Student housing",
    "Later living",
    "Regional development",
)

IMPORTANCE_ORDER = ("Critical", "High", "Medium", "Low")

COMPANY_TYPES = (
    "Developer",
    "Investor",
    "Housebuilder",
    "Fund",
    "Housing association",
    "Proptech",
    "Adviser",
    "Government body",
    "Other",
)


def excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    """Trim publisher text to a short, attributable excerpt."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"
