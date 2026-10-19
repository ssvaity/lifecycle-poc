"""End-to-end lookup: search → one official source per provider → extract → compare."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import cache
from .compare import compare
from .eoldate import find as find_eol
from .extract import extract
from .fetch import FetchError, fetch_page
from .models import LookupResult, ProviderResult, UsageItem
from .official import MAX_CANDIDATES, rank
from .providers import PROVIDERS
from .providers.base import ProviderError
from .versions import release_line

CACHE_DAYS = 7


def run_provider(name: str, query: str, pages: int = MAX_CANDIDATES) -> ProviderResult:
    """Search, then try the top-ranked candidates in order and keep the first
    page with lifecycle dates for the queried version — one source per provider.
    At most `pages` results are read.
    Dates from a page that doesn't tie them to the version (often another
    version's dates) are never returned: no answer beats a wrong one."""
    result = ProviderResult(provider=name)
    started = time.perf_counter()
    provider, fetched = None, 0
    try:
        provider = PROVIDERS[name]()
        # A few extra so excluded sites (forums, aggregators) still leave `pages` to read.
        provider.num_results = pages + 2
        candidates = rank(provider.search(query), query, limit=pages)
        if not candidates:
            result.error = "no usable search results"
            return result

        readable = None
        for hit, source in candidates:
            try:
                text = hit.text
                if text is None:
                    fetched += 1
                    text, source.url = fetch_page(hit.url)
            except FetchError as e:
                result.notes.append(f"skipped {hit.url}: {e}")
                continue
            ex = extract(query, text)
            if ex.version_matched:
                _apply(result, source, ex)
                break
            if ex.end_of_life or ex.end_of_support:
                result.notes.append(f"dates on {hit.url} don't mention the queried version; ignored them")
            else:
                result.notes.append(f"no dates on {hit.url}; tried next result")
            readable = readable or source
        else:
            if readable is None:
                result.error = "none of the top results could be read"
                return result
            result.source = readable
            result.notes.append("no result gave dates for this version")

        if result.source.trusted:
            result.notes.append("source is a trusted third-party tracker, not the vendor's own site")
        elif not result.source.official:
            result.notes.append("source may not be official; check the link")
    except ProviderError as e:
        result.error = str(e)
    finally:
        result.usage = list(getattr(provider, "usage", []))
        if fetched:
            result.usage.append(UsageItem("Page fetch", fetched, "page", 0.0))
        result.elapsed_s = round(time.perf_counter() - started, 2)
    return result


def _apply(result: ProviderResult, source, ex) -> None:
    result.source = source
    result.end_of_life, result.end_of_support = ex.end_of_life, ex.end_of_support
    result.quotes = ex.quotes
    result.notes += ex.notes


def cache_key(query: str, providers: tuple[str, ...], pages: int, free_first: bool, cross_check: bool) -> str:
    """Same key for "Python 3.10.22" and "python 3.10" — they search the same way."""
    q = " ".join(release_line(query).lower().split())
    return (f"lookup:{q}|{','.join(providers)}|{pages}|{'eol' if free_first else 'search'}"
            f"|{'cross' if cross_check else 'first'}")


def good_enough(r: ProviderResult) -> bool:
    """A date from the vendor's own page (or a trusted tracker): no need to pay for a second opinion."""
    return (not r.error and bool(r.end_of_life or r.end_of_support)
            and r.source is not None and (r.source.official or r.source.trusted))


def run_in_turn(query: str, providers: tuple[str, ...], pages: int) -> tuple[dict[str, ProviderResult], list[str]]:
    """Providers one at a time, stopping at the first good-enough answer.
    Returns (results, providers skipped)."""
    results: dict[str, ProviderResult] = {}
    for i, name in enumerate(providers):
        results[name] = run_provider(name, query, pages)
        if good_enough(results[name]):
            return results, list(providers[i + 1:])
    return results, []


def lookup(query: str, providers: tuple[str, ...] = ("searchapi", "exa"),
           pages: int = MAX_CANDIDATES, free_first: bool = True, use_cache: bool = True,
           cross_check: bool = False) -> LookupResult:
    """free_first: answer from endoflife.date when it has the release, skipping paid search.
    cross_check: run every provider (in parallel) so their answers can verify each other.
    Without it, providers run in the given order and the rest are skipped once one finds
    dates on an official or trusted page — about half the cost, but nothing is "verified".
    use_cache: return a saved result under CACHE_DAYS old. Fresh results are always saved
    (unless a provider failed), so turning use_cache off refreshes the entry."""
    key = cache_key(query, providers, pages, free_first, cross_check)
    if use_cache and (hit := cache.get(key, CACHE_DAYS * cache.DAY)):
        res = LookupResult.from_dict(hit[0])
        res.cached = True
        for p in res.providers.values():
            p.usage = []  # nothing was spent this time
        return res

    eol = find_eol(query) if free_first else None
    skipped: list[str] = []
    if eol:
        results = {eol.provider: eol}
    elif not cross_check:
        results, skipped = run_in_turn(query, providers, pages)
    else:
        with ThreadPoolExecutor(max_workers=len(providers)) as pool:
            futures = {name: pool.submit(run_provider, name, query, pages) for name in providers}
            results = {name: f.result() for name, f in futures.items()}
    final, agreement, verified = compare(results)
    res = LookupResult(
        query=query,
        end_of_life=final["end_of_life"],
        end_of_support=final["end_of_support"],
        verified=verified,
        agreement=agreement,
        providers=results,
        retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        skipped=skipped,
    )
    if not any(p.error for p in results.values()):
        cache.put(key, res.to_dict())
    return res
