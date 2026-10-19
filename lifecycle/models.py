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
class UsageItem:
    """One billable (or free) step of a lookup, e.g. a search request or page fetches."""

    step: str
    units: int
    unit: str                      # "credit", "request", "page"
    cost_usd: float | None = None  # None: billed in credits, or the provider didn't say

    def cost_label(self) -> str:
        """"1 credit", "$0.0070", "free" — for tables."""
        if self.unit == "credit":
            return f"{self.units} credit{'s' if self.units != 1 else ''}"
        if self.cost_usd is None:
            return "—"
        return "free" if self.cost_usd == 0 else f"${self.cost_usd:.4f}"


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
    usage: list[UsageItem] = field(default_factory=list)


@dataclass
class LookupResult:
    query: str
    end_of_life: str | None
    end_of_support: str | None
    verified: bool
    agreement: dict[str, bool | None]
    providers: dict[str, ProviderResult]
    retrieved_at: str
    #: Served from the on-disk cache: this lookup made no API calls.
    cached: bool = False
    #: Providers not called because an earlier one already gave an official answer.
    skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> LookupResult:
        providers = {
            name: ProviderResult(**(p | {
                "source": Source(**p["source"]) if p.get("source") else None,
                "usage": [UsageItem(**u) for u in p.get("usage", [])],
            }))
            for name, p in d["providers"].items()
        }
        return cls(**(d | {"providers": providers}))
