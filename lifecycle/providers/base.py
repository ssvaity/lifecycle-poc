from __future__ import annotations

import os

import httpx

from ..models import SearchHit
from ..versions import release_line

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class ProviderError(RuntimeError):
    pass


def search_query(query: str) -> str:
    """Query sent to every provider; patch versions cut to their release line."""
    return f"{release_line(query)} end of life end of support lifecycle official"


class Provider:
    name: str = ""
    env_key: str = ""
    #: True when search results already include page text (no fetch needed).
    returns_text: bool = False

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or os.getenv(self.env_key)
        if not self.api_key:
            raise ProviderError(f"{self.env_key} is not set (add it to .env)")
        self.client = client or httpx.Client(timeout=TIMEOUT)

    def search(self, query: str) -> list[SearchHit]:
        raise NotImplementedError
