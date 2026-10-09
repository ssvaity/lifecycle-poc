"""End-to-end lookup: search → one official source per provider → extract → compare."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .compare import compare
from .extract import extract
from .fetch import FetchError, fetch_page
from .models import LookupResult, ProviderResult
from .official import rank
from .providers import PROVIDERS
from .providers.base import ProviderError


def run_provider(name: str, query: str) -> ProviderResult:
    """Search, then try the top-ranked candidates in order and keep the first
    page with lifecycle dates for the queried version — one source per provider.
    Dates from a page that doesn't tie them to the version (often another
    version's dates) are never returned: no answer beats a wrong one."""
    result = ProviderResult(provider=name)
    started = time.perf_counter()
    try:
        provider = PROVIDERS[name]()
        candidates = rank(provider.search(query), query)
        if not candidates:
            result.error = "no usable search results"
            return result

        readable = None
        for hit, source in candidates:
            try:
                text = hit.text
                if text is None:
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
        result.elapsed_s = round(time.perf_counter() - started, 2)
    return result


def _apply(result: ProviderResult, source, ex) -> None:
    result.source = source
    result.end_of_life, result.end_of_support = ex.end_of_life, ex.end_of_support
    result.quotes = ex.quotes
    result.notes += ex.notes


def lookup(query: str, providers: tuple[str, ...] = ("searchapi", "exa")) -> LookupResult:
    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        futures = {name: pool.submit(run_provider, name, query) for name in providers}
        results = {name: f.result() for name, f in futures.items()}
    final, agreement, verified = compare(results)
    return LookupResult(
        query=query,
        end_of_life=final["end_of_life"],
        end_of_support=final["end_of_support"],
        verified=verified,
        agreement=agreement,
        providers=results,
        retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
