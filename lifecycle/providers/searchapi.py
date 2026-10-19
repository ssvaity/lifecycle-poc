"""SearchAPI.io — Google results. Returns links + snippets; pages are fetched separately.

Docs: https://www.searchapi.io/docs/google
"""

from __future__ import annotations

import httpx

import os

from ..models import SearchHit, UsageItem
from .base import TIMEOUT, Provider, ProviderError, search_query

URL = "https://www.searchapi.io/api/v1/search"
ACCOUNT_URL = "https://www.searchapi.io/api/v1/me"


def remaining_credits(api_key: str | None = None, client: httpx.Client | None = None) -> int | None:
    """Search credits left on the account (this call is free), or None if unknown."""
    api_key = api_key or os.getenv(SearchApiProvider.env_key)
    if not api_key:
        return None
    try:
        r = (client or httpx.Client(timeout=TIMEOUT)).get(
            ACCOUNT_URL, headers={"Authorization": f"Bearer {api_key}"})
        return int(r.json()["account"]["remaining_credits"]) if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None


class SearchApiProvider(Provider):
    name = "searchapi"
    env_key = "SEARCHAPI_API_KEY"
    returns_text = False

    def search(self, query: str) -> list[SearchHit]:
        try:
            r = self.client.get(
                URL,
                params={"engine": "google", "q": search_query(query), "hl": "en", "gl": "us"},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"SearchAPI request failed: {e}") from e
        if r.status_code != 200:
            raise ProviderError(f"SearchAPI HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        if data.get("error"):
            raise ProviderError(f"SearchAPI error: {data['error']}")
        self.usage.append(UsageItem("Google search", 1, "credit"))
        return [
            SearchHit(url=o["link"], title=o.get("title", ""), snippet=o.get("snippet", ""))
            for o in data.get("organic_results", [])
            if o.get("link")
        ]
