"""Exa.ai — neural search that also returns each page's text (no separate fetch).

Docs: https://exa.ai/docs/reference/search
"""

from __future__ import annotations

import httpx

from ..models import SearchHit
from .base import Provider, ProviderError, search_query

URL = "https://api.exa.ai/search"
MAX_CHARS = 60_000


class ExaProvider(Provider):
    name = "exa"
    env_key = "EXA_API_KEY"
    returns_text = True

    def search(self, query: str) -> list[SearchHit]:
        try:
            r = self.client.post(
                URL,
                headers={"x-api-key": self.api_key},
                json={
                    "query": search_query(query),
                    "type": "auto",
                    "numResults": 8,
                    "contents": {"text": {"maxCharacters": MAX_CHARS}},
                },
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"Exa request failed: {e}") from e
        if r.status_code != 200:
            raise ProviderError(f"Exa HTTP {r.status_code}: {r.text[:200]}")
        return [
            SearchHit(url=x["url"], title=x.get("title") or "", text=x.get("text"))
            for x in r.json().get("results", [])
            if x.get("url")
        ]
