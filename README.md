# UK Residential Property Intelligence

A daily market intelligence briefing on UK residential property, assembled and
published without anyone touching it. Every weekday at 09:00 London time a
GitHub Action collects headlines and data releases from nine trade and official
sources, sends them to Claude for analysis and ranking, and publishes a
dashboard to GitHub Pages.

**Live site:** `https://rron-patron.github.io/uk-resi-intel/`
**Set-up:** [SETUP.md](SETUP.md) — do this first, it takes about 15 minutes
**Sources:** [SOURCES.md](SOURCES.md) — what is monitored and how to fix a dead feed

---

## What it produces

| Section | Content |
|---|---|
| Morning note | 3–5 paragraphs on what actually moved, written from the day's collection |
| Market reading | Sentiment score −100 to +100 with the positive, neutral and negative signals behind it |
| Top stories | Every item rated Critical / High / Medium / Low, with a summary and a "why it matters" line |
| Market themes | Ten canonical themes with counts and a rising / steady / cooling direction |
| Companies tracker | Developers, investors, housebuilders, funds, housing associations and proptech, by mention count |
| Regional activity | Locations named in the coverage |
| Schemes in the news | Named developments with location, unit count and value where stated |
| Policy monitor | Government, planning, regulation and tax movement |
| Investor view | Opportunities, risks, capital flows, and what to watch next |
| Back editions | Every previous day, served from the archive |

Stories are filterable by importance band, source and free text. The page is a
single HTML file with no framework and no build step; everything is resolved in
Python and written to one JSON file.

## How it works

```
09:00 London  ┌─────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────┐
  (Actions) → │  collect    │ → │   analyse    │ → │     build     │ → │  Pages   │
              │ 9 sources   │   │ Claude API   │   │ dashboard.json│   │  deploy  │
              └─────────────┘   └──────────────┘   └───────────────┘   └──────────┘
                     ↓                  ↓                  ↓
              data/raw/DATE.json  data/analysis/    docs/data/ +
              + seen.json ledger    DATE.json        archive/DATE.json
```

**Collection** tries each source three ways in order: known feed URLs, then feed
autodiscovery from the homepage `<link rel="alternate">`, then a CSS-selector
scrape of a listing page. A source that fails all three is logged and skipped —
one dead publisher never breaks a run. Mixed-sector titles are keyword-filtered
down to residential; residential-only titles pass straight through.

**Deduplication** is two-layer. Within a run, URLs are canonicalised (tracking
parameters stripped, `www.` and trailing slashes normalised) and titles are
fingerprinted, so the same story from two publishers collapses to one. Across
runs, a 60-day `data/seen.json` ledger stops yesterday's stories reappearing.

**Analysis** sends up to 60 items to Claude with a strict JSON schema and an
importance rubric. Malformed JSON is repaired before it is rejected — unescaped
double quotes inside strings, literal newlines and trailing commas are the three
mistakes models actually make, and all three are fixed mechanically. Anything
still broken gets up to two repair turns with the parser error quoted back. The
response is then validated field by field: unknown themes are
dropped so the theme axis stays comparable day to day, ratings for IDs that were
never sent are discarded, and out-of-range scores are clamped. If the JSON is
malformed, one repair attempt is made. If the API is unavailable entirely, the
run publishes a **degraded edition** — real headlines and links, keyword-derived
themes, no ratings — clearly labelled as such at the top of the page.

**The 09:00 problem.** GitHub cron is UTC only, so a fixed expression drifts by
an hour twice a year. The workflow fires at 08:00, 09:00 and 10:30 UTC, and a
gate command decides whether to proceed: publish only once London local time has
passed 09:00 *and* today's edition does not already exist. That is correct in
both BST and GMT, and it survives GitHub delaying or dropping a scheduled run,
which happens more often than you would like.

## Commands

Everything runs through one CLI. `PYTHONPATH=src` is required.

```bash
export PYTHONPATH=src

python -m uk_resi.cli verify      # probe all nine sources, report what resolves
python -m uk_resi.cli collect     # scrape only, no API call
python -m uk_resi.cli analyse     # AI pass over today's collection
python -m uk_resi.cli build       # rebuild docs/data/dashboard.json
python -m uk_resi.cli run         # all three in sequence
python -m uk_resi.cli gate        # exit 0 if today's edition is due
python -m uk_resi.cli health      # today's per-source collection report
```

Useful flags: `--offline` skips the API, `--strict` fails instead of degrading,
`--force` ignores the seen ledger, `-v` for debug logging.

## Local development

```bash
git clone https://github.com/rron-patron/uk-resi-intel.git
cd uk-resi-intel
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export PYTHONPATH=src

cp .env.example .env          # add your key if you want to run the AI step
python -m uk_resi.cli verify  # check which sources currently work
```

To work on the frontend without spending API calls or hitting any publisher:

```bash
python scripts/demo_data.py     # synthetic, clearly-labelled preview data
python -m uk_resi.cli build
python -m http.server --directory docs 8000
# then reset the committed page:
python scripts/make_seed.py
```

Opening `docs/index.html` directly from disk will not work — `fetch` is blocked
on `file://`. Serve it over HTTP.

```bash
pytest -q    # 23 tests, no network or API key needed
```

## Cost

At 60 articles a day the analysis call runs roughly 20k input and 4k output
tokens. On `claude-sonnet-5` at $3/$15 per million tokens that is about
**$0.12 a day, so $3–4 a month**. Introductory Sonnet 5 pricing of $2/$10
applies until 31 August 2026, so expect less than that initially.

To spend less, set `ANTHROPIC_MODEL=claude-haiku-4-5-20251001` ($1/$5) as a
repository variable, or lower `UK_RESI_MAX_ARTICLES`. To spend more for sharper
analysis, use `claude-opus-5` ($5/$25). Check current pricing at
[platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing).

## Configuration

Set these as repository variables (Settings → Secrets and variables → Actions →
Variables) or in `.env` locally. All are optional.

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | Model for the analysis call |
| `UK_RESI_MAX_ARTICLES` | `60` | Items sent to the model; drives cost |
| `UK_RESI_LOOKBACK_HOURS` | `48` | How old an item can be and still count |
| `UK_RESI_EXCERPT_CHARS` | `400` | Publisher text stored per item |
| `UK_RESI_CRAWL_DELAY` | `1.5` | Seconds between requests to one host |
| `UK_RESI_RESPECT_ROBOTS` | `1` | Set `0` to ignore robots.txt (don't) |
| `UK_RESI_USER_AGENT` | repo URL | Change to point at your own fork |

`ANTHROPIC_API_KEY` is a **secret**, not a variable.

## Maintenance

Close to zero, with two things to watch.

**Dead sources.** Feed URLs and page markup change without notice. The Source
health workflow probes everything every Monday at 07:00 and opens a GitHub issue
listing anything that returned nothing, so it surfaces as a task rather than a
quietly thinner briefing. See [SOURCES.md](SOURCES.md) to fix one.

**Scheduled workflows going dormant.** GitHub disables cron on repositories with
no activity for 60 days, and commits made by `GITHUB_TOKEN` do not reliably count
as activity. If editions stop appearing, open the Actions tab — there will be a
banner offering to re-enable. Pushing any commit yourself also resets the clock.

## Attribution and limits

Headlines, links and excerpts belong to the publishers listed in
[SOURCES.md](SOURCES.md). This project stores a short excerpt for context and
always links to the original; it does not reproduce article bodies and is not a
substitute for a subscription. Requests identify themselves with a contactable
User-Agent, honour `robots.txt`, and are rate-limited to one every 1.5 seconds
per host. If you are a publisher and want out, open an issue and the source will
be removed.

Summaries, ratings, sentiment and commentary are generated by a language model.
They will sometimes be wrong. Verify anything you act on against the linked
original. Nothing here is investment advice.

## Licence

Code is MIT licensed — see [LICENSE](LICENSE). That covers this repository's own
source only, not the content it links to.
