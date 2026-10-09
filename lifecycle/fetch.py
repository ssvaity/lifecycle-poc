"""Fetch a page and reduce it to its main text (tables kept — lifecycle dates live there)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
import trafilatura

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; lifecycle-poc/0.1)"}

# Microsoft puts dates in <local-time> elements, which text extraction drops.
# Their datetime is UTC; the page shows it in the element's timezone (Pacific).
LOCAL_TIME = re.compile(r"<local-time\b([^>]*)>(.*?)</local-time>", re.S | re.I)
ATTR = re.compile(r'([\w-]+)="([^"]*)"')
# Search often returns a translated copy (…/de-de/…) the extractor can't read.
LOCALE_PATH = re.compile(r"^/([a-z]{2}-[a-z]{2})(?=/)", re.I)


class FetchError(RuntimeError):
    pass


def _local_date(m: re.Match) -> str:
    attrs = dict(ATTR.findall(m.group(1)))
    try:
        raw = attrs["datetime"]
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            dt = datetime.strptime(raw, "%m/%d/%Y %I:%M:%S %p")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo(attrs.get("timezone", "UTC"))).date().isoformat()
    except (KeyError, ValueError, ZoneInfoNotFoundError):
        return m.group(2)


def english_urls(url: str) -> list[str]:
    """English copies to try for a page with a non-English locale path."""
    p = urlparse(url)
    m = LOCALE_PATH.match(p.path)
    if not m or m.group(1).lower().startswith("en-"):
        return []
    rest = p.path[m.end():]
    return [urlunparse(p._replace(path=f"/{loc}{rest}")) for loc in ("en-us", "en")]


def fetch_page(url: str) -> tuple[str, str]:
    """(text, url actually read): an English copy if there is one, else the page itself."""
    for en in english_urls(url):
        try:
            return fetch_text(en), en
        except FetchError:
            pass
    return fetch_text(url), url


def html_to_text(html: str) -> str | None:
    html = LOCAL_TIME.sub(_local_date, html)
    return trafilatura.extract(html, include_tables=True, include_comments=False, favor_recall=True)


def fetch_text(url: str, client: httpx.Client | None = None) -> str:
    client = client or httpx.Client(timeout=30.0, follow_redirects=True, headers=HEADERS)
    try:
        r = client.get(url)
    except httpx.HTTPError as e:
        raise FetchError(f"could not fetch {url}: {e}") from e
    if r.status_code != 200:
        raise FetchError(f"{url} returned HTTP {r.status_code}")
    text = html_to_text(r.text)
    if not text:
        raise FetchError(f"no readable text at {url} (page may need JavaScript)")
    return text
