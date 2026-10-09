from lifecycle.extract import extract
from lifecycle.fetch import html_to_text

# Trimmed from learn.microsoft.com/en-us/lifecycle/products/windows-server-2016
MS_HTML = """<html><body><main><h1>Windows Server 2016</h1>
<p>Windows Server 2016 follows the Fixed Lifecycle Policy.</p>
<table><thead><tr><th>Listing</th><th>Start Date</th><th>Mainstream End Date</th><th>Extended End Date</th></tr></thead>
<tbody><tr><td>Windows Server 2016</td>
<td><local-time timezone="America/Los_Angeles" format="date" datetime="10/15/2016 8:00:00 AM">10/15/2016 8:00:00 AM</local-time></td>
<td><local-time timezone="America/Los_Angeles" format="date" datetime="1/12/2022 6:59:59 AM">1/12/2022 6:59:59 AM</local-time></td>
<td><local-time timezone="America/Los_Angeles" format="date" datetime="1/13/2027 6:59:59 AM">1/13/2027 6:59:59 AM</local-time></td>
</tr></tbody></table></main></body></html>"""


def test_microsoft_local_time_dates_kept_in_pacific_time():
    text = html_to_text(MS_HTML)
    ex = extract("Windows Server 2016", text)
    assert ex.end_of_support == "2022-01-11"  # UTC 1/12 06:59 is still Jan 11 in Redmond
    assert ex.end_of_life == "2027-01-12"


def test_english_urls():
    from lifecycle.fetch import english_urls
    assert english_urls("https://learn.microsoft.com/de-de/lifecycle/products/windows-server-2016")[0] == \
        "https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2016"
    assert "https://nodejs.org/en/about/eol" in english_urls("https://nodejs.org/zh-tw/about/eol")
    assert english_urls("https://learn.microsoft.com/en-gb/lifecycle/x") == []
    assert english_urls("https://devguide.python.org/versions/") == []
