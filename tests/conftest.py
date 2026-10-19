import pytest

from lifecycle import cache, lookup


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    """No test touches the real cache or endoflife.date unless it opts in."""
    monkeypatch.setattr(cache, "PATH", tmp_path / "cache.sqlite")
    monkeypatch.setattr(lookup, "find_eol", lambda query: None)
