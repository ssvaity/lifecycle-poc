import json

import httpx
import pytest

from lifecycle.providers import ExaProvider, SearchApiProvider
from lifecycle.providers.base import ProviderError
from lifecycle.providers.searchapi import remaining_credits


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_searchapi_parses_organic_results():
    def handler(req: httpx.Request):
        assert req.url.params["engine"] == "google"
        assert req.headers["authorization"] == "Bearer k"
        return httpx.Response(200, json={"organic_results": [
            {"position": 1, "title": "Lifecycle", "link": "https://learn.microsoft.com/x", "snippet": "s"},
            {"position": 2, "title": "No link"},
        ]})

    p = SearchApiProvider("k", client(handler))
    hits = p.search("Windows Server 2016")
    assert [h.url for h in hits] == ["https://learn.microsoft.com/x"]
    assert hits[0].text is None
    assert [(u.step, u.units, u.unit) for u in p.usage] == [("Google search", 1, "credit")]


def test_exa_returns_page_text():
    def handler(req: httpx.Request):
        body = json.loads(req.content)
        assert req.headers["x-api-key"] == "k"
        assert body["contents"]["text"]["maxCharacters"] > 0
        return httpx.Response(200, json={"results": [{"url": "https://devguide.python.org/versions/", "title": "Versions", "text": "page"}],
                                         "costDollars": {"total": 0.007}})

    p = ExaProvider("k", client(handler))
    hits = p.search("Python 3.8")
    assert hits[0].text == "page"
    assert p.usage[0].cost_usd == 0.007 and p.usage[0].cost_label() == "$0.0070"


def test_failed_search_records_no_usage():
    p = SearchApiProvider("k", client(lambda r: httpx.Response(401, text="bad key")))
    with pytest.raises(ProviderError):
        p.search("x")
    assert p.usage == []


def test_remaining_credits():
    ok = client(lambda r: httpx.Response(200, json={"account": {"remaining_credits": 39}}))
    assert remaining_credits("k", ok) == 39
    assert remaining_credits("k", client(lambda r: httpx.Response(401))) is None


def test_http_error_raises_provider_error():
    with pytest.raises(ProviderError, match="401"):
        SearchApiProvider("k", client(lambda r: httpx.Response(401, text="bad key"))).search("x")


def test_missing_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="EXA_API_KEY"):
        ExaProvider()


def test_search_query_uses_release_line():
    from lifecycle.providers.base import search_query
    assert search_query("python 3.10.22").startswith("python 3.10 ")
    assert search_query("Windows Server 2016").startswith("Windows Server 2016 ")


def test_exa_num_results_capped_at_included_price():
    sent = []

    def handler(req: httpx.Request):
        sent.append(json.loads(req.content)["numResults"])
        return httpx.Response(200, json={"results": []})

    p = ExaProvider("k", client(handler))
    p.num_results = 4
    p.search("x")
    p.num_results = 12
    p.search("x")
    assert sent == [4, 10]
