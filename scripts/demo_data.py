"""Generate synthetic collection + analysis files so the dashboard can be
previewed locally without hitting any source or spending an API call.

Everything here is invented for layout testing. Sources are named "Demo feed"
and links point at this repo, so a preview can never be mistaken for a real
edition.

    python scripts/demo_data.py
    python -m uk_resi.cli build
    python -m http.server --directory docs 8000

Reset the committed page afterwards with:

    python scripts/make_seed.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from uk_resi import config  # noqa: E402

REPO = "https://github.com/rron-patron/uk-resi-intel"
now = datetime.now(timezone.utc)

ITEMS = [
    ("Demo feed A", "Critical",
     "MPC holds base rate as housing transaction volumes soften",
     "Committee voted to hold, with two members dissenting for a cut. Transaction volumes in the accompanying data were below consensus.",
     "Sets the discount rate every resi model in the market is running, and pushes the expected cut into the next quarter.",
     ["Interest rates & mortgages"], ["Bank of England"], ["United Kingdom"], "data"),
    ("Demo feed B", "High",
     "Institutional investor forward funds 640-home BTR scheme in Salford",
     "A forward funding agreement covering two blocks, with practical completion targeted for 2029 and management retained in-house.",
     "Confirms institutional appetite for regional BTR at scale despite a wider slowdown in single-asset trading.",
     ["Build-to-rent", "Residential investment", "Regional development"],
     ["Demo Capital Partners", "Demo Living"], ["Salford", "North West"], "news"),
    ("Demo feed C", "High",
     "Consultation opens on planning reform affecting grey belt release",
     "A twelve-week consultation covering release tests, viability evidence and affordable housing thresholds on released land.",
     "The viability test in question determines whether a large share of the pipeline is deliverable at current build costs.",
     ["Planning policy", "Housing supply"], ["Demo Department"], ["England"], "news"),
    ("Demo feed A", "High",
     "Regulator downgrades a large registered provider on governance grounds",
     "The judgement cites stock condition data quality and board oversight, with a voluntary undertaking agreed.",
     "Downgrades of this size usually pause development programmes, which tightens affordable supply in the affected region.",
     ["Affordable housing"], ["Demo Housing Group"], ["West Midlands"], "news"),
    ("Demo feed D", "Medium",
     "Housebuilder trading update points to flat completions and firmer margins",
     "Completions guidance held, average selling price up marginally, land approvals slowed in the period.",
     "Margin recovery without volume growth suggests the sector is still choosing price discipline over output.",
     ["Housebuilders"], ["Demo Homes plc"], ["United Kingdom"], "news"),
    ("Demo feed B", "Medium",
     "PBSA scheme of 410 beds approved next to a Russell Group campus",
     "Committee approved subject to conditions on cycle parking and a management plan.",
     "Adds to a thin consented PBSA pipeline in a market where beds-per-student ratios remain stretched.",
     ["Student housing"], ["Demo Student Living"], ["Leeds", "Yorkshire"], "news"),
    ("Demo feed C", "Medium",
     "Later living operator acquires three sites for integrated retirement communities",
     "Sites in the South West and South East, with a stated pipeline target of 1,200 units.",
     "One of the few sub-sectors where new entrants are still paying for land at scale.",
     ["Later living"], ["Demo Retirement Villages"], ["South West", "South East"], "news"),
    ("Demo feed D", "Low",
     "Consultancy appoints a new head of residential capital markets",
     "Joins from a competitor, effective next month.",
     "",
     ["Residential investment"], ["Demo Advisory"], ["London"], "news"),
    ("Demo feed A", "Low",
     "Awards shortlist announced for regional development of the year",
     "Six schemes shortlisted across four regions.",
     "",
     ["Regional development"], [], ["North West"], "news"),
]

articles, ratings = [], {}
for n, (src, band, title, summary, why, themes, cos, locs, kind) in enumerate(ITEMS):
    aid = f"demo{n:02d}"
    articles.append({
        "source_key": f"demo_{src[-1].lower()}",
        "source_name": src,
        "title": title,
        "url": f"{REPO}#demo-item-{n}",
        "published": (now - timedelta(hours=n * 3 + 1)).isoformat(timespec="seconds"),
        "excerpt": summary,
        "entities": cos,
        "kind": kind,
        "collected_at": now.isoformat(timespec="seconds"),
        "id": aid,
    })
    ratings[aid] = {
        "id": aid, "importance": band, "summary": summary,
        "why_it_matters": why, "themes": themes, "companies": cos, "locations": locs,
    }

theme_counts: dict[str, int] = {}
for r in ratings.values():
    for t in r["themes"]:
        theme_counts[t] = theme_counts.get(t, 0) + 1

raw = {
    "collected_at": now.isoformat(timespec="seconds"),
    "date_london": datetime.now(config.LONDON).date().isoformat(),
    "counts": {"seen_in_feeds": len(articles), "new": len(articles),
               "sources_live": 4, "sources_total": len(config.SOURCES)},
    "source_health": [
        {"source": s.key, "name": s.name,
         "route": "feed" if i % 3 else "scrape",
         "url": s.homepage, "found": (7 - i) if i < 5 else 0, "attempts": []}
        for i, s in enumerate(config.SOURCES)
    ],
    "articles": articles,
}

analysis = {
    "generated_at": now.isoformat(timespec="seconds"),
    "date_label": datetime.now(config.LONDON).strftime("%A %d %B %Y"),
    "executive_summary": (
        "This is synthetic preview data, generated locally to check the layout. "
        "None of it is real.\n\n"
        "The rate decision dominates: a hold with two dissents leaves the "
        "expected cut in the next quarter, and the transaction volumes released "
        "alongside it came in below consensus. Anyone underwriting on a "
        "near-term cut is now carrying that assumption for another three months.\n\n"
        "Against that, institutional appetite for regional build-to-rent has not "
        "gone anywhere. A 640-home forward funding in Salford is the clearest "
        "signal of the week, and it lands in the same market where a 410-bed "
        "student scheme cleared committee.\n\n"
        "The two items to file for later are the grey belt consultation, where "
        "the viability test will decide how much of the released pipeline is "
        "actually deliverable, and a governance downgrade at a large registered "
        "provider, which historically pauses development programmes."
    ),
    "sentiment": {
        "overall": "neutral", "score": -12,
        "rationale": "Capital is still committing at scale in the rented "
                     "sectors, but the rate path and softening volumes cap the "
                     "upside for now.",
        "positive_signals": ["Institutional BTR forward funding at scale",
                             "Later living land acquisition continuing",
                             "Housebuilder margins firming"],
        "neutral_signals": ["Planning consultation opens, outcome unclear"],
        "negative_signals": ["Base rate held with volumes below consensus",
                             "Registered provider governance downgrade",
                             "Land approvals slowing at housebuilders"],
    },
    "themes": [
        {"name": name, "count": count,
         "direction": "rising" if count > 1 else "steady",
         "summary": f"Preview text for {name.lower()}.",
         "article_ids": [k for k, v in ratings.items() if name in v["themes"]]}
        for name, count in sorted(theme_counts.items(), key=lambda kv: -kv[1])
    ],
    "companies": [
        {"name": "Demo Capital Partners", "type": "Investor", "mentions": 3,
         "context": "Forward funding the Salford scheme."},
        {"name": "Demo Homes plc", "type": "Housebuilder", "mentions": 2,
         "context": "Trading update, flat completions."},
        {"name": "Demo Housing Group", "type": "Housing association", "mentions": 2,
         "context": "Governance downgrade."},
        {"name": "Demo Student Living", "type": "Developer", "mentions": 1,
         "context": "410-bed consent."},
        {"name": "Demo Retirement Villages", "type": "Developer", "mentions": 1,
         "context": "Three-site acquisition."},
        {"name": "Bank of England", "type": "Government body", "mentions": 1,
         "context": "Rate hold."},
    ],
    "projects": [
        {"name": "Salford waterside blocks", "location": "Salford, Salford City Council",
         "developers": ["Demo Living"], "homes": "640", "value": "£180m",
         "summary": "Two blocks, forward funded, completion targeted 2029.",
         "article_ids": ["demo01"]},
        {"name": "Campus edge PBSA", "location": "Leeds, Leeds City Council",
         "developers": ["Demo Student Living"], "homes": "410 beds", "value": "",
         "summary": "Consent granted subject to conditions.", "article_ids": ["demo05"]},
    ],
    "policy": [
        {"headline": "Grey belt release consultation opens",
         "kind": "planning",
         "body": "Twelve weeks, covering release tests, viability evidence and "
                 "affordable thresholds on released land. Responses close before "
                 "the next fiscal event, so the direction should be visible by "
                 "the autumn.",
         "article_ids": ["demo02"]},
        {"headline": "Regulator judgement on governance",
         "kind": "regulation",
         "body": "A voluntary undertaking has been agreed. Stock condition data "
                 "quality is the cited weakness, which is the same issue behind "
                 "several recent judgements.",
         "article_ids": ["demo03"]},
    ],
    "investor_view": {
        "opportunities": [
            {"point": "Regional BTR forward funding", "reasoning": "Pricing still clears at scale outside London"},
            {"point": "PBSA in supply-constrained university cities", "reasoning": "Consented pipeline remains thin"},
        ],
        "risks": [
            {"point": "Rate path slipping another quarter", "reasoning": "Exit yields in current models look optimistic"},
            {"point": "Grey belt viability test", "reasoning": "Could strand land bought on release assumptions"},
        ],
        "capital_flows": ["Institutional money into regional rented residential",
                          "Housebuilder land spend slowing"],
        "watch_next": ["Consultation close before the autumn fiscal event",
                       "Next MPC meeting", "Half-year housebuilder reporting"],
    },
    "regions": [
        {"name": "North West", "mentions": 3, "note": "Salford BTR plus an awards shortlist."},
        {"name": "Yorkshire", "mentions": 1, "note": "Leeds PBSA consent."},
        {"name": "West Midlands", "mentions": 1, "note": "Registered provider judgement."},
        {"name": "South West", "mentions": 1, "note": "Later living land."},
        {"name": "London", "mentions": 1, "note": "Appointment only."},
    ],
    "articles": ratings,
    "meta": {"rated": len(ratings), "unrated": 0, "degraded": False,
             "model": "preview (no API call)", "input_tokens": None,
             "output_tokens": None},
}

stamp = datetime.now(config.LONDON).date().isoformat()
for path, payload in ((config.RAW / f"{stamp}.json", raw),
                      (config.ANALYSIS / f"{stamp}.json", analysis)):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path}")
print("\nNow run:  python -m uk_resi.cli build")
