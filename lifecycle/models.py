"""Data shapes shared across providers, extractors and the CLI / web page."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

# The two dates we look for. Definitions used throughout:
#   end_of_support - end of mainstream / active / standard support
#   end_of_life    - end of all support, including security / extended support
FIELDS = ("end_of_life", "end_of_support")


@dataclass
class SearchHit:
    """One search result as returned by a provider."""

    url: str
    title: str
    snippet: str = ""
    text: str | None = None


@dataclass
class Source:
    """The single page a provider's answer is based on."""

    url: str
    title: str
    official: bool
    official_score: int
    trusted: bool = False


@dataclass
class Extraction:
    """Dates pulled from one page, with the exact text each came from."""

    end_of_life: str | None = None
    end_of_support: str | None = None
    quotes: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    #: At least one date came from a line or row naming the queried version.
    version_matched: bool = False


@dataclass
class ProviderResult:
    provider: str
    end_of_life: str | None = None
    end_of_support: str | None = None
    source: Source | None = None
    quotes: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    elapsed_s: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class LookupResult:
    query: str
    end_of_life: str | None
    end_of_support: str | None
    verified: bool
    agreement: dict[str, bool | None]
    providers: dict[str, ProviderResult]
    retrieved_at: str

    def to_dict(self) -> dict:
        return asdict(self)
