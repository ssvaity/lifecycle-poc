"""Compare two providers' answers and decide the final dates."""

from __future__ import annotations

from .models import FIELDS, ProviderResult


def same_date(a: str, b: str) -> bool:
    """Equal, or equal at the coarser precision ("2027-01" matches "2027-01-12")."""
    return a.startswith(b) or b.startswith(a)


def compare(results: dict[str, ProviderResult]) -> tuple[dict[str, str | None], dict[str, bool | None], bool]:
    """Returns (final dates, per-field agreement, verified).

    agreement[field]: True/False when at least two providers found a date,
    None when fewer did. A final date is set when providers agree (the more
    precise value wins) or when only one provider found it; disagreements
    leave it None. `verified` means every date found was confirmed by both.
    """
    final: dict[str, str | None] = {}
    agreement: dict[str, bool | None] = {}
    for f in FIELDS:
        values = [v for r in results.values() if (v := getattr(r, f))]
        if len(values) >= 2:
            agree = all(same_date(values[0], v) for v in values[1:])
            agreement[f] = agree
            final[f] = max(values, key=len) if agree else None
        else:
            agreement[f] = None
            final[f] = values[0] if values else None

    found = [f for f in FIELDS if any(getattr(r, f) for r in results.values())]
    verified = bool(found) and all(agreement[f] is True for f in found)
    return final, agreement, verified
