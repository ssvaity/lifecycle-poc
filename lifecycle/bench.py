"""Provider benchmark: run every product in bench/products.json through both
providers and score each against reference dates from endoflife.date.

endoflife.date mapping: `support` → end_of_support, `eol` → end_of_life.
Fields the reference doesn't give as a date are not scored.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import httpx

from .compare import same_date
from .lookup import lookup
from .models import FIELDS

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ROOT / "bench" / "products.json"
RESULTS_DIR = ROOT / "bench" / "results"


def reference(product: str, cycle: str) -> dict[str, str | None]:
    r = httpx.get(f"https://endoflife.date/api/{product}/{cycle}.json", timeout=20)
    r.raise_for_status()
    data = r.json()
    as_date = lambda v: v if isinstance(v, str) else None  # noqa: E731 — booleans mean "no date"
    return {"end_of_life": as_date(data.get("eol")), "end_of_support": as_date(data.get("support"))}


def run(limit: int | None = None, on_progress=None) -> dict:
    products = json.loads(PRODUCTS.read_text())[:limit]
    rows = []
    for i, p in enumerate(products, 1):
        if on_progress:
            on_progress(i, len(products), p["query"])
        try:
            ref = reference(p["ref"]["product"], p["ref"]["cycle"])
        except httpx.HTTPError as e:
            ref, ref_error = {f: None for f in FIELDS}, str(e)
        else:
            ref_error = None
        # Scored against endoflife.date, so never answer from it — and never from cache.
        # Every provider runs, so each one gets scored.
        res = lookup(p["query"], free_first=False, use_cache=False, cross_check=True)
        scores = {}
        for name, pr in res.providers.items():
            scores[name] = {
                f: (None if not ref[f] else bool(getattr(pr, f) and same_date(getattr(pr, f), ref[f])))
                for f in FIELDS
            } | {"error": pr.error, "elapsed_s": pr.elapsed_s, "official": bool(pr.source and pr.source.official)}
        rows.append({"query": p["query"], "reference": ref, "reference_error": ref_error,
                     "agreement": res.agreement, "verified": res.verified, "scores": scores,
                     "result": res.to_dict()})

    summary = {}
    for name in ("searchapi", "exa"):
        graded = [r["scores"][name][f] for r in rows for f in FIELDS if r["scores"][name][f] is not None]
        times = [r["scores"][name]["elapsed_s"] for r in rows]
        summary[name] = {
            "accuracy": round(sum(graded) / len(graded), 3) if graded else None,
            "fields_graded": len(graded),
            "errors": sum(1 for r in rows if r["scores"][name]["error"]),
            "official_source_rate": round(sum(r["scores"][name]["official"] for r in rows) / len(rows), 3) if rows else None,
            "avg_seconds": round(sum(times) / len(times), 2) if times else None,
        }
    compared = [a for r in rows for a in r["agreement"].values() if a is not None]
    summary["agreement_rate"] = round(sum(compared) / len(compared), 3) if compared else None

    report = {"ran_at": datetime.now().isoformat(timespec="seconds"), "summary": summary, "rows": rows}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"bench-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(report, indent=2))
    report["saved_to"] = str(out)
    return report
