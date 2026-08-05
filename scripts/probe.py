"""Test candidate feed or listing URLs one at a time, before editing config.py.

Reports the HTTP status, content type and item count for each URL you give it,
so you can find a working endpoint by trial without touching the source
registry.

    python scripts/probe.py https://example.co.uk/feed/ https://example.co.uk/rss

With --selectors, dumps the classes on a listing page so you can work out a
ScrapeRule:

    python scripts/probe.py --selectors https://example.co.uk/news/
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import feedparser  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from uk_resi import http  # noqa: E402


def probe_feed(url: str) -> None:
    print(f"\n{url}")
    resp = http.get(url)
    if resp is None:
        print("  unreachable — blocked, 404, or robots.txt disallowed")
        print("  (run with -v on the CLI, or check the URL in a browser)")
        return
    ctype = resp.headers.get("Content-Type", "unknown")
    print(f"  HTTP {resp.status_code}  {ctype}  {len(resp.content):,} bytes")

    body = resp.text[:300].lstrip().lower()
    is_feed = "xml" in ctype.lower() or body.startswith("<?xml") or "<rss" in body
    if not is_feed:
        print("  not a feed — looks like HTML")
        soup = BeautifulSoup(resp.text, "lxml")
        links = [
            l.get("href")
            for l in soup.find_all("link", rel=lambda v: v and "alternate" in v)
            if l.get("type") and "xml" in l.get("type")
        ]
        if links:
            print("  but it declares a feed:")
            for l in links:
                print(f"    {l}")
        else:
            print("  and declares no feed — you will need a ScrapeRule")
        return

    parsed = feedparser.parse(resp.content)
    print(f"  parsed {len(parsed.entries)} entries"
          + ("  (malformed but readable)" if parsed.bozo else ""))
    for entry in parsed.entries[:5]:
        print(f"    {entry.get('published', 'no date')[:30]:32} "
              f"{entry.get('title', '')[:70]}")
    if parsed.entries:
        print(f"  sample link: {parsed.entries[0].get('link', 'none')}")


def probe_selectors(url: str) -> None:
    print(f"\n{url}")
    resp = http.get(url)
    if resp is None:
        print("  unreachable")
        return
    soup = BeautifulSoup(resp.text, "lxml")
    print(f"  HTTP {resp.status_code}, {len(resp.text):,} bytes")

    print("\n  Repeated container classes (candidates for ScrapeRule.item):")
    counts: Counter = Counter()
    for tag in soup.find_all(["article", "div", "li"]):
        for cls in tag.get("class", []):
            counts[f"{tag.name}.{cls}"] += 1
    for name, count in counts.most_common(25):
        if count >= 3:
            print(f"    {count:4}  {name}")

    print("\n  Common link path prefixes (candidates for an anchor selector):")
    paths: Counter = Counter()
    for a in soup.find_all("a", href=True):
        parts = [p for p in a["href"].split("/") if p and "." not in p][:2]
        if parts:
            paths["/" + "/".join(parts) + "/"] += 1
    for path, count in paths.most_common(12):
        print(f"    {count:4}  a[href*='{path}']")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--selectors", action="store_true",
                    help="inspect an HTML listing page instead of parsing a feed")
    args = ap.parse_args()
    for url in args.urls:
        if args.selectors:
            probe_selectors(url)
        else:
            probe_feed(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
