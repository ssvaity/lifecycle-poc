"""CLI: `lifecycle lookup "Windows Server 2016"` and `lifecycle bench`."""

from __future__ import annotations

import json
from enum import Enum

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from .official import MAX_CANDIDATES

load_dotenv()

app = typer.Typer(add_completion=False, help="Look up end-of-life / end-of-support dates with citations.")
console = Console()


class Which(str, Enum):
    both = "both"
    searchapi = "searchapi"
    exa = "exa"


def _providers(which: Which) -> tuple[str, ...]:
    return ("searchapi", "exa") if which is Which.both else (which.value,)


def _mark(v: bool | None) -> str:
    return {True: "[green]✓ agree[/]", False: "[red]✗ differ[/]", None: "[dim]–[/]"}[v]


@app.command()
def lookup(
    query: str = typer.Argument(..., help='Product and version, e.g. "Windows Server 2016"'),
    provider: Which = typer.Option(Which.both, help="Which search provider(s) to use"),
    as_json: bool = typer.Option(False, "--json", help="Print the full JSON result"),
    pages: int = typer.Option(MAX_CANDIDATES, min=1, max=10, help="Most result pages each provider may read"),
    eol: bool = typer.Option(True, help="Check endoflife.date first (free); skip paid search if it has the release"),
    cache: bool = typer.Option(True, help="Use a saved result if one is under a week old"),
    cross_check: bool = typer.Option(False, help="Run every provider so they verify each other (about 2x the cost)"),
):
    """Find EOL / EOS dates for one product."""
    from .lookup import lookup as run

    with console.status(f"Looking up {query}…"):
        res = run(query, _providers(provider), pages, free_first=eol, use_cache=cache, cross_check=cross_check)

    if as_json:
        print(json.dumps(res.to_dict(), indent=2))
        return

    status = ("[cyan]from endoflife.date[/]" if list(res.providers) == ["endoflife.date"]
              else "[green]verified[/]" if res.verified
              else f"[cyan]official source; {', '.join(res.skipped)} skipped (--cross-check to verify)[/]" if res.skipped
              else "[yellow]not verified[/]")
    if res.cached:
        status += f"  [dim](saved result from {res.retrieved_at}; --no-cache to refresh)[/]"
    console.print(f"\n[bold]{res.query}[/]  {status}")
    t = Table(show_header=True, header_style="bold")
    t.add_column("")
    t.add_column("Final")
    for name in res.providers:
        t.add_column(name)
    t.add_column("Match")
    for f, label in (("end_of_support", "End of support"), ("end_of_life", "End of life")):
        t.add_row(label, getattr(res, f) or "—",
                  *[getattr(p, f) or "—" for p in res.providers.values()], _mark(res.agreement[f]))
    console.print(t)

    for name, p in res.providers.items():
        console.print(f"\n[bold]{name}[/] ({p.elapsed_s}s)")
        if p.error:
            console.print(f"  [red]error:[/] {p.error}")
            continue
        if p.source:
            badge = ("[green]official[/]" if p.source.official
                     else "[cyan]trusted (not the vendor)[/]" if p.source.trusted
                     else "[yellow]unofficial?[/]")
            console.print(f"  source: {p.source.title} {badge}\n  {p.source.url}")
        for f, q in p.quotes.items():
            console.print(f'  {f}: [italic]"{q[:200]}"[/]')
        for n in p.notes:
            console.print(f"  [dim]note: {n}[/]")

    usage = [(name, u) for name, p in res.providers.items() for u in p.usage]
    if usage:
        t = Table(title="Usage", header_style="bold")
        for col in ("Provider", "Step", "Units", "Cost"):
            t.add_column(col)
        for name, u in usage:
            t.add_row(name, u.step, f"{u.units} {u.unit}{'s' if u.units != 1 else ''}", u.cost_label())
        console.print()
        console.print(t)
    if "searchapi" in res.providers:
        from .providers.searchapi import remaining_credits

        left = remaining_credits()
        if left is not None:
            console.print(f"SearchAPI credits left: [bold]{left}[/]")


@app.command("clear-cache")
def clear_cache():
    """Delete all saved lookups and endoflife.date data."""
    from . import cache

    console.print(f"Removed {cache.clear()} saved entries.")


@app.command()
def bench(
    limit: int = typer.Option(None, help="Only run the first N products"),
):
    """Score both providers against endoflife.date (uses API credits)."""
    from .bench import run

    report = run(limit, on_progress=lambda i, n, q: console.print(f"[dim]{i}/{n}[/] {q}"))
    t = Table(title="Provider benchmark", header_style="bold")
    for col in ("Provider", "Accuracy", "Fields graded", "Errors", "Official source", "Avg seconds"):
        t.add_column(col)
    for name in ("searchapi", "exa"):
        s = report["summary"][name]
        pct = lambda v: "—" if v is None else f"{v:.0%}"  # noqa: E731
        t.add_row(name, pct(s["accuracy"]), str(s["fields_graded"]), str(s["errors"]),
                  pct(s["official_source_rate"]), str(s["avg_seconds"]))
    console.print(t)
    ar = report["summary"]["agreement_rate"]
    console.print(f"Providers agreed on {'—' if ar is None else f'{ar:.0%}'} of compared dates.")
    console.print(f"Full report: {report['saved_to']}")


if __name__ == "__main__":
    app()
