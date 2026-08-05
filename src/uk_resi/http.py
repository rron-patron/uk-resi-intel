"""One polite HTTP client for the whole run.

Rules enforced here so no caller can forget them: a real User-Agent, one request
per host at a time with a delay between them, robots.txt honoured, and retries
that back off instead of hammering.
"""

from __future__ import annotations

import logging
import time
import urllib.robotparser as robotparser
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

log = logging.getLogger(__name__)

_last_hit: dict[str, float] = {}
_robots: dict[str, robotparser.RobotFileParser | None] = {}


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": config.USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, "
            "application/xml, text/xml, text/html;q=0.8, */*;q=0.5",
            "Accept-Language": "en-GB,en;q=0.9",
        }
    )
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=8)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


SESSION = _session()


def _throttle(host: str) -> None:
    now = time.monotonic()
    last = _last_hit.get(host)
    if last is not None:
        wait = config.CRAWL_DELAY - (now - last)
        if wait > 0:
            time.sleep(wait)
    _last_hit[host] = time.monotonic()


def allowed(url: str) -> bool:
    """Check robots.txt. A missing or unreadable robots.txt is treated as allow."""
    if not config.RESPECT_ROBOTS:
        return True
    parts = urlparse(url)
    host = f"{parts.scheme}://{parts.netloc}"
    if host not in _robots:
        rp = robotparser.RobotFileParser()
        rp.set_url(f"{host}/robots.txt")
        try:
            resp = SESSION.get(f"{host}/robots.txt", timeout=config.REQUEST_TIMEOUT)
            if resp.status_code >= 400:
                _robots[host] = None
            else:
                rp.parse(resp.text.splitlines())
                _robots[host] = rp
        except requests.RequestException:
            _robots[host] = None
    rp = _robots.get(host)
    if rp is None:
        return True
    return rp.can_fetch(config.USER_AGENT, url)


def get(url: str, *, expect: str | None = None) -> requests.Response | None:
    """Fetch a URL politely. Returns None on any failure — never raises."""
    if not allowed(url):
        log.warning("robots.txt disallows %s — skipping", url)
        return None
    parts = urlparse(url)
    _throttle(parts.netloc)
    try:
        resp = SESSION.get(url, timeout=config.REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        log.warning("fetch failed %s: %s", url, exc)
        return None
    if resp.status_code >= 400:
        log.warning("fetch %s returned HTTP %s", url, resp.status_code)
        return None
    if expect == "feed":
        ctype = resp.headers.get("Content-Type", "").lower()
        body = resp.text[:400].lstrip().lower()
        looks_feed = (
            "xml" in ctype
            or "rss" in ctype
            or body.startswith("<?xml")
            or "<rss" in body
            or "<feed" in body
        )
        if not looks_feed:
            log.info("%s is not a feed (content-type %s)", url, ctype or "unknown")
            return None
    return resp
