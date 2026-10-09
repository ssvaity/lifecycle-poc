from lifecycle.compare import compare, same_date
from lifecycle.models import ProviderResult


def pr(name, eol=None, eos=None):
    return ProviderResult(provider=name, end_of_life=eol, end_of_support=eos)


def test_same_date_precision():
    assert same_date("2027-01", "2027-01-12")
    assert not same_date("2027-01-12", "2027-01-13")


def test_agree_is_verified_and_keeps_precise_value():
    final, agreement, verified = compare({"a": pr("a", "2027-01-12", "2022-01"), "b": pr("b", "2027-01-12", "2022-01-11")})
    assert verified
    assert final == {"end_of_life": "2027-01-12", "end_of_support": "2022-01-11"}
    assert agreement == {"end_of_life": True, "end_of_support": True}


def test_disagreement_leaves_field_empty():
    final, agreement, verified = compare({"a": pr("a", "2027-01-12"), "b": pr("b", "2026-01-12")})
    assert not verified
    assert final["end_of_life"] is None
    assert agreement["end_of_life"] is False


def test_single_provider_value_is_kept_but_unverified():
    final, agreement, verified = compare({"a": pr("a", "2027-01-12"), "b": pr("b")})
    assert final["end_of_life"] == "2027-01-12"
    assert agreement["end_of_life"] is None
    assert not verified


def test_nothing_found():
    _, _, verified = compare({"a": pr("a"), "b": pr("b")})
    assert not verified
