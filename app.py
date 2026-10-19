"""Streamlit page: `streamlit run app.py`."""

import json

import streamlit as st
from dotenv import load_dotenv

from lifecycle.eoldate import NAME as EOL
from lifecycle.lookup import CACHE_DAYS, lookup
from lifecycle.official import MAX_CANDIDATES, PAGE_CHOICES
from lifecycle.providers.searchapi import remaining_credits

load_dotenv()

st.set_page_config(page_title="Lifecycle Lookup", page_icon="📅", layout="wide")
st.title("Product lifecycle lookup")
st.caption("End-of-life and end-of-support dates, with citations — compared across SearchAPI.io and Exa.")

with st.form("lookup"):
    query = st.text_input("Product and version", placeholder="e.g. Windows Server 2016")
    which = st.radio("Providers", ["Both", "SearchAPI.io", "Exa"], horizontal=True)
    pages = st.select_slider(
        "Pages to read", options=PAGE_CHOICES, value=MAX_CANDIDATES,
        help="Most result pages each provider may read before giving up. It stops at the first page "
             "with dates for this version. More pages cost no extra credits, only time.")
    c1, c2, c3 = st.columns(3)
    free_first = c1.checkbox("Check endoflife.date first (free)", value=True,
                             help="If endoflife.date knows this release, answer from it and skip the paid search.")
    use_cache = c2.checkbox(f"Use saved results (up to {CACHE_DAYS} days old)", value=True,
                            help="Untick to search again and refresh the saved result.")
    cross_check = c3.checkbox("Cross-check with a second provider", value=False,
                              help="Run both providers so they can verify each other — about twice the cost. "
                                   "Off: Exa only runs if SearchAPI finds no official answer.")
    submitted = st.form_submit_button("Look up", type="primary")

if submitted and query.strip():
    providers = {"Both": ("searchapi", "exa"), "SearchAPI.io": ("searchapi",), "Exa": ("exa",)}[which]
    with st.spinner(f"Searching for {query}…"):
        res = lookup(query.strip(), providers, pages, free_first, use_cache, cross_check)

    if res.cached:
        st.info(f"Saved result from {res.retrieved_at} — no API calls made. "
                "Untick “Use saved results” to search again.")
    if list(res.providers) == [EOL]:
        st.info("Answered by endoflife.date for free — no paid search used. "
                "Untick “Check endoflife.date first” to search the vendor's own pages instead.")
    elif res.skipped:
        st.info(f"{', '.join(res.skipped)} not called — {', '.join(res.providers)} found the dates on an "
                "official page. Tick “Cross-check” to have a second provider verify them.")
    else:
        (st.success if res.verified else st.warning)(
            "Verified — the providers agree." if res.verified
            else "Not verified — check the sources below."
        )
    m1, m2 = st.columns(2)
    m1.metric("End of support", res.end_of_support or "—")
    m2.metric("End of life", res.end_of_life or "—")

    cols = st.columns(len(res.providers))
    for col, (name, p) in zip(cols, res.providers.items()):
        with col:
            st.subheader(name)
            if p.error:
                st.error(p.error)
                continue
            st.write(f"**End of support:** {p.end_of_support or '—'}  \n**End of life:** {p.end_of_life or '—'}")
            if p.source:
                badge = ("✅ official" if p.source.official
                         else "☑️ trusted (not the vendor)" if p.source.trusted
                         else "⚠️ may not be official")
                st.markdown(f"[{p.source.title or p.source.url}]({p.source.url}) · {badge}")
            for f, q in p.quotes.items():
                st.caption(f"{f.replace('_', ' ')}:")
                st.markdown(f"> {q}")
            for n in p.notes:
                st.caption(f"Note: {n}")
            st.caption(f"{p.elapsed_s}s")

    st.subheader("Usage")
    rows = [{"Provider": name, "Step": u.step, "Units": f"{u.units} {u.unit}{'s' if u.units != 1 else ''}",
             "Cost": u.cost_label()}
            for name, p in res.providers.items() for u in p.usage]
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.caption("No API calls were made for this lookup.")
    u1, u2, u3 = st.columns(3)
    credits = sum(u.units for p in res.providers.values() for u in p.usage if u.unit == "credit")
    dollars = sum(u.cost_usd or 0 for p in res.providers.values() for u in p.usage)
    u1.metric("SearchAPI credits used", credits)
    u2.metric("Exa cost", f"${dollars:.4f}")
    if "searchapi" in res.providers:
        left = remaining_credits()
        u3.metric("SearchAPI credits left", "—" if left is None else left)

    data = json.dumps(res.to_dict(), indent=2)
    with st.expander("JSON output"):
        st.code(data, language="json")
    st.download_button("Download JSON", data, file_name="lifecycle.json", mime="application/json")
