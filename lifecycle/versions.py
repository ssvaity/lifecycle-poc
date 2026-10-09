"""Version handling shared by ranking and extraction.

Lifecycle dates belong to a release line, not a patch: "Python 3.10.22" is
listed as "3.10" on lifecycle pages, so a patch version is widened to its line.
"""

from __future__ import annotations

import re


def version_tokens(query: str) -> list[str]:
    """Version-like parts of the query, most specific first: "3.10.22" → ["3.10.22", "3.10"]."""
    out: list[str] = []
    for t in re.findall(r"[\w.\-]+", query):
        if not any(c.isdigit() for c in t):
            continue
        out.append(t)
        parts = t.split(".")
        if len(parts) >= 3 and all(p.isdigit() for p in parts):
            out.append(".".join(parts[:2]))
    return list(dict.fromkeys(out))


def _version_rx(v: str) -> re.Pattern:
    # Whole version only: "3.1" must not match "3.10", "18" must not match "2018".
    return re.compile(r"(?<![\d.])" + re.escape(v) + r"(?!\d)", re.I)


def has_version(text: str, versions: list[str]) -> bool:
    return any(_version_rx(v).search(text) for v in versions)


def release_line(query: str) -> str:
    """The query with patch versions cut to their release line, for searching."""
    return re.sub(r"\b(\d+\.\d+)(?:\.\d+)+\b", r"\1", query)
