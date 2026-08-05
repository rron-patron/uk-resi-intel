"""Article record plus the normalisation rules that make dedupe reliable."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PREFIXES = ("utm_", "mc_", "pk_", "hsa_", "_hs")
TRACKING_KEYS = {
    "fbclid", "gclid", "igshid", "ref", "source", "cmpid", "campaign",
    "sh", "share", "amp", "at_medium", "at_campaign",
}


def canonical_url(url: str) -> str:
    """Strip tracking noise so the same story from two places collapses to one."""
    if not url:
        return ""
    parts = urlparse(url.strip())
    scheme = "https"
    host = (parts.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]
    path = re.sub(r"/+$", "", parts.path) or "/"
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if k.lower() not in TRACKING_KEYS
        and not any(k.lower().startswith(p) for p in TRACKING_PREFIXES)
    ]
    return urlunparse((scheme, host, path, "", urlencode(sorted(kept)), ""))


def normalise_title(title: str) -> str:
    """Lowercase, strip punctuation and publisher suffixes for fuzzy matching."""
    t = (title or "").lower()
    t = re.sub(r"\s+[-–|]\s+[^-–|]{3,40}$", "", t)  # trailing " - Publisher"
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\b(the|a|an|of|for|to|in|on|and|as|at|by|is|are|its)\b", " ", t)
    return " ".join(t.split())


def title_fingerprint(title: str) -> str:
    return hashlib.sha1(normalise_title(title).encode()).hexdigest()[:16]


@dataclass
class Article:
    source_key: str
    source_name: str
    title: str
    url: str
    published: str | None = None  # ISO 8601, UTC
    excerpt: str = ""
    entities: list[str] = field(default_factory=list)
    kind: str = "news"  # "news" | "data"
    collected_at: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        self.url = canonical_url(self.url)
        self.title = " ".join((self.title or "").split())
        if not self.collected_at:
            self.collected_at = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )
        if not self.id:
            self.id = hashlib.sha1(
                f"{self.source_key}|{self.url}".encode()
            ).hexdigest()[:12]

    @property
    def dedupe_keys(self) -> tuple[str, str]:
        return self.url, f"{self.source_key}:{title_fingerprint(self.title)}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "Article":
        allowed = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in allowed})


def dedupe(articles: list[Article]) -> list[Article]:
    """Collapse duplicates within one run. First occurrence wins."""
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    # A cross-source title match is also a duplicate (wire copy, syndication).
    seen_global_titles: set[str] = set()
    out: list[Article] = []
    for a in articles:
        url_key, title_key = a.dedupe_keys
        global_title = title_fingerprint(a.title)
        if not a.title or not a.url:
            continue
        if url_key in seen_urls or title_key in seen_titles:
            continue
        if global_title in seen_global_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        seen_global_titles.add(global_title)
        out.append(a)
    return out
