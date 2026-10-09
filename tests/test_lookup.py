"""End-to-end lookup with both providers stubbed (no network)."""

from pathlib import Path

from lifecycle import lookup as lookup_mod
from lifecycle.models import SearchHit
from lifecycle.providers.base import ProviderError

PAGE = (Path(__file__).parent / "fixtures" / "windows_server_page.txt").read_text()


class FakeProvider:
    def __init__(self, hits):
        self.hits = hits

    def search(self, query):
        return self.hits


def test_both_agree(monkeypatch):
    hit = SearchHit("https://learn.microsoft.com/lifecycle/windows-server-2016", "Microsoft Lifecycle", text=PAGE)
    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"searchapi": lambda: FakeProvider([hit]), "exa": lambda: FakeProvider([hit])})
    res = lookup_mod.lookup("Windows Server 2016")
    assert res.verified
    assert res.end_of_life == "2027-01-12" and res.end_of_support == "2022-01-11"
    assert res.providers["exa"].source.official


def test_one_provider_fails(monkeypatch):
    hit = SearchHit("https://learn.microsoft.com/lifecycle/windows-server-2016", "Microsoft Lifecycle", text=PAGE)

    def broken():
        raise ProviderError("EXA_API_KEY is not set (add it to .env)")

    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"searchapi": lambda: FakeProvider([hit]), "exa": broken})
    res = lookup_mod.lookup("Windows Server 2016")
    assert res.providers["exa"].error.startswith("EXA_API_KEY")
    assert res.end_of_life == "2027-01-12"   # kept from the working provider…
    assert not res.verified                   # …but not verified by a second one
    assert res.to_dict()["providers"]["searchapi"]["quotes"]


def test_skips_candidate_without_dates(monkeypatch):
    """The top-ranked page has no dates; the lookup moves on to the next one."""
    no_dates = SearchHit("https://www.python.org/downloads/release/python-3818/", "Python Release Python 3.8.18", text="A security release.")
    status = SearchHit("https://devguide.python.org/versions/", "Status of Python versions",
                       text="| Branch | Status | End of life |\n| 3.8 | end-of-life | 2024-10-07 |")
    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"exa": lambda: FakeProvider([no_dates, status])})
    res = lookup_mod.lookup("Python 3.8", providers=("exa",))
    exa = res.providers["exa"]
    assert exa.end_of_life == "2024-10-07"
    assert exa.source.url == "https://devguide.python.org/versions/"
    assert any("tried next result" in n for n in exa.notes)


def test_prefers_page_about_queried_version(monkeypatch):
    """A page with another version's dates loses to one that names the queried version."""
    other = SearchHit("https://example.com/python-39-eol", "Python EOL", text="Python 3.9 will reach end of life in October 2025.")
    status = SearchHit("https://devguide.python.org/versions/", "Status of Python versions",
                       text="| Branch | Status | End of life |\n| 3.10 | security | 2026-10-01 |")
    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"searchapi": lambda: FakeProvider([other, status])})
    res = lookup_mod.lookup("python 3.10.22", providers=("searchapi",))
    assert res.providers["searchapi"].end_of_life == "2026-10-01"
    assert res.providers["searchapi"].source.url == "https://devguide.python.org/versions/"


def test_other_versions_dates_are_not_returned(monkeypatch):
    """Only pages with another version's dates: leave the answer blank, don't guess."""
    other = SearchHit("https://example.com/python-39-eol", "Python EOL", text="Python 3.9 will reach end of life in October 2025.")
    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"searchapi": lambda: FakeProvider([other])})
    p = lookup_mod.lookup("Python 3.10", providers=("searchapi",)).providers["searchapi"]
    assert p.end_of_life is None and p.end_of_support is None
    assert any("no result gave dates for this version" in n for n in p.notes)
