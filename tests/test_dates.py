from lifecycle.extract.dates import find_dates, normalise


def test_formats():
    assert normalise("2027-01-12") == "2027-01-12"
    assert normalise("Jan 12, 2027") == "2027-01-12"
    assert normalise("January 12 2027") == "2027-01-12"
    assert normalise("12 January 2027") == "2027-01-12"
    assert normalise("12th Jan, 2027") == "2027-01-12"
    assert normalise("1/12/2027") == "2027-01-12"
    assert normalise("October 2025") == "2025-10"
    assert normalise("Sept. 30, 2024") == "2024-09-30"


def test_rejects_non_dates():
    assert normalise(None) is None
    assert normalise("version 2016") is None
    assert normalise("2027-13-45") is None


def test_precise_match_wins_over_month_only():
    # "January 12, 2027" must not also yield a month-only "2027-01"
    assert [d.iso for d in find_dates("ends January 12, 2027.")] == ["2027-01-12"]


def test_order_preserved():
    assert [d.iso for d in find_dates("from 2016-10-15 to Jan 11, 2022")] == ["2016-10-15", "2022-01-11"]


def test_year_month_numeric():
    from lifecycle.extract.dates import find_dates
    assert [d.iso for d in find_dates("| 3.12 | 2023-10-02 | 2028-10 |")] == ["2023-10-02", "2028-10"]
