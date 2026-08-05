# Sources

Nine sources, defined in `SOURCES` in
[`src/uk_resi/config.py`](src/uk_resi/config.py).

## What is monitored

| Source | Type | Scope | Notes |
|---|---|---|---|
| Bisnow UK | Trade press | Mixed sector | Keyword-filtered to residential |
| Inside Housing | Trade press | Residential only | Headlines ungated, bodies subscriber-only |
| Property Week — Residential | Trade press | Mixed sector | Largely paywalled |
| Place North West | Trade press | Mixed sector, North West | WordPress |
| PlaceTech | Trade press | Proptech | Keyword-filtered |
| Estate Agent Today | Trade press | Residential only | Feed confirmed working |
| LandlordZONE | Trade press | Residential only, PRS | WordPress |
| HM Land Registry — UK HPI | Official data | Residential only | GOV.UK Atom |
| ONS — Housing & Prices | Official data | Residential only | ONS topic RSS |

`residential_only` sources bypass the keyword filter. Mixed-sector sources must
match at least one term in `RESIDENTIAL_TERMS` to be collected, which is what
keeps logistics and office coverage out of a residential briefing.

## Verification status

Honesty about what was actually confirmed, because it determines how much of
step 2.8 in [SETUP.md](SETUP.md) is real work:

| Source | Feed status |
|---|---|
| Estate Agent Today | **Confirmed.** `/newsfeeds` serves `application/xml` |
| Place North West, PlaceTech, LandlordZONE | **Likely.** WordPress sites, `/feed/` is the standard endpoint; their terms reference RSS availability |
| HM Land Registry | **Likely.** GOV.UK exposes Atom by appending `.atom` to organisation and search pages |
| ONS | **Likely.** ONS topic listing pages carry an RSS link |
| Bisnow UK, Inside Housing, Property Week | **Unconfirmed.** Candidates are informed guesses; expect to fix at least one |

Run `python -m uk_resi.cli verify` before trusting the first edition.

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
