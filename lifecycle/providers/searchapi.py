"""SearchAPI.io — Google results. Returns links + snippets; pages are fetched separately.

Docs: https://www.searchapi.io/docs/google
"""

from __future__ import annotations

import httpx

from ..models import SearchHit
from .base import Provider, ProviderError, search_query

URL = "https://www.searchapi.io/api/v1/search"


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
        return [
            SearchHit(url=o["link"], title=o.get("title", ""), snippet=o.get("snippet", ""))
            for o in data.get("organic_results", [])
            if o.get("link")
        ]
