from pathlib import Path

from lifecycle.extract.rules import extract, version_tokens

FIX = Path(__file__).parent / "fixtures"


def test_version_tokens():
    assert version_tokens("Windows Server 2016") == ["2016"]
    assert version_tokens("Ubuntu 20.04 LTS") == ["20.04"]
    assert version_tokens("Python") == []


def test_table_page():
    ex = extract("Windows Server 2016", (FIX / "windows_server_page.txt").read_text())
    assert ex.end_of_support == "2022-01-11"  # Mainstream End Date column
    assert ex.end_of_life == "2027-01-12"     # Extended End Date column
    assert "Extended End Date" in ex.quotes["end_of_life"]


def test_prose_page_prefers_line_with_version():
    ex = extract("Python 3.8", (FIX / "python_page.txt").read_text())
    assert ex.end_of_life == "2024-10-07"     # not 3.9's October 2025
    assert ex.end_of_support == "2021-05-03"
    assert "3.8" in ex.quotes["end_of_life"]


def test_no_dates():
    ex = extract("Foo 1.0", "Nothing about lifecycles here.")
    assert ex.end_of_life is None and ex.end_of_support is None
    assert ex.notes


DEVGUIDE = (
    "| Branch | Schedule | Status | First release | End of life | Release manager |\n"
    "| 3.10 | PEP 619 | end-of-life | 2021-10-04 | 2026-10-01 | Pablo Galindo Salgado |\n"
    "| 3.1 | PEP 375 | end-of-life | 2009-06-27 | 2012-04-09 | Benjamin Peterson |"
)


def test_patch_version_finds_release_line_row():
    # "3.10.22" is listed as "3.10"; the Status cell's "end-of-life" must not
    # claim the First release date, and "3.1" must not match "3.10".
    ex = extract("python 3.10.22", DEVGUIDE)
    assert ex.end_of_life == "2026-10-01"
    assert ex.version_matched


def test_other_versions_dates_not_version_matched():
    ex = extract("Python 3.10", "Python 3.9 will reach end of life in October 2025.")
    assert ex.end_of_life == "2025-10"
    assert not ex.version_matched


def test_footnoted_headers():
    # djangoproject.com/download: header cells end in footnote digits
    text = ("| Release Series | Latest Release | End of mainstream support1 | End of extended support2 |\n"
            "| 4.2 LTS | 4.2.30 | December 4, 2023 | April 7, 2026 |")
    ex = extract("Django 4.2", text)
    assert ex.end_of_support == "2023-12-04" and ex.end_of_life == "2026-04-07"


def test_endoflife_date_table_matches_version_in_first_cell_only():
    text = ("| Release | Python | Released | Active Support | Security Support | Latest |\n"
            "| 5.0 | 3.10 - 3.12 | (04 Dec 2023) | Ended (02 Apr 2025) | Ended (31 Mar 2025) | 5.0.14 |\n"
            "| 3.10 | 3.6 - 3.9 | (01 Jan 2020) | Ended (01 Jan 2021) | Ended (01 Apr 2022) | 3.10.1 |")
    ex = extract("Django 3.10", text)   # "3.10" also appears in 5.0's Python column
    assert ex.end_of_life == "2022-04-01" and ex.end_of_support == "2021-01-01"


def test_devguide_month_precision_row():
    text = DEVGUIDE + "\n| 3.12 | PEP 693 | security | 2023-10-02 | 2028-10 | Thomas Wouters |"
    ex = extract("Python 3.12", text)
    assert ex.end_of_life == "2028-10" and ex.version_matched
