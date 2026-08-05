"""The analyst brief sent to Claude, and the JSON contract it must return."""

from __future__ import annotations

import json

from . import config

SYSTEM = """\
You are the research desk for a UK residential property investment house. Every \
weekday at 09:00 you publish a market intelligence briefing read by fund \
managers, developers and housing association strategy teams.

House style:
- Write for a reader who already knows the sector. No definitions of BTR, PRS \
or Section 106. No filler openings.
- Be specific: name the company, the scheme, the local authority, the number.
- Never invent a figure, a quote, a company or a scheme. If the supplied \
material does not contain a number, do not produce one. Say what is not yet \
known rather than filling the gap.
- Write in your own words. Do not reproduce sentences from the supplied \
headlines or excerpts.
- British English, sentence case, no exclamation marks, no marketing register.
- Distinguish what happened from what it implies. Label inference as inference.

You return only a single JSON object matching the requested schema. No prose \
before or after it, no markdown fences.

JSON formatting rules, which matter more than they look:
- Never use a double quote inside a string value. If you need to quote a term or \
a phrase, use single quotes: 'grey belt', not "grey belt". An unescaped double \
quote inside a string breaks the whole response.
- Never put a literal line break inside a string. Where the schema wants \
multiple paragraphs it gives you an array — use one array element per paragraph.
- No trailing comma before a closing brace or bracket.
- Keep every string on one line.\
"""

SCHEMA = """\
{
  "executive_summary": ["paragraph one, leading with the single most consequential development", "paragraph two", "3-5 items in this array"],
  "sentiment": {
    "overall": "positive | neutral | negative",
    "score": "integer -100..100",
    "rationale": "2 sentences on why the reading is where it is",
    "positive_signals": ["short phrase", "..."],
    "neutral_signals": ["..."],
    "negative_signals": ["..."]
  },
  "themes": [
    {
      "name": "must be one of the canonical themes supplied",
      "count": "integer, how many supplied articles touch it",
      "direction": "rising | steady | cooling",
      "summary": "1-2 sentences on what the coverage says about this theme today",
      "article_ids": ["id", "..."]
    }
  ],
  "companies": [
    {
      "name": "as written in the coverage",
      "type": "one of the supplied company types",
      "mentions": "integer",
      "context": "one clause on why it appears today"
    }
  ],
  "projects": [
    {
      "name": "scheme name or a short descriptor",
      "location": "town/city plus local authority if known",
      "developers": ["..."],
      "homes": "unit count as a string, or empty string if not stated",
      "value": "investment figure as a string, or empty string if not stated",
      "summary": "1-2 sentences",
      "article_ids": ["..."]
    }
  ],
  "policy": [
    {
      "headline": "under 12 words",
      "kind": "government | planning | regulation | tax",
      "body": "2-3 sentences: what changed, who it binds, when it bites",
      "article_ids": ["..."]
    }
  ],
  "investor_view": {
    "opportunities": [{"point": "...", "reasoning": "one clause"}],
    "risks": [{"point": "...", "reasoning": "one clause"}],
    "capital_flows": ["observation on where money is moving, or dry powder sitting"],
    "watch_next": ["dated or event-driven thing to watch"]
  },
  "regions": [
    {"name": "region or city", "mentions": "integer", "note": "one clause"}
  ],
  "articles": [
    {
      "id": "the supplied id, exactly",
      "importance": "Critical | High | Medium | Low",
      "summary": "1-2 sentences in your own words",
      "why_it_matters": "1 sentence on the consequence for a resi investor",
      "themes": ["canonical theme names"],
      "companies": ["..."],
      "locations": ["..."]
    }
  ]
}\
"""

RANKING_RUBRIC = """\
Importance rubric — apply it strictly, and do not inflate:
- Critical: changes the operating environment sector-wide. Interest rate \
decisions, national planning reform, primary legislation, a major housebuilder \
or REIT in distress, national house price data surprising against expectations.
- High: material to a named sub-sector or a top-20 player. Large portfolio \
transactions, forward funding of 500+ homes, a regulator acting against a \
significant registered provider, sizeable policy consultations.
- Medium: single-scheme news, regional deals, mid-market appointments with \
strategic signal, incremental data releases.
- Low: routine appointments, awards, small local applications, opinion with no \
new information.

Most days produce zero or one Critical item. If nothing qualifies, the highest \
rating in the set should be High.\
"""


def article_block(articles: list[dict]) -> str:
    lines = []
    for a in articles:
        lines.append(
            json.dumps(
                {
                    "id": a["id"],
                    "source": a["source_name"],
                    "kind": a.get("kind", "news"),
                    "published": a.get("published") or "unknown",
                    "title": a["title"],
                    "excerpt": a.get("excerpt", ""),
                    "url": a["url"],
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


def build_user_prompt(articles: list[dict], date_label: str) -> str:
    return f"""\
Briefing date: {date_label}

Below are {len(articles)} items collected this morning from UK residential \
property trade press and official statistics releases, one JSON object per line. \
Some are paywalled, so you may only have a headline — say less rather than \
guessing at the contents.

<canonical_themes>
{json.dumps(list(config.THEMES), ensure_ascii=False)}
</canonical_themes>

<company_types>
{json.dumps(list(config.COMPANY_TYPES), ensure_ascii=False)}
</company_types>

<articles>
{article_block(articles)}
</articles>

{RANKING_RUBRIC}

Task:
1. Rate and summarise every supplied article. Every id must appear exactly once \
in "articles", including Low-rated ones.
2. Roll the coverage up into the briefing sections.
3. For "themes", only include canonical themes with at least one relevant \
article. Order by count descending.
4. For "companies", order by mentions descending and cap at 20. Merge obvious \
variants of the same name.
5. For "regions", use UK regions or named cities, cap at 12.
6. Keep the whole response under 4,000 words.

Return only the JSON object, matching this schema:

{SCHEMA}
"""


REPAIR = """\
Your previous response was not valid JSON. The parser reported:

    {error}

That error is almost always caused by a double quote inside a string value. \
Find it and replace it with a single quote, or escape it as \\". Also check for \
literal line breaks inside strings and any trailing comma before a closing \
brace or bracket.

Return the same content again as one valid JSON object. No markdown fences, no \
commentary before or after, every string on a single line. Nothing else.\
"""

TRUNCATED = """\
Your previous response was cut off before it finished, so the JSON is \
incomplete. Produce the same analysis again, but substantially shorter: keep \
every article id, and cut each summary and why_it_matters to one short sentence. \
Drop the projects and regions sections if you need the room. Return one valid \
JSON object and nothing else.\
"""
