"""Rank search results by how likely they are to be the official vendor source.

The POC is product-agnostic, so "official" is a heuristic:
  + the product's (or vendor's) name in the domain (python.org for "Python 3.8",
    microsoft.com for "Windows Server 2016") — required to be labelled official
  + lifecycle / docs / release wording in the path and title
  + the version in the title or URL
  - forums, Q&A, issue trackers, blogs, and third-party EOL aggregators
The lookup then tries candidates in this order and keeps the first page that
actually contains lifecycle dates, so a page that only *looks* right is skipped.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import SearchHit, Source
from .versions import has_version, version_tokens

OFFICIAL_THRESHOLD = 4
MAX_CANDIDATES = 5

# Reliable third parties, tried after the vendor's own pages: (host, path prefix).
TRUSTED_SOURCES = (
    ("endoflife.date", "/"),
    ("github.com", "/nodejs/release"),  # nodejs.org renders its dates with JavaScript
)

# Never used: community sites and EOL aggregators (forums are caught by the patterns below).
EXCLUDED_DOMAINS = (
    "reddit.com", "stackoverflow.com", "stackexchange.com", "superuser.com",
    "serverfault.com", "askubuntu.com", "quora.com", "medium.com", "dev.to",
    "youtube.com", "wikipedia.org", "facebook.com", "linkedin.com", "x.com",
    "twitter.com", "blogspot.com", "wordpress.com", "substack.com", "hashnode.dev",
    "endoflife.ai", "endoflife.software", "compathub.com",
    "versio.io", "eol.wiki", "xeol.io", "versionlog.com", "eosl.date",
)
# Third-party EOL trackers tend to put "eol"/"endoflife" in the domain itself.
AGGREGATOR_HOST = re.compile(r"(endoflife|end-of-life|eol)[^.]*\.", re.I)

FORUM_HOST = re.compile(r"^(discuss|forum|forums|community|answers|ask|support-forum)\.", re.I)
FORUM_PATH = re.compile(r"/(t|questions|issues|pull|discussions|forum|forums|thread|threads|comments|topic)/", re.I)

PATH_SIGNALS = (
    "lifecycle", "end-of-life", "end-of-support", "eol", "support", "versions",
    "release", "schedule", "policy", "docs", "documentation",
)
TITLE_SIGNALS = (
    "lifecycle", "end of life", "end-of-life", "end of support", "end-of-support",
    "eol", "support policy", "release schedule", "status of", "retirement",
)
DOTTED_VERSION = re.compile(r"(?<![\d.])\d+\.\d+")
STOP_WORDS = {"lts", "the", "and", "for", "version", "edition", "release", "server", "enterprise", "linux"}

# Products whose vendor domain doesn't contain the product name.
VENDOR_ALIASES = {
    "windows": "microsoft", "office": "microsoft", "sql": "microsoft", "exchange": "microsoft",
    "sharepoint": "microsoft", "azure": "microsoft", "dotnet": "microsoft", "net": "microsoft",
    "rhel": "redhat", "red": "redhat", "java": "oracle", "mysql": "oracle", "node": "nodejs",
    "macos": "apple", "ios": "apple", "esxi": "vmware", "vsphere": "vmware", "asa": "cisco",
    "ios-xe": "cisco", "fortigate": "fortinet", "fortios": "fortinet", "junos": "juniper",
    "django": "djangoproject", "go": "go.dev", "golang": "go.dev", "rails": "rubyonrails",
    "kubernetes": "kubernetes", "k8s": "kubernetes", "sles": "suse", "ubuntu": "ubuntu",
}


def product_tokens(query: str) -> list[str]:
    """Name words of the query ("windows", "server"), not version numbers."""
    words = re.findall(r"[a-z]+", " ".join(t for t in query.lower().split() if not any(c.isdigit() for c in t)))
    return [w for w in words if len(w) >= 3 and w not in STOP_WORDS]


def vendor_tokens(query: str) -> set[str]:
    toks = set(product_tokens(query))
    return toks | {VENDOR_ALIASES[t] for t in toks if t in VENDOR_ALIASES}


def is_vendor_domain(url: str, query: str) -> bool:
    """The product's (or its vendor's) name is a whole part of the domain:
    python.org for Python, but not nodesource.com for Node.js."""
    host = (urlparse(url).hostname or "").lower()
    labels = set(host.split(".")[:-1])  # not the TLD: ".NET" must not match every .net site
    return any(
        tok in labels or ("." in tok and (host == tok or host.endswith("." + tok)))
        for tok in vendor_tokens(query)
    )


def is_trusted(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.lower()
    return any(host == h and path.startswith(p) for h, p in TRUSTED_SOURCES)


def score(hit: SearchHit, query: str = "") -> int:
    parsed = urlparse(hit.url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.lower()
    title = hit.title.lower()

    if not is_trusted(hit.url) and (
        any(host == d or host.endswith("." + d) for d in EXCLUDED_DOMAINS)
        or AGGREGATOR_HOST.match(host)
        or FORUM_HOST.match(host)
        or FORUM_PATH.search(path)
    ):
        return -10

    s = 0
    if host == "github.com" or host.endswith(".github.io"):
        s -= 3
    if "blog" in host or "/blog" in path or host.startswith("news."):
        s -= 2

    if is_vendor_domain(hit.url, query):
        s += 4
    s += min(4, sum(2 for sig in PATH_SIGNALS if sig in path))
    s += min(2, sum(1 for sig in TITLE_SIGNALS if sig in title))
    versions = version_tokens(query)
    if has_version(title, versions) or has_version(path, versions):
        s += 2
    elif any("." in v for v in versions) and DOTTED_VERSION.search(title):
        s -= 3  # the title names a different version ("Python 3.9 …" for 3.10)
    return s


def to_source(hit: SearchHit, query: str) -> Source:
    sc = score(hit, query)
    official = is_vendor_domain(hit.url, query) and sc >= OFFICIAL_THRESHOLD
    return Source(url=hit.url, title=hit.title, official=official,
                  trusted=not official and is_trusted(hit.url), official_score=sc)


def rank(hits: list[SearchHit], query: str, limit: int = MAX_CANDIDATES) -> list[tuple[SearchHit, Source]]:
    """Top candidates: official pages first, then trusted ones, then the rest,
    each by score; excluded sites dropped; ties keep the provider's order."""
    sources = [(to_source(h, query), i, h) for i, h in enumerate(hits)]
    kept = [t for t in sources if t[0].official_score > -10]
    kept.sort(key=lambda t: (0 if t[0].official else 1 if t[0].trusted else 2, -t[0].official_score, t[1]))
    return [(h, src) for src, _, h in kept[:limit]]
