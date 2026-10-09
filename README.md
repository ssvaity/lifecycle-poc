# Product Lifecycle Lookup — POC

Give it a product (e.g. `Windows Server 2016`) and it returns the **end-of-support**
and **end-of-life** dates as JSON, each with a **citation** — the source page and the
exact text the date came from. Every lookup runs through **SearchAPI.io** and **Exa**
side by side and compares their answers.

```
query ─► SearchAPI.io (Google) ─► best official result ─► fetch page ─┐
     └─► Exa ───────────────────► best official result (+ page text) ─┤─► extract dates ─► compare ─► JSON
```

- **One source per product, per provider** — the result that looks most like an official
  vendor lifecycle/docs page (forums, blogs and aggregators are ranked down).
- **Extraction** — rule-based: lifecycle keywords matched to the nearest date, with
  table awareness (e.g. a "Mainstream End Date" column in the version's row). Each
  date comes with the exact text it was found in.
- **Verified** — both providers found the date and agree. Disagreements are flagged
  and left blank instead of guessed.

Definitions: *end of support* = end of mainstream / active / standard support;
*end of life* = end of all support, including extended / security support.

## Setup

```bash
cd ~/Desktop/lifecycle-poc
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # then add your keys
```

## Use

```bash
lifecycle lookup "Windows Server 2016"            # table with sources and quotes
lifecycle lookup "Python 3.8" --json              # full JSON
lifecycle lookup "Ubuntu 20.04" --provider exa    # one provider only

streamlit run app.py                              # web page at http://localhost:8501
```

## Test

```bash
pytest                       # unit + end-to-end tests, no network or API credits
lifecycle bench --limit 3    # provider benchmark — uses real API credits
```

`lifecycle bench` runs every product in `bench/products.json` through both providers,
scores each against reference dates from [endoflife.date](https://endoflife.date), and
reports accuracy, agreement rate, official-source rate and speed. The full report is
saved to `bench/results/`. Add products to `bench/products.json` (the `ref` is the
product's endoflife.date slug and cycle).

## JSON output

```json
{
  "query": "Windows Server 2016",
  "end_of_life": "2027-01-12",
  "end_of_support": "2022-01-11",
  "verified": true,
  "agreement": { "end_of_life": true, "end_of_support": true },
  "providers": {
    "searchapi": {
      "end_of_life": "2027-01-12",
      "end_of_support": "2022-01-11",
      "source": { "url": "https://learn.microsoft.com/…", "title": "…", "official": true, "official_score": 6 },
      "quotes": { "end_of_life": "… Extended End Date … Jan 12, 2027 …" },
      "error": null,
      "elapsed_s": 2.1,
      "notes": []
    },
    "exa": { "…": "same shape" }
  },
  "retrieved_at": "2026-10-08T09:00:00+00:00"
}
```

## Layout

```
lifecycle/
  providers/     searchapi.py, exa.py — one class per search API
  official.py    picks the single most-official result
  fetch.py       page → main text (tables kept)
  extract/       dates.py (parsing), rules.py
  compare.py     agreement + final dates
  lookup.py      the pipeline, both providers in parallel
  bench.py       accuracy benchmark vs endoflife.date
  cli.py         `lifecycle` command
app.py           Streamlit page
tests/           pytest suite with fixtures
```

## Known limits (POC)

- "Official" is a heuristic, not a vendor allow-list.
- Rule-based extraction can miss unusual page layouts.
- Pages that need JavaScript to render return no text via SearchAPI's fetch step.
- Vendors use "end of support" loosely — for some it means the final date.
