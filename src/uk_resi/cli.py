"""Command line entrypoints.

    python -m uk_resi.cli verify      # which sources currently resolve
    python -m uk_resi.cli collect     # scrape only
    python -m uk_resi.cli analyse     # AI pass over today's collection
    python -m uk_resi.cli build       # rebuild dashboard.json from stored files
    python -m uk_resi.cli run         # collect -> analyse -> build
    python -m uk_resi.cli gate        # exit 0 if today's edition is still due
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime

from . import analyse as analyse_mod
from . import build as build_mod
from . import collect as collect_mod
from . import config, feeds

log = logging.getLogger("uk_resi")


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ------------------------------------------------------------------ commands


def cmd_verify(args) -> int:
    """Probe every source and report the route that works."""
    resolved = collect_mod.load_json(config.RESOLVED_FEEDS, {})
    rows, failures = [], []
    for source in config.SOURCES:
        report = feeds.fetch_source(source, resolved)
        rows.append(report)
        if report["route"] in {"feed", "discovered"}:
            resolved[source.key] = report["url"]
        if not report["articles"]:
            failures.append(source.key)
        print(f"\n{source.name}  [{source.key}]")
        print(f"  route : {report['route']}")
        print(f"  url   : {report['url']}")
        print(f"  items : {len(report['articles'])}")
        for attempt in report["attempts"]:
            print(f"    · {attempt}")
        for article in report["articles"][:2]:
            print(f"    → {article.title[:88]}")
    collect_mod.save_json(config.RESOLVED_FEEDS, resolved)

    live = len(config.SOURCES) - len(failures)
    print(f"\n{live}/{len(config.SOURCES)} sources returned items.")
    if failures:
        print("No items from: " + ", ".join(failures))
        print(
            "Fix by editing SOURCES in src/uk_resi/config.py — add the correct "
            "feed URL, or update the ScrapeRule selectors."
        )
    if args.strict and failures:
        return 1
    return 0


def cmd_collect(args) -> int:
    payload = collect_mod.collect(force=args.force)
    counts = payload["counts"]
    log.info(
        "collected %d new item(s) from %d/%d live source(s)",
        counts["new"],
        counts["sources_live"],
        counts["sources_total"],
    )
    return 0


def cmd_analyse(args) -> int:
    stamp = datetime.now(config.LONDON).date().isoformat()
    raw = collect_mod.load_json(config.RAW / f"{stamp}.json", None)
    if raw is None:
        log.error("no collection for %s — run `collect` first", stamp)
        return 1

    articles = raw.get("articles", [])
    if len(articles) < args.min_articles:
        pooled = collect_mod.recent_articles(days=3)
        log.info(
            "only %d new item(s); pooling the last 3 days -> %d item(s)",
            len(articles),
            len(pooled),
        )
        articles = pooled
        raw["pooled_articles"] = pooled
        collect_mod.save_json(config.RAW / f"{stamp}.json", raw)

    date_label = datetime.now(config.LONDON).strftime("%A %d %B %Y")
    if args.offline:
        analysis = analyse_mod.fallback_analysis(
            articles, date_label, "run with --offline"
        )
    else:
        try:
            analysis = analyse_mod.analyse(articles, date_label)
        except analyse_mod.AnalysisError as exc:
            if args.strict:
                log.error("analysis failed: %s", exc)
                return 1
            log.error("analysis failed (%s) — publishing a degraded edition", exc)
            analysis = analyse_mod.fallback_analysis(articles, date_label, str(exc))

    collect_mod.save_json(config.ANALYSIS / f"{stamp}.json", analysis)
    usage = analysis.get("meta", {})
    log.info(
        "analysis stored: %s rated, model=%s in=%s out=%s",
        usage.get("rated"),
        usage.get("model"),
        usage.get("input_tokens"),
        usage.get("output_tokens"),
    )
    return 0


def cmd_build(args) -> int:
    stamp = args.date or datetime.now(config.LONDON).date().isoformat()
    raw = collect_mod.load_json(config.RAW / f"{stamp}.json", None)
    analysis = collect_mod.load_json(config.ANALYSIS / f"{stamp}.json", None)
    if raw is None or analysis is None:
        log.error("missing raw or analysis file for %s", stamp)
        return 1
    dashboard = build_mod.build_dashboard(raw, analysis)
    build_mod.write_dashboard(dashboard)
    return 0


def cmd_run(args) -> int:
    for step in (cmd_collect, cmd_analyse, cmd_build):
        code = step(args)
        if code != 0:
            return code
    return 0


def cmd_gate(args) -> int:
    """Exit 0 if today's edition should run now, 1 if it should be skipped.

    Handles both British Summer Time and GMT without touching the cron
    expression, and tolerates GitHub's scheduler running late:

      * run only once London local time has reached the publish hour
      * run only if today's edition has not already been produced
    """
    now = datetime.now(config.LONDON)
    stamp = now.date().isoformat()
    already = (config.ANALYSIS / f"{stamp}.json").exists()
    print(f"london_time={now.isoformat(timespec='minutes')}")
    print(f"already_published={str(already).lower()}")

    if args.force:
        print("decision=run (forced)")
        return 0
    if already:
        print("decision=skip (today's edition already exists)")
        return 1
    if now.hour < args.hour:
        print(f"decision=skip (before {args.hour:02d}:00 London)")
        return 1
    print("decision=run")
    return 0


def cmd_health(args) -> int:
    stamp = datetime.now(config.LONDON).date().isoformat()
    raw = collect_mod.load_json(config.RAW / f"{stamp}.json", {})
    print(json.dumps(raw.get("source_health", []), indent=2))
    return 0


# --------------------------------------------------------------------- parser


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uk_resi", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("verify", help="probe all sources")
    p.add_argument("--strict", action="store_true", help="non-zero exit on any dead source")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("collect", help="scrape sources")
    p.add_argument("--force", action="store_true", help="ignore the seen ledger")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("analyse", help="run the Claude analysis")
    p.add_argument("--offline", action="store_true", help="skip the API entirely")
    p.add_argument("--strict", action="store_true", help="fail instead of degrading")
    p.add_argument("--min-articles", type=int, default=8)
    p.set_defaults(func=cmd_analyse)

    p = sub.add_parser("build", help="write docs/data/dashboard.json")
    p.add_argument("--date", help="YYYY-MM-DD (defaults to today, London)")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("run", help="collect, analyse and build")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--min-articles", type=int, default=8)
    p.add_argument("--date", default=None)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("gate", help="decide whether to publish now")
    p.add_argument("--hour", type=int, default=9, help="publish hour, London time")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("health", help="print today's source health report")
    p.set_defaults(func=cmd_health)

    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
