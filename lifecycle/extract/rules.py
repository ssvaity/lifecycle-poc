"""Rule-based extractor: keyword + nearest-date matching, with table awareness.

Free, fast and transparent, but can miss unusual page layouts. Every date
returned comes with the line it was found on, so a wrong match is easy to spot.
"""

from __future__ import annotations

import re

from ..models import Extraction
from ..versions import has_version, version_tokens
from .dates import find_dates

KEYWORDS = {
    "end_of_life": (
        "end of life", "end-of-life", "eol", "extended end", "extended support",
        "end of extended support", "security support", "end of security", "end of all support",
        "retired", "retirement",
    ),
    "end_of_support": (
        "end of support", "end-of-support", "mainstream end", "mainstream support",
        "end of mainstream", "standard support", "end of standard", "active support",
        "general support", "end of maintenance", "eos",
    ),
}
WINDOW = 220  # chars after a keyword in which a date counts as belonging to it


def _kw_rx(words: tuple[str, ...]) -> re.Pattern:
    # No closing \b: headers carry footnote digits ("End of extended support2").
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")(?![a-z])", re.I)


KW_RX = {f: _kw_rx(words) for f, words in KEYWORDS.items()}


def _cells(line: str) -> list[str] | None:
    if line.count("|") < 2:
        return None
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _from_tables(lines: list[str], versions: list[str]) -> dict[str, tuple[str, str, int]]:
    """Header row naming the fields → value in that column of the row matching the version."""
    out: dict[str, tuple[str, str, int]] = {}
    for i, line in enumerate(lines):
        header = _cells(line)
        if not header:
            continue
        cols = {
            f: j
            for f in KW_RX
            for j, cell in enumerate(header)
            if KW_RX[f].search(cell) and not find_dates(cell)
        }
        if not cols:
            continue
        for row_line in lines[i + 1 : i + 40]:
            row = _cells(row_line)
            if not row:
                if row_line.strip():
                    break
                continue
            # Version only in the row label: other cells can list unrelated versions.
            hit = has_version(row[0], versions) if versions else True
            for f, j in cols.items():
                if j < len(row) and (d := find_dates(row[j])):
                    rank = 2 if hit else 0
                    if f not in out or rank > out[f][2]:
                        out[f] = (d[0].iso, f"{line.strip()} / {row_line.strip()}", rank)
    return out


def extract(query: str, text: str) -> Extraction:
    lines = text.splitlines()
    versions = version_tokens(query)
    best: dict[str, tuple[str, str, int]] = _from_tables(lines, versions)

    for line in lines:
        cells = _cells(line)
        on_version = has_version(cells[0] if cells else line, versions)
        # In a table row, a keyword only owns a date in its own cell.
        for segment in cells or [line]:
            for f, rx in KW_RX.items():
                for kw in rx.finditer(segment):
                    after = [d for d in find_dates(segment) if 0 <= d.start - kw.end() <= WINDOW]
                    if not after:
                        continue
                    rank = 1 + (1 if on_version else 0)
                    if f not in best or rank > best[f][2]:
                        best[f] = (after[0].iso, line.strip()[:400], rank)

    ex = Extraction(version_matched=bool(best) and (not versions or any(r == 2 for _, _, r in best.values())))
    for f, (iso, quote, _) in best.items():
        setattr(ex, f, iso)
        ex.quotes[f] = quote
    if not best:
        ex.notes.append("no lifecycle dates matched on this page")
    return ex
