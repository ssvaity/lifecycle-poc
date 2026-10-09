"""Find and normalise dates in free text. Output is ISO: YYYY-MM-DD, or YYYY-MM when no day is given."""

from __future__ import annotations

import re
from dataclasses import dataclass

MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
            ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
            ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"), ("dec", "december"),
        ],
        start=1,
    )
    for m in names
}
_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
_ORD = r"(?:st|nd|rd|th)?"

PATTERNS = [
    # 2027-01-12
    ("ymd", re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")),
    # 2028-10
    ("ym", re.compile(r"\b(\d{4})-(\d{1,2})\b(?!-\d)")),
    # January 12, 2027 / Jan 12 2027
    ("mdy", re.compile(rf"\b{_MON}\s+(\d{{1,2}}){_ORD},?\s+(\d{{4}})\b", re.I)),
    # 12 January 2027 / 12th Jan, 2027
    ("dmy", re.compile(rf"\b(\d{{1,2}}){_ORD}\s+{_MON},?\s+(\d{{4}})\b", re.I)),
    # 1/12/2027 — read as US month/day/year
    ("us", re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")),
    # January 2027
    ("my", re.compile(rf"\b{_MON}\s+(\d{{4}})\b", re.I)),
]


@dataclass
class FoundDate:
    iso: str
    start: int
    end: int


def _iso(y: int, m: int, d: int | None) -> str | None:
    if not (1990 <= y <= 2100 and 1 <= m <= 12) or (d is not None and not 1 <= d <= 31):
        return None
    return f"{y:04d}-{m:02d}" + (f"-{d:02d}" if d else "")


def find_dates(text: str) -> list[FoundDate]:
    """All dates in `text`, earliest position first; overlapping matches keep the most precise."""
    found: list[FoundDate] = []
    taken: list[tuple[int, int]] = []
    for kind, rx in PATTERNS:  # ordered most → least precise
        for m in rx.finditer(text):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            g = m.groups()
            if kind == "ymd":
                iso = _iso(int(g[0]), int(g[1]), int(g[2]))
            elif kind == "ym":
                iso = _iso(int(g[0]), int(g[1]), None)
            elif kind == "mdy":
                iso = _iso(int(g[2]), MONTHS[g[0].lower().rstrip(".")], int(g[1]))
            elif kind == "dmy":
                iso = _iso(int(g[2]), MONTHS[g[1].lower().rstrip(".")], int(g[0]))
            elif kind == "us":
                iso = _iso(int(g[2]), int(g[0]), int(g[1]))
            else:
                iso = _iso(int(g[1]), MONTHS[g[0].lower().rstrip(".")], None)
            if iso:
                found.append(FoundDate(iso, m.start(), m.end()))
                taken.append((m.start(), m.end()))
    return sorted(found, key=lambda f: f.start)


def normalise(value: str | None) -> str | None:
    """Normalise any single date string to ISO, or None if it isn't one."""
    if not value:
        return None
    dates = find_dates(value.strip())
    return dates[0].iso if dates else None
