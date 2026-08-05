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
    "uk-resi-intel/1.0 (+https://github.com/rron-patron/uk-resi-intel; "
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
# 51 articles at full detail runs close to 12k output tokens, and a truncated
# response is unparseable. You only pay for tokens actually generated, so
# headroom is free insurance.
MAX_OUTPUT_TOKENS = int(os.getenv("UK_RESI_MAX_OUTPUT_TOKENS", "20000"))

# --------------------------------------------------------------- source model


@dataclass(frozen=True)
class ScrapeRule:
    """CSS-selector fallback for sources without a working feed."""

    list_url: str
    item: str  # container for one story; may match the <a> itself
    link: str = "a"  # anchor inside the container; "" means the item IS the anchor
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
    # For publishers that cover several countries from one feed: an item's URL
    # must contain one of these fragments to be kept. Empty means no check.
    require_url_contains: tuple[str, ...] = ()
    note: str = ""


SOURCES: tuple[Source, ...] = (
    Source(
        key="bisnow_uk",
        name="Bisnow UK",
        homepage="https://www.bisnow.com/london",
        feeds=(
            "https://www.bisnow.com/london/rss",
            "https://www.bisnow.com/rss/london",
            "https://www.bisnow.com/london/news/rss",
            "https://www.bisnow.com/rss",
        ),
        # The national /rss feed is mostly US coverage, so require a UK path.
        require_url_contains=("/london/", "/uk/", "/united-kingdom/"),
        scrape=ScrapeRule(
            list_url="https://www.bisnow.com/london",
            item="a[href*='/london/news/'], article, div[class*='card']",
            link="",
        ),
        note="Mixed sector and mixed geography. Keyword filter plus a UK URL "
        "check, because bisnow.com/rss carries US stories.",
    ),
    Source(
        key="inside_housing",
        name="Inside Housing",
        homepage="https://www.insidehousing.co.uk",
        residential_only=True,
        feeds=(
            # Confirmed working: found by autodiscovery, pinned so a run never
            # depends on parsing the homepage first.
            "https://www.insidehousing.co.uk/Syndication/DF.cfm?f=6&ft=10",
            "https://www.insidehousing.co.uk/rss",
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
        note="Paywalled AND blocking automated requests — every route returned "
        "nothing on first probe, which usually means a CDN rule rather than a "
        "wrong URL. See SOURCES.md for accessible substitutes.",
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
    # PlaceTech closed. Its digital assets were sold to CREtech in 2023 and
    # remaining content folded into Place North, so placetech.net no longer
    # publishes — the empty result was the site, not the scraper. Replaced with
    # Property Industry Eye, which is free, ungated and covers the residential
    # agency and housing market daily. Delete this source if you would rather
    # track CREtech's global proptech coverage instead.
    Source(
        key="property_industry_eye",
        name="Property Industry Eye",
        homepage="https://propertyindustryeye.com",
        residential_only=True,
        feeds=(
            "https://propertyindustryeye.com/feed/",
            "https://www.propertyindustryeye.com/feed/",
        ),
        scrape=ScrapeRule(
            list_url="https://propertyindustryeye.com/",
            item="article, div[class*='post']",
        ),
        note="Replacement for the defunct PlaceTech. WordPress, ungated.",
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
            # Webflow only serves RSS if the site owner enabled it, at a path
            # they chose. These are the conventional ones; all may 404.
            "https://www.landlordzone.co.uk/news/rss.xml",
            "https://www.landlordzone.co.uk/blog/rss.xml",
            "https://www.landlordzone.co.uk/rss.xml",
        ),
        scrape=ScrapeRule(
            # Webflow renders CMS collections as .w-dyn-item. The anchor
            # selector is the belt-and-braces fallback.
            list_url="https://www.landlordzone.co.uk/news",
            item="div.w-dyn-item, div.collection-item, a[href*='/news/']",
            link="",
        ),
        note="Webflow, not WordPress — /feed/ does not exist, which is why the "
        "original candidates all returned nothing. Scrape route is primary.",
    ),
    Source(
        key="hm_land_registry",
        name="HM Land Registry — UK HPI",
        homepage="https://www.gov.uk/government/organisations/land-registry",
        kind="data",
        residential_only=True,
        feeds=(
            # Statistics only. The plain organisation feed is dominated by
            # guidance and service notices, not house price releases.
            "https://www.gov.uk/search/research-and-statistics.atom"
            "?organisations%5B%5D=land-registry&order=updated-newest",
            "https://www.gov.uk/search/research-and-statistics.atom"
            "?keywords=UK+House+Price+Index&order=updated-newest",
            "https://www.gov.uk/government/organisations/land-registry.atom",
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
