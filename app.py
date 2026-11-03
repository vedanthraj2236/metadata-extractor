import json
import os

import pandas as pd
import streamlit as st

from extractor import SUPPORTED, clean_file, extract, privacy_report

st.set_page_config(page_title="Metadata Extractor", page_icon="🔍", layout="wide")

LEVEL_COLOR = {"Low": "#1E8E5A", "Medium": "#B87400", "High": "#C62F3B"}
KEY_FIELDS = ["Make", "Model", "DateTimeOriginal", "DateTime", "Software", "Author",
              "Last Modified By", "Creator", "Producer", "Title", "Created",
              "Modified", "CreationDate", "Dimensions", "Pages", "Format"]

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;700;800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400&display=swap');
html, body, [class*="st-"], .stMarkdown { font-family: 'IBM Plex Sans', sans-serif; }
h1, h2, h3, .display { font-family: 'Bricolage Grotesque', sans-serif !important; letter-spacing: -0.02em; }
.block-container { max-width: 1120px; padding-top: 2.5rem; }
header[data-testid="stHeader"] { background: transparent; }

.hero { display: grid; grid-template-columns: 1.15fr 1fr; gap: 2.5rem; align-items: center; margin-bottom: 2rem; }
.hero h1 { font-size: 3.1rem; line-height: 1.04; font-weight: 800; margin: 0 0 1rem; }
.hero p { font-size: 1.12rem; line-height: 1.55; max-width: 34em; margin: 0; color: #3B4658; }
.readout { background: #0E1726; color: #DCE3F0; border-radius: 6px; padding: 1.2rem 1.4rem;
           font-family: 'IBM Plex Mono', monospace; font-size: .86rem; line-height: 1.9; }
.readout .k { color: #8896AE; display: inline-block; width: 8.5em; }
.readout .warn { color: #FF8A94; }
.readout .cap { color: #8896AE; margin-bottom: .4rem; border-bottom: 1px solid #25324A; padding-bottom: .5rem; }
@media (max-width: 800px) { .hero { grid-template-columns: 1fr; } .hero h1 { font-size: 2.3rem; } }

.score { display: flex; align-items: center; gap: 1.2rem; padding: 1.1rem 1.3rem; background: #fff;
         border: 1px solid #D5DAE3; border-left-width: 6px; border-radius: 6px; margin: .6rem 0 1rem; }
.score .num { font-family: 'Bricolage Grotesque', sans-serif; font-size: 2.6rem; font-weight: 800; line-height: 1; }
.score .bar { height: 8px; background: #E9ECF2; border-radius: 4px; overflow: hidden; margin-top: .5rem; width: 260px; max-width: 100%; }
.score .bar > div { height: 100%; }
.facts { display: grid; grid-template-columns: 11em 1fr; gap: .45rem 1rem; }
.facts .k { color: #5A6679; } .facts .v { font-weight: 500; word-break: break-word; }
.hash { font-family: 'IBM Plex Mono', monospace; font-size: .8rem; word-break: break-all; }
button:focus-visible, [role="tab"]:focus-visible { outline: 2px solid #2B4EFF !important; outline-offset: 2px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <div>
    <h1>Find out what your files are telling people.</h1>
    <p>Photos, PDFs and Word documents carry hidden details: who made them, with what, and sometimes exactly where.
       Upload a file to read them, see how exposed you are, and download a clean copy.</p>
  </div>
  <div class="readout">
    <div class="cap">IMG_2041.jpg — what a stranger can read</div>
    <div><span class="k">Device</span>iPhone 14</div>
    <div><span class="k">Taken</span>2026:10:12 18:41:07</div>
    <div><span class="k">Software</span>17.4.1</div>
    <div class="warn"><span class="k">Location</span>12.29581, 76.63938</div>
  </div>
</div>
""", unsafe_allow_html=True)

tab_analyze, tab_about = st.tabs(["Analyze files", "How it works"])


@st.cache_data(show_spinner=False)
def analyze(name, data):
    result = extract(data, name)
    result["privacy"] = privacy_report(result)
    return result


def score_card(p):
    c = LEVEL_COLOR[p["level"]]
    st.markdown(f"""<div class="score" style="border-left-color:{c}">
      <div class="num" style="color:{c}">{p['score']}</div>
      <div><strong>{p['level']} exposure</strong>
        <div style="color:#5A6679">{len(p['findings'])} personal detail(s) found in this file</div>
        <div class="bar"><div style="width:{p['score']}%;background:{c}"></div></div></div>
    </div>""", unsafe_allow_html=True)


def show_file(f, idx):
    r = analyze(f.name, f.getvalue())
    st.subheader(f.name)
    if r["error"]:
        st.error(r["error"])
        return r
    score_card(r["privacy"])
    t1, t2, t3, t4, t5 = st.tabs(["Overview", "All fields", "Privacy details", "Clean copy", "Export"])

    with t1:
        left, right = st.columns([1, 1.4])
        with left:
            if r["kind"] == "image":
                st.image(f.getvalue(), use_container_width=True)
            else:
                st.metric("Size", f"{r['size_kb']} KB")
        with right:
            rows = [(k, r["details"][k]) for k in KEY_FIELDS if k in r["details"]]
            rows.insert(0, ("File size", f"{r['size_kb']} KB"))
            st.markdown('<div class="facts">' + "".join(
                f'<div class="k">{k}</div><div class="v">{v}</div>' for k, v in rows) + "</div>",
                unsafe_allow_html=True)
            st.markdown("**File fingerprints**")
            for k, v in r["hashes"].items():
                st.markdown(f'<div class="hash"><b>{k}</b> {v}</div>', unsafe_allow_html=True)
        if r["gps"]:
            st.markdown("**Where this was created**")
            st.map(pd.DataFrame({"lat": [r["gps"][0]], "lon": [r["gps"][1]]}), zoom=13)

    with t2:
        df = pd.DataFrame({"Field": list(r["details"]), "Value": [str(v) for v in r["details"].values()]})
        q = st.text_input("Search fields", key=f"q{idx}", placeholder="author, date, camera…")
        if q:
            df = df[df.apply(lambda row: q.lower() in (row["Field"] + row["Value"]).lower(), axis=1)]
        st.dataframe(df, use_container_width=True, hide_index=True)

    with t3:
        if r["privacy"]["findings"]:
            st.dataframe(pd.DataFrame(r["privacy"]["findings"]), use_container_width=True, hide_index=True)
        else:
            st.success("No personal details found. This file is safe to share.")

    with t4:
        st.write("Download a copy with names, device details and location removed. "
                 "Your original file is not changed.")
        try:
            data, mime = clean_file(f.getvalue(), f.name)
            base, ext = os.path.splitext(f.name)
            st.download_button("Download clean copy", data, f"{base}_clean{ext}", mime, key=f"c{idx}")
            after = extract(data, f.name)
            st.caption(f"Exposure after cleaning: {privacy_report(after)['score']}/100")
        except Exception as e:
            st.error(f"Could not clean this file: {e}")

    with t5:
        st.json(r["details"], expanded=False)
        st.download_button("Download as JSON", json.dumps(r, indent=2, default=str),
                           f"{os.path.splitext(f.name)[0]}_metadata.json", "application/json", key=f"j{idx}")
    return r


with tab_analyze:
    files = st.file_uploader("Drop files here (JPG, PNG, PDF, DOCX)",
                             type=[e.strip(".") for e in SUPPORTED], accept_multiple_files=True)
    if not files:
        st.info("Add one or more files to begin. Nothing is stored; files are read in memory and discarded.")
    else:
        results = []
        if len(files) > 1:
            st.markdown("### Batch summary")
            summary = []
            for f in files:
                a = analyze(f.name, f.getvalue())
                summary.append({"File": f.name, "Type": (a["kind"] or "?"), "Size (KB)": a["size_kb"],
                                "Fields": len(a["details"]), "Exposure": a["privacy"]["score"],
                                "Level": a["privacy"]["level"]})
            sdf = pd.DataFrame(summary)
            st.dataframe(sdf, use_container_width=True, hide_index=True)
            st.download_button("Download summary (CSV)", sdf.to_csv(index=False), "metadata_summary.csv", "text/csv")
            st.divider()
        for i, f in enumerate(files):
            show_file(f, i)
            st.divider()

with tab_about:
    st.markdown("""
### What is metadata?
Metadata is information stored inside a file next to its visible content. A photo holds its camera model, time and
GPS position (EXIF). A PDF or Word file holds the author, editing software and dates.

### What this tool does
1. **Reads** the metadata from images, PDFs and Word documents.
2. **Scores** how much personal information the file exposes, from 0 to 100.
3. **Maps** the location when a photo has GPS data.
4. **Fingerprints** the file with MD5 and SHA-256 hashes, which forensic work uses to prove a file is unchanged.
5. **Cleans** a copy by removing names, device details and location.

### Good to know
- Messaging apps such as WhatsApp usually strip photo metadata, so test with an original camera photo.
- Social networks remove most metadata, but email, cloud links and direct file transfers keep it.
- Built with Python, Streamlit, Pillow, pypdf and python-docx.
""")