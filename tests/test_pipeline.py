"""Offline tests. No network, no API key needed.

Feed parsing is tested against a fixture so the suite stays green when a
publisher changes their site.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from uk_resi import analyse, build, config, feeds
from uk_resi.models import Article, canonical_url, dedupe, normalise_title

FIXTURES = Path(__file__).parent / "fixtures"


# ------------------------------------------------------------- URL handling


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.example.co.uk/news/story/", "https://example.co.uk/news/story"),
        ("http://example.co.uk/a?utm_source=x&id=7", "https://example.co.uk/a?id=7"),
        ("https://m.example.co.uk/a#top", "https://example.co.uk/a"),
        ("https://example.co.uk/a?b=2&a=1", "https://example.co.uk/a?a=1&b=2"),
    ],
)
def test_canonical_url(raw, expected):
    assert canonical_url(raw) == expected


def test_normalise_title_drops_publisher_suffix():
    a = normalise_title("Barratt agrees 500-home deal in Leeds - Property Week")
    b = normalise_title("Barratt agrees 500 home deal in Leeds")
    assert a == b


# ------------------------------------------------------------------ dedupe


def article(**kw) -> Article:
    base = dict(
        source_key="src",
        source_name="Src",
        title="Vistry forward funds 320 affordable homes in Salford",
        url="https://example.co.uk/story-1",
    )
    base.update(kw)
    return Article(**base)


def test_dedupe_collapses_tracking_variants():
    items = [
        article(url="https://example.co.uk/story-1"),
        article(url="https://www.example.co.uk/story-1/?utm_campaign=daily"),
    ]
    assert len(dedupe(items)) == 1


def test_dedupe_collapses_same_story_across_sources():
    items = [
        article(source_key="a", source_name="A", url="https://a.co.uk/x"),
        article(source_key="b", source_name="B", url="https://b.co.uk/y"),
    ]
    assert len(dedupe(items)) == 1


def test_dedupe_keeps_distinct_stories():
    items = [
        article(url="https://example.co.uk/1"),
        article(title="Bank of England holds base rate", url="https://example.co.uk/2"),
    ]
    assert len(dedupe(items)) == 2


def test_article_id_is_stable():
    assert article().id == article().id


# ------------------------------------------------------------ feed parsing


def test_read_feed_parses_fixture(monkeypatch):
    body = (FIXTURES / "sample_feed.xml").read_bytes()

    class FakeResponse:
        content = body
        text = body.decode()
        headers = {"Content-Type": "application/rss+xml"}
        status_code = 200

    monkeypatch.setattr(feeds.http, "get", lambda url, expect=None: FakeResponse())
    monkeypatch.setattr(feeds, "is_recent", lambda iso, hours=48: True)

    source = config.SOURCES_BY_KEY["landlordzone"]
    items = feeds.read_feed(source, "https://example.invalid/feed")

    titles = [i.title for i in items]
    assert "Renters' Rights Act: what landlords must do before October" in titles
    assert all(i.source_key == "landlordzone" for i in items)
    assert all(len(i.excerpt) <= config.EXCERPT_CHARS + 1 for i in items)
    first = items[0]
    assert first.published and first.published.endswith("+00:00")


def test_keyword_filter_drops_non_residential():
    mixed = config.SOURCES_BY_KEY["bisnow_uk"]
    resi = config.SOURCES_BY_KEY["inside_housing"]
    assert not feeds.relevant(mixed, "Logistics shed letting in Milton Keynes")
    assert feeds.relevant(mixed, "Build-to-rent scheme approved in Manchester")
    assert feeds.relevant(resi, "Anything at all")


def test_strip_html():
    assert feeds.strip_html("<p>Hello <b>world</b></p>") == "Hello world"


# ------------------------------------------------------- analysis validation


def sample_analysis(ids):
    return {
        "executive_summary": "Para one.\n\nPara two.",
        "sentiment": {
            "overall": "NEGATIVE",
            "score": "-350",
            "rationale": "Rates and supply.",
            "positive_signals": ["BTR funding open"],
            "neutral_signals": [],
            "negative_signals": ["Approvals slowing"],
        },
        "themes": [
            {"name": "Planning policy", "count": "4", "direction": "RISING",
             "summary": "Reform detail lands.", "article_ids": list(ids) + ["ghost"]},
            {"name": "Not A Real Theme", "count": 9, "direction": "rising",
             "summary": "", "article_ids": []},
        ],
        "companies": [{"name": "Vistry", "type": "Housebuilder", "mentions": 3, "context": "Forward funding."}],
        "projects": [{"name": "Salford Rise", "location": "Salford", "developers": ["Vistry"],
                      "homes": "320", "value": "", "summary": "Approved.", "article_ids": list(ids)}],
        "policy": [{"headline": "NPPF consultation opens", "kind": "planning",
                    "body": "Consults on grey belt.", "article_ids": list(ids)}],
        "investor_view": {
            "opportunities": [{"point": "Forward funding", "reasoning": "Margins widen"}],
            "risks": ["Build cost inflation"],
            "capital_flows": ["Overseas capital into PBSA"],
            "watch_next": ["MPC decision"],
        },
        "regions": [{"name": "North West", "mentions": "5", "note": "Salford leads."}],
        "articles": [
            {"id": i, "importance": "critical" if n == 0 else "nonsense",
             "summary": "S.", "why_it_matters": "W.",
             "themes": ["Planning policy", "Fake"], "companies": ["Vistry"], "locations": ["Salford"]}
            for n, i in enumerate(ids)
        ] + [{"id": "ghost", "importance": "Critical", "summary": "x", "why_it_matters": "y"}],
    }


def test_validate_coerces_and_filters():
    ids = {"aaa", "bbb"}
    out = analyse.validate(sample_analysis(ids), ids)

    assert out["sentiment"]["overall"] == "negative"
    assert out["sentiment"]["score"] == -100  # clamped
    # Unknown themes are dropped so the dashboard axis stays stable.
    assert [t["name"] for t in out["themes"]] == ["Planning policy"]
    assert out["themes"][0]["direction"] == "rising"
    assert out["themes"][0]["article_ids"] == sorted(ids) or set(out["themes"][0]["article_ids"]) == ids
    # Ratings for ids we never sent are discarded.
    assert set(out["articles"]) == ids
    importances = {a["importance"] for a in out["articles"].values()}
    assert importances <= set(config.IMPORTANCE_ORDER)
    assert "Fake" not in out["articles"]["aaa"]["themes"]
    # Bare-string risks get normalised into the point/reasoning shape.
    assert out["investor_view"]["risks"][0] == {"point": "Build cost inflation", "reasoning": ""}


def test_validate_rejects_missing_sections():
    with pytest.raises(analyse.AnalysisError):
        analyse.validate({"executive_summary": "x"}, {"aaa"})


def test_validate_rejects_all_unknown_ids():
    with pytest.raises(analyse.AnalysisError):
        analyse.validate(sample_analysis({"zzz"}), {"aaa"})


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        'Here you go:\n{"a": 1}\nHope that helps.',
    ],
)
def test_extract_json_survives_wrappers(text):
    assert analyse.extract_json(text) == {"a": 1}


def test_extract_json_raises_without_object():
    with pytest.raises(ValueError):
        analyse.extract_json("no json here")


def test_fallback_analysis_is_labelled_degraded():
    articles = [
        {"id": "aaa", "title": "Build-to-rent scheme funded in Leeds",
         "excerpt": "A 300-home BTR block.", "entities": ["Grainger"],
         "source_name": "X", "url": "https://x.co.uk/a"}
    ]
    out = analyse.fallback_analysis(articles, "Monday", "no API key")
    assert out["meta"]["degraded"] is True
    assert "no API key" in out["executive_summary"]
    assert any(t["name"] == "Build-to-rent" for t in out["themes"])


# ------------------------------------------------------------------- build


def test_build_dashboard_orders_and_counts():
    raw = {
        "counts": {"sources_live": 7, "sources_total": 9},
        "source_health": [],
        "articles": [
            {"id": "low1", "source_key": "s", "source_name": "S", "title": "Minor",
             "url": "https://x.co.uk/1", "published": "2026-08-04T07:00:00+00:00", "excerpt": ""},
            {"id": "crit", "source_key": "s", "source_name": "S", "title": "Rate decision",
             "url": "https://x.co.uk/2", "published": "2026-08-03T07:00:00+00:00", "excerpt": ""},
            {"id": "high", "source_key": "t", "source_name": "T", "title": "Portfolio deal",
             "url": "https://x.co.uk/3", "published": "2026-08-04T09:00:00+00:00", "excerpt": ""},
        ],
    }
    analysis = {
        "executive_summary": "Note.",
        "articles": {
            "low1": {"importance": "Low", "summary": "", "why_it_matters": ""},
            "crit": {"importance": "Critical", "summary": "", "why_it_matters": ""},
            "high": {"importance": "High", "summary": "", "why_it_matters": ""},
        },
        "meta": {"model": "claude-sonnet-5"},
    }
    dash = build.build_dashboard(raw, analysis)

    assert [s["id"] for s in dash["stories"]] == ["crit", "high", "low1"]
    assert dash["stats"]["critical"] == 1
    assert dash["stats"]["stories"] == 3
    assert dash["stats"]["sources_live"] == 7
    assert dash["schema"] == 1
    # Everything the frontend reads must be present.
    for key in ("executive_summary", "sentiment", "themes", "companies",
                "projects", "policy", "investor_view", "regions", "stories",
                "stats", "sources"):
        assert key in dash


def test_seed_dashboard_matches_expected_shape():
    seed = json.loads(Path("docs/data/dashboard.json").read_text())
    assert seed["schema"] == 1
    for key in ("stories", "stats", "sentiment", "themes", "sources"):
        assert key in seed


def test_excerpt_truncates_politely():
    long = "word " * 400
    out = config.excerpt(long, 100)
    assert len(out) <= 101
    assert out.endswith("…")
