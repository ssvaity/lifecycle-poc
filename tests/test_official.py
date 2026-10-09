from lifecycle.models import SearchHit
from lifecycle.official import MAX_CANDIDATES, rank, score, to_source

Q = "Python 3.8"


def test_excluded_sites():
    for url in (
        "https://www.reddit.com/r/sysadmin/comments/x",
        "https://endoflife.ai/python/3.8",
        "https://discuss.python.org/t/end-of-life-eol-versions-usage/69601",  # forum on the vendor's own domain
        "https://github.com/vega/altair/issues/3497",
    ):
        assert score(SearchHit(url, "Python 3.8 end of life"), Q) == -10, url


def test_vendor_page_beats_lifecycle_sounding_third_party():
    # Real Python 3.8 results: the forum thread used to win on keywords alone.
    hits = [
        SearchHit("https://discuss.python.org/t/end-of-life-eol-versions-usage/69601", "End-of-life (EOL) versions usage - Python Discussions"),
        SearchHit("https://help.maptek.com/mapteksdk/1.9/topics/technical-notes/python-lifecycle-policy.htm", "Python Lifecycle Policy"),
        SearchHit("https://devguide.python.org/versions/", "Status of Python versions"),
    ]
    ranked = rank(hits, Q)
    assert ranked[0][0].url == "https://devguide.python.org/versions/"
    assert all("discuss.python.org" not in h.url for h, _ in ranked)


def test_official_requires_vendor_domain():
    assert to_source(SearchHit("https://devguide.python.org/versions/", "Status of Python versions"), Q).official
    assert not to_source(SearchHit("https://help.maptek.com/x/python-lifecycle-policy.htm", "Python Lifecycle Policy"), Q).official
    # vendor alias: Windows → microsoft.com
    ms = SearchHit("https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2016", "Windows Server 2016 - Microsoft Lifecycle")
    assert to_source(ms, "Windows Server 2016").official


def test_rank_limit_and_empty():
    hits = [SearchHit(f"https://docs.python.org/{i}", "Python docs") for i in range(6)]
    assert len(rank(hits, Q)) == MAX_CANDIDATES
    assert rank([], Q) == []


def test_title_naming_other_version_ranks_down():
    q = "python 3.10.22"
    other = SearchHit("https://example.com/python-eol", "Python 3.9 End of Life October 2025 — Upgrade Target")
    right = SearchHit("https://example.com/python-eol-2", "Python 3.10 End of Life")
    assert score(right, q) > score(other, q)


def test_trusted_tracker_after_official_before_others():
    hits = [
        SearchHit("https://www.herodevs.com/python-eol", "Python 3.8 End of Life"),
        SearchHit("https://endoflife.date/python", "Python"),
        SearchHit("https://devguide.python.org/versions/", "Status of Python versions"),
    ]
    ranked = rank(hits, Q)
    assert [h.url for h, _ in ranked] == [
        "https://devguide.python.org/versions/", "https://endoflife.date/python", "https://www.herodevs.com/python-eol"]
    eol = ranked[1][1]
    assert eol.trusted and not eol.official
    assert score(SearchHit("https://endoflife.ai/python/3.8", "Python 3.8"), Q) == -10  # other trackers still excluded


def test_vendor_name_must_be_whole_domain_label():
    assert to_source(SearchHit("https://nodejs.org/en/about/eol", "Node.js EOL"), "Node.js 20").official
    assert not to_source(SearchHit("https://nodesource.com/blog/node-20-eol", "Node.js 20 end of life"), "Node.js 20").official
    assert not to_source(SearchHit("https://example.net/lifecycle/dotnet-6", ".NET 6 end of support"), ".NET 6").official
