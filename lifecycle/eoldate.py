"""endoflife.date — free API covering hundreds of products. Tried before the
paid search providers; if it knows the product and release, no credits are spent.

Docs: https://endoflife.date/docs/api/v1/
Mapping (same as the benchmark): `eoasFrom` → end_of_support, `eolFrom` → end_of_life.
"""

from __future__ import annotations

import re

import httpx

from . import cache
from .models import ProviderResult, Source, UsageItem
from .versions import version_tokens

NAME = "endoflife.date"
API = "https://endoflife.date/api/v1"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
# Name words that never help pick the product ("Ubuntu 20.04 LTS").
SKIP_WORDS = {"lts", "version", "release", "edition", "the"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


class _Api:
    """GETs through the on-disk cache (catalog data changes slowly); counts real requests."""

    def __init__(self, client: httpx.Client | None):
        self.client = client or httpx.Client(timeout=TIMEOUT)
        self.requests = 0

    def get(self, path: str) -> dict:
        key = f"eol:{path}"
        if hit := cache.get(key, cache.DAY):
            return hit[0]
        self.requests += 1
        r = self.client.get(API + path)
        r.raise_for_status()
        data = r.json()["result"]
        cache.put(key, data)
        return data


def match_product(query: str, products: list[dict]) -> str | None:
    """The product slug for the query's name words, longest match first:
    "Debian 10 Buster" tries "debianbuster", then "debian"."""
    index: dict[str, str] = {}
    for p in products:
        for key in (p["name"], p.get("label") or "", *(p.get("aliases") or [])):
            index.setdefault(_norm(key), p["name"])
    words = [w for w in query.split() if not any(c.isdigit() for c in w) and w.lower() not in SKIP_WORDS]
    for k in range(len(words), 0, -1):
        if slug := index.get(_norm(" ".join(words[:k]))):
            return slug
    return None


def match_release(query: str, releases: list[dict]) -> dict | None:
    """The release named by the query's version, most specific first ("3.10.22" → "3.10")."""
    by_name = {r["name"].lower(): r for r in releases}
    for v in version_tokens(query):
        if r := by_name.get(v.lower().removeprefix("v")):
            return r
    return None


def find(query: str, client: httpx.Client | None = None) -> ProviderResult | None:
    """A full answer from endoflife.date, or None (unknown product or release,
    no dates, or the API is unreachable) so the caller falls back to search."""
    api = _Api(client)
    try:
        slug = match_product(query, api.get("/products"))
        if not slug:
            return None
        product = api.get(f"/products/{slug}")
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    release = match_release(query, product.get("releases") or [])
    if not release or not (release.get("eolFrom") or release.get("eoasFrom")):
        return None

    labels = product.get("labels") or {}
    result = ProviderResult(provider=NAME, end_of_life=release.get("eolFrom"),
                            end_of_support=release.get("eoasFrom"))
    result.source = Source(
        url=(product.get("links") or {}).get("html") or f"https://endoflife.date/{slug}",
        title=f"{product.get('label', slug)} | endoflife.date",
        official=False, official_score=0, trusted=True,
    )
    name = f"{product.get('label', slug)} {release.get('label') or release['name']}"
    for field, key, default in (("end_of_support", "eoasFrom", "Active support"),
                                ("end_of_life", "eolFrom", "Security support")):
        if release.get(key):
            result.quotes[field] = f"{name}: {labels.get(key[:-4]) or default} ends {release[key]}"
    if release.get("eoesFrom"):
        result.notes.append(f"{labels.get('eoes') or 'Extended support'} (usually paid) runs until {release['eoesFrom']}")
    result.notes.append("from endoflife.date, a community-maintained tracker — no paid search was used")
    if api.requests:
        result.usage.append(UsageItem("endoflife.date API", api.requests, "request", 0.0))
    return result
