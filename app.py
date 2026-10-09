"""Streamlit page: `streamlit run app.py`."""

import json

import streamlit as st
from dotenv import load_dotenv

from lifecycle.lookup import lookup

load_dotenv()

st.set_page_config(page_title="Lifecycle Lookup", page_icon="📅", layout="wide")
st.title("Product lifecycle lookup")
st.caption("End-of-life and end-of-support dates, with citations — compared across SearchAPI.io and Exa.")

with st.form("lookup"):
    query = st.text_input("Product and version", placeholder="e.g. Windows Server 2016")
    which = st.radio("Providers", ["Both", "SearchAPI.io", "Exa"], horizontal=True)
    submitted = st.form_submit_button("Look up", type="primary")

if submitted and query.strip():
    providers = {"Both": ("searchapi", "exa"), "SearchAPI.io": ("searchapi",), "Exa": ("exa",)}[which]
    with st.spinner(f"Searching for {query}…"):
        res = lookup(query.strip(), providers)

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

    data = json.dumps(res.to_dict(), indent=2)
    with st.expander("JSON output"):
        st.code(data, language="json")
    st.download_button("Download JSON", data, file_name="lifecycle.json", mime="application/json")
