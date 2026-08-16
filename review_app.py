"""
BRSR Extraction Review Queue — Streamlit UI

Reviews rows the semantic matcher flagged as "needs_review" (medium
confidence). Groups by UNIQUE context string, not by row — reviewing one
context resolves every row that shares it, so a 200+ row document usually
only needs a couple dozen actual decisions.

Confirmed decisions are saved to confirmed_aliases.json, which field_mapper
checks FIRST (before regex, before semantic) on every future run — so a
confirmed wording becomes instant and free forever after, and the review
queue shrinks over time as real variants get covered.

Run:
    streamlit run review_app.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve() / ".." / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ingestion.field_mapper import CONFIRMED_ALIASES_PATH, ExtractionStatus, map_rows
from ingestion.row_parser import extract_data_rows
from ingestion.schema_registry import load_registry

st.set_page_config(page_title="BRSR Review Queue", layout="wide")
st.title("BRSR Extraction Review Queue")


def save_confirmation(context: str, family_id: str) -> None:
    entries = []
    if CONFIRMED_ALIASES_PATH.exists():
        try:
            entries = json.loads(CONFIRMED_ALIASES_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            entries = []
    entries.append({
        "context": context, "family_id": family_id,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    })
    CONFIRMED_ALIASES_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


extracted_dir = Path("data/extracted")
available_files = sorted(extracted_dir.glob("*.json")) if extracted_dir.exists() else []

if not available_files:
    st.warning(f"No extracted JSON files found in {extracted_dir}. Run the extraction pipeline first.")
    st.stop()

selected = st.sidebar.selectbox("Document", available_files, format_func=lambda p: p.name)
registry = load_registry()

with st.spinner("Loading and mapping document (first run downloads the embedding model, ~80MB)..."):
    data = json.loads(selected.read_text(encoding="utf-8"))
    rows = extract_data_rows(data)
    mapped = map_rows(rows, registry)

accept_count = sum(1 for m in mapped if m.status == ExtractionStatus.ACCEPT)
needs_review = [m for m in mapped if m.reason == "needs_review"]

context_groups: dict[str, list] = {}
for m in needs_review:
    context_groups.setdefault(m.provenance.context, []).append(m)
context_list = list(context_groups.keys())

st.sidebar.metric("Total rows", len(mapped))
st.sidebar.metric("Auto-accepted", accept_count)
st.sidebar.metric("Needs review (unique contexts)", len(context_list))
st.sidebar.metric("Rows covered by review", sum(len(g) for g in context_groups.values()))

session_key = f"review_idx_{selected.name}"
if session_key not in st.session_state:
    st.session_state[session_key] = 0
idx = st.session_state[session_key]

if not context_list:
    st.success("Nothing flagged for review in this document — every ambiguous row was either auto-accepted or is confidently unmapped noise.")
elif idx >= len(context_list):
    st.success(f"All {len(context_list)} flagged contexts reviewed for this document! 🎉 Re-run field_mapper.py to see the updated ACCEPT count.")
else:
    context = context_list[idx]
    group = context_groups[context]
    example = group[0]

    st.progress(idx / len(context_list))
    st.caption(f"Reviewing {idx + 1} of {len(context_list)} — this decision applies to {len(group)} row(s)")

    st.subheader("Disclosure context (as extracted from the PDF)")
    st.code(context, language=None)

    conf_pct = f"{example.confidence:.0%}" if example.confidence else "?"
    st.subheader(f"Suggested family: `{example.family_id}`  (confidence: {conf_pct})")
    st.write("Preview of how values would be labeled if confirmed:")
    st.json(example.fields)

    with st.expander(f"Show all {len(group)} affected row(s)"):
        for m in group:
            st.text(f"[page {m.row.page}] label={m.row.label!r}  values={m.row.values}")

    col1, col2, col3 = st.columns([2, 3, 1])
    with col1:
        if st.button(f"✅ Confirm as {example.family_id}", type="primary", use_container_width=True):
            save_confirmation(context, example.family_id)
            st.session_state[session_key] += 1
            st.rerun()
    with col2:
        family_ids = [f.family_id for f in registry.families]
        alt_family = st.selectbox("Not that? Pick the correct family:", [""] + family_ids, key=f"alt_{idx}")
        if st.button("Confirm this instead", use_container_width=True) and alt_family:
            save_confirmation(context, alt_family)
            st.session_state[session_key] += 1
            st.rerun()
    with col3:
        if st.button("⏭️ Skip", use_container_width=True):
            st.session_state[session_key] += 1
            st.rerun()