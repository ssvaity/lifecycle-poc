"""endoflife.date matching and answers, with the API stubbed (no network)."""

import httpx

from lifecycle import eoldate

PRODUCTS = [
    {"name": "windows-server", "label": "Microsoft Windows Server", "aliases": ["windowsserver"]},
    {"name": "windows", "label": "Microsoft Windows", "aliases": []},
    {"name": "debian", "label": "Debian", "aliases": []},
    {"name": "nodejs", "label": "Node.js", "aliases": ["node"]},
    {"name": "rhel", "label": "Red Hat Enterprise Linux", "aliases": ["redhat"]},
    {"name": "python", "label": "Python", "aliases": []},
]
WINDOWS_SERVER = {
    "label": "Microsoft Windows Server",
    "labels": {"eoas": "Active Support", "eol": "Security Support", "eoes": "Extended Security Updates"},
    "links": {"html": "https://endoflife.date/windows-server"},
    "releases": [
        {"name": "2019", "label": "2019", "eoasFrom": "2024-01-09", "eolFrom": "2029-01-09"},
        {"name": "2016", "label": "2016 (LTSC)", "eoasFrom": "2022-01-11", "eolFrom": "2027-01-12", "eoesFrom": "2030-01-12"},
    ],
}


def api(routes, calls=None):
    def handler(req: httpx.Request):
        if calls is not None:
            calls.append(req.url.path)
        body = routes.get(req.url.path)
        return httpx.Response(200, json={"result": body}) if body is not None else httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


ROUTES = {"/api/v1/products": PRODUCTS, "/api/v1/products/windows-server": WINDOWS_SERVER}


def test_match_product():
    m = lambda q: eoldate.match_product(q, PRODUCTS)  # noqa: E731
    assert m("Windows Server 2016") == "windows-server"
    assert m("Microsoft Windows Server 2016") == "windows-server"
    assert m("Windows 11") == "windows"
    assert m("Debian 10 Buster") == "debian"
    assert m("Node.js 18") == "nodejs"
    assert m("Red Hat Enterprise Linux 7") == "rhel"
    assert m("Ubuntu 20.04 LTS") is None


def test_match_release_uses_release_line():
    releases = [{"name": "3.10"}, {"name": "3.1"}]
    assert eoldate.match_release("Python 3.10.22", releases)["name"] == "3.10"
    assert eoldate.match_release("Python 3.9", releases) is None


def test_find_answers_with_citation():
    r = eoldate.find("Windows Server 2016", api(ROUTES))
    assert (r.end_of_support, r.end_of_life) == ("2022-01-11", "2027-01-12")
    assert r.source.url == "https://endoflife.date/windows-server" and r.source.trusted
    assert r.quotes["end_of_life"] == "Microsoft Windows Server 2016 (LTSC): Security Support ends 2027-01-12"
    assert any("Extended Security Updates" in n and "2030-01-12" in n for n in r.notes)
    assert r.usage[0].units == 2 and r.usage[0].cost_label() == "free"


def test_find_caches_catalog():
    calls = []
    eoldate.find("Windows Server 2016", api(ROUTES, calls))
    r = eoldate.find("Windows Server 2019", api(ROUTES, calls))
    assert len(calls) == 2 and r.usage == []
    assert r.end_of_life == "2029-01-09"


def test_find_falls_back():
    assert eoldate.find("Windows Server 2003", api(ROUTES)) is None    # unknown release
    assert eoldate.find("Acme Widget 3", api(ROUTES)) is None           # unknown product


def test_find_api_down():
    assert eoldate.find("Windows Server 2016", api({})) is None
