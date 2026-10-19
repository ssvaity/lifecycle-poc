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
    res = lookup_mod.lookup("Windows Server 2016", cross_check=True)
    assert res.verified
    assert res.end_of_life == "2027-01-12" and res.end_of_support == "2022-01-11"
    assert res.providers["exa"].source.official


def test_one_provider_fails(monkeypatch):
    hit = SearchHit("https://learn.microsoft.com/lifecycle/windows-server-2016", "Microsoft Lifecycle", text=PAGE)

    def broken():
        raise ProviderError("EXA_API_KEY is not set (add it to .env)")

    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"searchapi": lambda: FakeProvider([hit]), "exa": broken})
    res = lookup_mod.lookup("Windows Server 2016", cross_check=True)
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


def test_usage_counts_searches_and_page_fetches(monkeypatch):
    """Provider usage is carried over and free page fetches are counted."""
    from lifecycle.models import UsageItem

    class Billed(FakeProvider):
        def search(self, query):
            self.usage = [UsageItem("Google search", 1, "credit")]
            return self.hits

    hits = [SearchHit("https://www.python.org/downloads/release/python-3818/", "Python Release Python 3.8.18"),
            SearchHit("https://example.com/python", "Python 3.8")]
    pages = {"https://www.python.org/downloads/release/python-3818/": "A security release.",
             "https://example.com/python": "| Branch | Status | End of life |\n| 3.8 | end-of-life | 2024-10-07 |"}
    monkeypatch.setattr(lookup_mod, "fetch_page", lambda url: (pages[url], url))
    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"searchapi": lambda: Billed(hits)})
    p = lookup_mod.lookup("Python 3.8", providers=("searchapi",)).providers["searchapi"]
    assert p.end_of_life == "2024-10-07"
    assert [(u.step, u.units) for u in p.usage] == [("Google search", 1), ("Page fetch", 2)]
    assert p.usage[1].cost_label() == "free"


def test_pages_limits_how_many_results_are_read(monkeypatch):
    """With pages=2 the lookup gives up after two dateless pages; the third is never read."""
    hits = [SearchHit(f"https://www.python.org/p{i}", "Python 3.8", text="No dates here.") for i in range(3)]
    hits[2].text = "| Branch | Status | End of life |\n| 3.8 | end-of-life | 2024-10-07 |"
    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"exa": lambda: FakeProvider(hits)})
    assert lookup_mod.lookup("Python 3.8", ("exa",), pages=2).providers["exa"].end_of_life is None
    assert lookup_mod.lookup("Python 3.8", ("exa",), pages=4).providers["exa"].end_of_life == "2024-10-07"


def test_second_lookup_comes_from_cache(monkeypatch):
    calls = []
    hit = SearchHit("https://learn.microsoft.com/lifecycle/windows-server-2016", "Microsoft Lifecycle", text=PAGE)

    def make():
        calls.append(1)
        return FakeProvider([hit])

    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"exa": make})
    first = lookup_mod.lookup("Windows Server 2016", ("exa",))
    again = lookup_mod.lookup("windows server  2016", ("exa",))
    assert len(calls) == 1 and not first.cached and again.cached
    assert again.end_of_life == first.end_of_life == "2027-01-12"
    assert again.providers["exa"].source.official and again.providers["exa"].usage == []
    lookup_mod.lookup("Windows Server 2016", ("exa",), use_cache=False)
    assert len(calls) == 2


def test_failed_lookups_are_not_cached(monkeypatch):
    def broken():
        raise ProviderError("EXA_API_KEY is not set (add it to .env)")

    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"exa": broken})
    lookup_mod.lookup("Windows Server 2016", ("exa",))
    assert not lookup_mod.lookup("Windows Server 2016", ("exa",)).cached


def test_endoflife_date_answer_skips_paid_search(monkeypatch):
    from lifecycle.models import ProviderResult

    def paid():
        raise AssertionError("paid search should not run")

    eol = ProviderResult("endoflife.date", end_of_life="2027-01-12", end_of_support="2022-01-11")
    monkeypatch.setattr(lookup_mod, "find_eol", lambda q: eol)
    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"searchapi": paid, "exa": paid})
    res = lookup_mod.lookup("Windows Server 2016")
    assert list(res.providers) == ["endoflife.date"] and res.end_of_life == "2027-01-12"


def test_second_provider_skipped_after_official_answer(monkeypatch):
    hit = SearchHit("https://learn.microsoft.com/lifecycle/windows-server-2016", "Microsoft Lifecycle", text=PAGE)

    def paid():
        raise AssertionError("exa should not run")

    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"searchapi": lambda: FakeProvider([hit]), "exa": paid})
    res = lookup_mod.lookup("Windows Server 2016")
    assert list(res.providers) == ["searchapi"] and res.skipped == ["exa"]
    assert res.end_of_life == "2027-01-12" and not res.verified


def test_second_provider_runs_when_first_has_no_official_answer(monkeypatch):
    unofficial = SearchHit("https://example.com/ws2016", "Windows Server 2016", text=PAGE)
    official = SearchHit("https://learn.microsoft.com/lifecycle/windows-server-2016", "Microsoft Lifecycle", text=PAGE)
    monkeypatch.setattr(lookup_mod, "PROVIDERS", {"searchapi": lambda: FakeProvider([unofficial]),
                                                  "exa": lambda: FakeProvider([official])})
    res = lookup_mod.lookup("Windows Server 2016")
    assert list(res.providers) == ["searchapi", "exa"] and res.skipped == []
    assert res.verified  # both found the same dates
