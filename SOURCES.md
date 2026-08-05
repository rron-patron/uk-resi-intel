# Sources

Nine sources, defined in `SOURCES` in
[`src/uk_resi/config.py`](src/uk_resi/config.py).

## What is monitored

| Source | Type | Scope | Notes |
|---|---|---|---|
| Bisnow UK | Trade press | Mixed sector and geography | Keyword filter plus UK URL guard |
| Inside Housing | Trade press | Residential only | Headlines ungated, bodies subscriber-only |
| Property Week — Residential | Trade press | Mixed sector | Largely paywalled |
| Place North West | Trade press | Mixed sector, North West | WordPress |
| Property Industry Eye | Trade press | Residential only | Replaced defunct PlaceTech |
| Estate Agent Today | Trade press | Residential only | Feed confirmed working |
| LandlordZONE | Trade press | Residential only, PRS | Webflow — scrape route |
| HM Land Registry — UK HPI | Official data | Residential only | GOV.UK Atom |
| ONS — Housing & Prices | Official data | Residential only | ONS topic RSS |

`residential_only` sources bypass the keyword filter. Mixed-sector sources must
match at least one term in `RESIDENTIAL_TERMS` to be collected, which is what
keeps logistics and office coverage out of a residential briefing.

## Verification status

Probed live on 4 August 2026 — **6 of 9 returning items**. This table reflects
what actually happened, not what was hoped for.

| Source | Result | Route now used |
|---|---|---|
| Inside Housing | **15 items** | Syndication feed, found by autodiscovery and now pinned |
| Estate Agent Today | **12 items** | `/newsfeeds` |
| Place North West | **10 items** | `/feed/` |
| ONS — Housing | **10 items** | Scrape of the publications page; both RSS paths returned nothing |
| HM Land Registry | **1 item** | Org Atom feed — but the item was service guidance, not house price data. Reordered to query statistics first |
| Bisnow UK | **3 items, wrong country** | `/rss` is mostly US coverage. Now guarded by a UK URL check |
| Property Week | **0 items** | Blocked. See below |
| PlaceTech | **0 items** | Site is defunct. Replaced |
| LandlordZONE | **0 items** | Wrong platform assumed. Fixed |

### What each failure actually was

**PlaceTech — the site no longer publishes.** Its digital assets were sold to
CREtech in 2023 and the remaining content folded into Place North. `placetech.net`
is not a broken feed; there is nothing behind it. No scraper fixes that. It has
been replaced with **Property Industry Eye** — free, ungated, WordPress, and
covering the residential agency and housing market daily. If you would rather
track global proptech, point the source at CREtech instead.

**LandlordZONE — wrong platform.** The original config assumed WordPress and
tried `/feed/`. It is actually a **Webflow** site, and Webflow does not create
`/feed/` at all; RSS exists only if the owner enabled it, at a path they chose.
The scrape route is now primary, targeting Webflow's `.w-dyn-item` CMS wrapper
with an anchor selector as backup. The site is publishing normally, so this
should recover.

**Property Week — actively blocking.** All three feed candidates *and* the HTML
scrape returned nothing. When every route fails together, that is normally a CDN
rule against automated requests rather than four wrong URLs. Options, in order:

1. Probe for a feed that is served anyway: `python scripts/probe.py https://www.propertyweek.com/rss`
2. Substitute an accessible title. Free and ungated UK residential alternatives:
   **Property Industry Eye**, **Landlord Today** (`/breaking-news`, same
   publisher as Estate Agent Today, so the feed pattern is known to work),
   **Showhouse** for housebuilding, **The Negotiator** for agency
3. Leave it in and accept eight live sources — the briefing does not depend on
   any single publisher

Do not work around the block by disguising the User-Agent.

**Bisnow — right feed, wrong country.** `bisnow.com/london/rss` returned nothing
and `bisnow.com/rss` returned US stories that slipped past the residential
keyword filter. A geography guard now requires `/london/`, `/uk/` or
`/united-kingdom/` in the item URL. Expect Bisnow to fall through to its scrape
route as a result, which is the correct behaviour — an empty Bisnow is better
than three US data-centre stories in a UK residential briefing.

**HM Land Registry — right feed, wrong content.** The organisation Atom feed
carries all HMLR output, mostly guidance and service notices. The candidates are
now ordered to query GOV.UK's statistics search first, so UK HPI releases surface
ahead of general publications.

### Diagnosing a zero yourself

`verify` now distinguishes the two kinds of zero, because they need different
fixes:

- **unreachable** — 404, blocked, or robots.txt disallowed. Find a different URL
- **parsed N entries but all filtered out** — printed as
  `filtered: stale=12, off_topic=8`. The URL is fine; the items were too old,
  not residential, or out of geography

To test candidate URLs before editing config:

```bash
export PYTHONPATH=src
python scripts/probe.py https://example.co.uk/feed/ https://example.co.uk/rss
python scripts/probe.py --selectors https://example.co.uk/news/
```

The `--selectors` mode lists repeated container classes and common link paths on
a page, which is how you build a `ScrapeRule` without guessing.

## How resolution works

Each source is tried three ways, in order, and the first route that returns
items wins:

1. **Known feed URLs** — every candidate in `Source.feeds`, in order. A
   previously successful URL is cached in `data/resolved_feeds.json` and tried
   first on subsequent runs.
2. **Autodiscovery** — fetch the homepage and look for
   `<link rel="alternate" type="application/rss+xml">`.
3. **HTML scrape** — apply the CSS selectors in `Source.scrape` to a listing
   page.

A source that fails all three is recorded in the run's `source_health` report,
shown in the dashboard footer and the workflow summary, and skipped. It never
breaks the run.

## Fixing a dead source

### If a feed URL has moved

Find the real one: open the publisher's homepage, view source, and search for
`rss+xml`. Or try the usual suspects — `/feed/`, `/rss`, `/rss.xml`,
`/feeds/all.xml`, `/newsfeeds`.

Add it to the **front** of that source's `feeds` tuple in `config.py`:

```python
Source(
    key="property_week_resi",
    name="Property Week — Residential",
    homepage="https://www.propertyweek.com",
    feeds=(
        "https://www.propertyweek.com/the-actual-working-url",  # ← new, tried first
        "https://www.propertyweek.com/rss",
        ...
    ),
    ...
)
```

Then delete the stale cache entry and re-probe:

```bash
rm data/resolved_feeds.json
export PYTHONPATH=src
python -m uk_resi.cli verify
```

### If there is no feed at all

Fix the `ScrapeRule` instead. Open the listing page in a browser, inspect one
story card, and find a selector that matches the container for a single story:

```python
scrape=ScrapeRule(
    list_url="https://www.example.co.uk/news/",
    item="article.story-card",      # container for one story
    link="h3 a",                    # anchor inside it
    title="h3",                     # optional; defaults to anchor text
    date="time",                    # element with a datetime attribute
    summary="p.standfirst",         # optional teaser
),
```

The scraper discards anything with a title under 20 characters, which filters out
navigation and "read more" links. Verify with:

```bash
python -m uk_resi.cli verify -v
```

### If a source blocks you

A `403` on every route usually means the publisher is blocking automated
requests, often via a CDN. Options, in order of preference:

1. Check whether they publish a feed elsewhere — many block HTML scraping but
   serve RSS freely
2. Contact them; several trade titles will allow a named, rate-limited crawler
3. Remove the source

Do not work around a block by disguising the User-Agent. `robots.txt` compliance
and an honest, contactable User-Agent are the terms on which this project is
reasonable to run at all.

## Adding a new source

Append a `Source` to the `SOURCES` tuple:

```python
Source(
    key="my_source",                    # unique, used in IDs and filters
    name="My Source",                   # shown in the dashboard
    homepage="https://example.co.uk",
    kind="news",                        # or "data" for statistical releases
    residential_only=True,              # False means keyword-filtered
    feeds=("https://example.co.uk/feed/",),
    scrape=ScrapeRule(
        list_url="https://example.co.uk/news/",
        item="article",
    ),
    note="Anything a future maintainer should know.",
),
```

Then `python -m uk_resi.cli verify` to confirm, and commit. Nothing else needs
changing — the dashboard reads the source list from the same config.

## Adding or changing themes

`THEMES` in `config.py` is a closed list, deliberately. The validator drops any
theme the model invents, which is what makes counts comparable across days. If
you add one, also add its keyword terms to `theme_terms` in
`analyse.fallback_analysis` so degraded editions stay consistent.

Changing the list breaks comparability with earlier archived editions. Note the
date you changed it.

## Publishers

If you publish one of these titles and would rather not be included, open an
issue and the source will be removed. This project stores headlines, links and a
400-character maximum excerpt, always links to the original, honours
`robots.txt`, rate-limits to one request per 1.5 seconds per host, and identifies
itself with a contactable User-Agent.
