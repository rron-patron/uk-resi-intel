"""Write the placeholder edition that ships with the repo.

Its job is to make GitHub Pages render something coherent between "repo created"
and "first successful 09:00 run". It deliberately contains no invented
headlines: every card explains what will replace it.

    python scripts/make_seed.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from uk_resi import config  # noqa: E402

PLACEHOLDERS = [
    (
        "Critical",
        "Rate decisions, planning reform and national house price data land here",
        "Reserved for developments that move the whole sector: Monetary Policy "
        "Committee decisions, primary legislation, national statistics that "
        "surprise against expectations.",
        "Most days carry no Critical item. When one appears, it is the reason to "
        "read the briefing before your inbox.",
    ),
    (
        "High",
        "Portfolio transactions and sub-sector policy appear at this level",
        "Large deals, forward funding of 500 homes or more, regulator action "
        "against a significant registered provider, substantial consultations.",
        "This is the band that usually sets the working agenda for the day.",
    ),
    (
        "Medium",
        "Single schemes, regional deals and incremental data",
        "Individual planning consents, mid-market appointments with strategic "
        "signal, monthly index updates that land in line with expectations.",
        "Useful context rather than a call to act.",
    ),
    (
        "Low",
        "Appointments, awards and comment with no new information",
        "Kept in the record so the day's coverage is complete, and filtered out "
        "with the chips above when you want signal only.",
        "",
    ),
]

now = datetime.now(config.LONDON)

stories = []
for n, (band, title, summary, why) in enumerate(PLACEHOLDERS):
    stories.append(
        {
            "id": f"seed{n}",
            "title": title,
            "source": "Placeholder",
            "source_key": "seed",
            "url": "https://github.com/rron-patron/uk-resi-intel#readme",
            "published": now.isoformat(timespec="seconds"),
            "kind": "news",
            "excerpt": "",
            "importance": band,
            "summary": summary,
            "why_it_matters": why,
            "themes": [],
            "companies": [],
            "locations": [],
        }
    )

dashboard = {
    "schema": 1,
    "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "generated_at_london": now.isoformat(timespec="minutes"),
    "date_label": "Sample edition",
    "time_label": "not yet published",
    "executive_summary": (
        "This is a placeholder. No sources have been collected and no analysis "
        "has run yet, so nothing on this page is real market information.\n\n"
        "Once you add an ANTHROPIC_API_KEY secret and the daily workflow "
        "completes, this panel carries the morning note: three to five "
        "paragraphs on what actually moved in UK residential, written from the "
        "headlines and data releases collected at 09:00 London time.\n\n"
        "To publish immediately rather than waiting for tomorrow, open the "
        "Actions tab, choose \"Daily briefing\", and click Run workflow."
    ),
    "sentiment": {
        "overall": "neutral",
        "score": 0,
        "rationale": "No reading until the first edition runs.",
        "positive_signals": [],
        "neutral_signals": ["Awaiting first collection"],
        "negative_signals": [],
    },
    "themes": [
        {"name": name, "count": 0, "direction": "steady",
         "summary": "Counts and commentary appear after the first run.",
         "article_ids": []}
        for name in config.THEMES[:4]
    ],
    "companies": [],
    "projects": [],
    "policy": [],
    "investor_view": {
        "opportunities": [],
        "risks": [],
        "capital_flows": [],
        "watch_next": [],
    },
    "regions": [],
    "stories": stories,
    "stats": {
        "stories": len(stories),
        "critical": 1, "high": 1, "medium": 1, "low": 1,
        "sources_live": 0,
        "sources_total": len(config.SOURCES),
        "by_source": [{"name": "Placeholder", "count": len(stories)}],
    },
    "sources": [
        {"key": s.key, "name": s.name, "homepage": s.homepage, "kind": s.kind}
        for s in config.SOURCES
    ],
    "source_health": [
        {"source": s.key, "name": s.name, "route": "not yet run", "url": s.homepage,
         "found": 0, "attempts": []}
        for s in config.SOURCES
    ],
    "meta": {
        "rated": 0,
        "unrated": 0,
        "degraded": False,
        "sample": True,
        "model": None,
    },
}

out = config.DOCS_DATA / "dashboard.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n")
print(f"wrote {out}")
