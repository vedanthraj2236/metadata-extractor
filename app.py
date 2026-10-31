import os
import json
import tempfile
import pandas as pd
import streamlit as st
from extractor import extract

st.set_page_config(page_title="Metadata Extractor", page_icon="🔍", layout="wide")

# ---------- Custom styling ----------
st.markdown("""
<style>
    .block-container { padding-top: 2rem; max-width: 1100px; }
    .hero {
        background: linear-gradient(135deg, #4f46e5, #06b6d4);
        padding: 2.2rem 2rem; border-radius: 18px; color: white;
        margin-bottom: 1.5rem;
    }
    .hero h1 { margin: 0; font-size: 2.4rem; color: white; }
    .hero p { margin: .4rem 0 0; font-size: 1.05rem; opacity: .92; }
    .card {
        background: rgba(128,128,128,.10); border: 1px solid rgba(128,128,128,.25);
        border-radius: 14px; padding: 1rem 1.2rem;
    }
    .card .label { font-size: .8rem; opacity: .7; text-transform: uppercase; letter-spacing: .05em; }
    .card .value { font-size: 1.25rem; font-weight: 600; word-break: break-all; }
    .privacy-ok { color: #22c55e; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>🔍 Metadata Extractor</h1>
    <p>Discover the hidden information inside your images, PDFs and Word documents.</p>
</div>
""", unsafe_allow_html=True)

# ---------- Sidebar ----------
with st.sidebar:
    st.header("ℹ️ About")
    st.write("Upload a file to read its metadata. Files are processed temporarily and never stored.")
    st.subheader("Supported formats")
    st.markdown("- 🖼️ JPG, JPEG, PNG\n- 📄 PDF\n- 📝 DOCX")
    st.subheader("Why it matters")
    st.write("Metadata can reveal who created a file, with what software, and even "
             "where a photo was taken.")

# ---------- Helpers ----------
SENSITIVE_KEYS = ["GPS Location", "Author", "Last Modified By", "Creator",
                  "Producer", "Make", "Model", "Software", "Artist"]

def card(label, value):
    st.markdown(f'<div class="card"><div class="label">{label}</div>'
                f'<div class="value">{value}</div></div>', unsafe_allow_html=True)

def analyze(uploaded_file):
    suffix = os.path.splitext(uploaded_file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name
    try:
        result = extract(tmp_path)
    finally:
        os.remove(tmp_path)
    result["File Name"] = uploaded_file.name
    return result

# ---------- Upload ----------
files = st.file_uploader(
    "Drag and drop your files here",
    type=["jpg", "jpeg", "png", "pdf", "docx"],
    accept_multiple_files=True,
)

if not files:
    st.info("👆 Upload one or more files to get started.")

for f in files:
    result = analyze(f)
    ext = os.path.splitext(f.name)[1].upper().replace(".", "")

    st.markdown(f"## 📁 {f.name}")

    c1, c2, c3, c4 = st.columns(4)
    with c1: card("File type", ext)
    with c2: card("Size", f"{result.get('Size (KB)', '-')} KB")
    with c3: card("Fields found", len(result))
    with c4: card("Pages / Dimensions", result.get("Pages", result.get("Dimensions", "-")))

    st.write("")
    tab1, tab2, tab3 = st.tabs(["📋 Details", "🔒 Privacy check", "{ } Raw JSON"])

    with tab1:
        df = pd.DataFrame({
            "Property": list(result.keys()),
            "Value": [str(v) for v in result.values()],
        })
        search = st.text_input("Search properties", key=f"search_{f.name}",
                               placeholder="e.g. author, date, camera...")
        if search:
            df = df[df["Property"].str.contains(search, case=False)
                    | df["Value"].str.contains(search, case=False)]
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab2:
        found = {k: v for k, v in result.items()
                 if k in SENSITIVE_KEYS and str(v) not in ("", "None")}
        if "GPS Location" in found:
            st.error("📍 This file contains GPS coordinates. Anyone who gets it can see where it was created.")
            st.markdown(f"[Open location on Google Maps]({found['GPS Location']})")
        if found:
            st.warning("These fields may reveal personal information:")
            st.table(pd.DataFrame({"Field": list(found.keys()),
                                   "Value": [str(v) for v in found.values()]}))
        else:
            st.markdown('<p class="privacy-ok">✅ No obvious personal information found.</p>',
                        unsafe_allow_html=True)

    with tab3:
        st.json(result)
        st.download_button(
            "⬇️ Download as JSON",
            json.dumps(result, indent=2, default=str),
            file_name=f"{os.path.splitext(f.name)[0]}_metadata.json",
            mime="application/json",
            key=f"dl_{f.name}",
        )

    st.divider()