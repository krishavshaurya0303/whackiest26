"""
app.py - the website (built with Streamlit: a website written entirely in Python).

Run it with:   streamlit run app.py

Screen layout:
  left  = "Your product" form
  right = live Agent Trace (each step appears as the agent works)
  below = Repair Passport + pre-filled service form + extras (voice, complaint letter)
"""
import html
import json
import os
import pathlib

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()            # read .env BEFORE importing agent/llm, so the provider setting is picked up
import agent             # noqa: E402
from llm import ask_llm  # noqa: E402

APP_NAME = "MendMap"     # <- change the product name here (one line)
TAGLINE = "From broken to fixed. Without the guesswork."
BASE = pathlib.Path(__file__).parent

st.set_page_config(page_title=APP_NAME, layout="wide")
demo = json.loads((BASE / "demo_case.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------- look & feel
# Same "Peach and Steel" design as our AlgoViz project: paper background, steel header band,
# peach accent, Atkinson Hyperlegible (made for readability) + IBM Plex Mono for numbers.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root { --paper:#eadfc8; --card:#f3ebda; --sunk:#e4d8bf; --line:#c4b598; --steel:#3f5a62;
        --ink:#2b3f45; --ink2:#4a5b60; --ink3:#58666b; --peach:#fe8254; --peach-ink:#a8441f; }
html, body, [class*="css"], .stMarkdown, input, textarea, button, label {
    font-family: "Atkinson Hyperlegible", "Segoe UI", sans-serif !important; }
code, .mono { font-family: "IBM Plex Mono", monospace !important; }
.block-container { padding-top: 1.2rem; max-width: 1280px; }
header[data-testid="stHeader"] { background: transparent; }

/* steel header band with the brand, like the AlgoViz sidebar */
.mm-hero { background: var(--steel); color: var(--paper); border-radius: 14px; padding: 22px 26px;
           display: flex; justify-content: space-between; align-items: center; gap: 20px; flex-wrap: wrap; }
.mm-brand { display: flex; align-items: center; gap: 14px; }
.mm-logo { width: 44px; height: 44px; border-radius: 10px; background: var(--peach); display: grid;
           place-items: center; font-size: 22px; }
.mm-name { font-size: 26px; font-weight: 700; line-height: 1.1; }
.mm-sub { color: #b9c7c9; font-size: 14px; }
.mm-flow { display: flex; gap: 6px; flex-wrap: wrap; font-family: "IBM Plex Mono", monospace; font-size: 12px; }
.mm-flow span { border: 1px solid rgba(234,223,200,.35); border-radius: 6px; padding: 4px 9px; color: var(--paper); }
.mm-flow b { color: var(--peach); font-weight: 500; }

/* section headings: small caps eyebrow in accent ink */
.mm-eyebrow { color: var(--peach-ink); font-size: 12px; font-weight: 700; letter-spacing: .1em;
              text-transform: uppercase; margin: 6px 0 2px; }

/* cards = Streamlit bordered containers */
div[data-testid="stVerticalBlockBorderWrapper"] { background: var(--card); border-color: var(--line) !important;
                                                  border-radius: 10px !important; }

/* buttons: primary = peach with dark ink (as in AlgoViz), others = paper with a border */
.stButton > button, .stDownloadButton > button { border-radius: 8px; border: 1px solid var(--line);
    background: var(--card); color: var(--ink); font-weight: 700; }
.stButton > button:hover, .stDownloadButton > button:hover { background: #d9cbad; border-color: var(--steel); color: var(--ink); }
.stButton > button[kind="primary"] { background: var(--peach); border-color: var(--peach); color: var(--ink); }
.stButton > button[kind="primary"]:hover { background: #ff9a74; border-color: #ff9a74; color: var(--ink); }

/* inputs sit slightly sunk into the card */
.stTextInput input, .stTextArea textarea, .stNumberInput input, div[data-baseweb="select"] > div {
    background: var(--sunk) !important; border-color: var(--line) !important; }

/* Agent Trace rows */
.mm-step { display: flex; gap: 10px; align-items: baseline; padding: 6px 0; border-bottom: 1px solid var(--line); }
.mm-step .n { font-family: "IBM Plex Mono", monospace; color: var(--peach-ink); min-width: 22px; }
.mm-step .t { font-weight: 700; }
.mm-step .d { color: var(--ink2); }
.mm-step.needs_you .t { color: var(--peach-ink); }
.mm-step.failed .t { color: #b5452e; }
.mm-src { font-family: "IBM Plex Mono", monospace; font-size: 11.5px; color: var(--ink3); word-break: break-all; }

/* evidence label chips */
.mm-chip { padding: 2px 9px; border-radius: 6px; font-weight: 700; font-size: 12.5px; border: 1px solid; }
.mm-quote { border-left: 3px solid var(--steel); background: var(--sunk); padding: 6px 10px; border-radius: 0 6px 6px 0;
            margin: 4px 0 2px; color: var(--ink); }
.mm-note { font-size: 13px; color: var(--ink3); }
.mm-cost { font-family: "IBM Plex Mono", monospace; font-weight: 500; color: var(--ink); }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="mm-hero">
  <div class="mm-brand"><div class="mm-logo">🔧</div>
    <div><div class="mm-name">{APP_NAME}</div><div class="mm-sub">{TAGLINE}</div></div></div>
  <div class="mm-flow"><span><b>1</b> Identify</span><span><b>2</b> Investigate</span><span><b>3</b> Verify</span>
    <span><b>4</b> Decide</span><span><b>5</b> Fix</span></div>
</div>""", unsafe_allow_html=True)
st.write("")


def step_html(s):
    """One Agent Trace row: number, title, detail, source URL."""
    src = f"<div class='mm-src'>{html.escape(s['source'])}</div>" if s["source"] else ""
    return (f"<div class='mm-step {s['status']}'><span class='n'>{s['n']:02d}</span><div>"
            f"<span class='t'>{html.escape(s['title'])}</span> <span class='d'>· {html.escape(s['detail'])}</span>"
            f"{src}</div></div>")

left, right = st.columns([1, 1.4], gap="large")

# ---------------------------------------------------------------- 1. the input form
with left, st.container(border=True):
    st.markdown("<div class='mm-eyebrow'>Step 1 · Your product</div>", unsafe_allow_html=True)
    brand = st.text_input("Brand", demo["brand"])
    model = st.text_input("Model number", demo["model"])
    category = st.text_input("Product type", demo["category"])
    error_code = st.text_input("Error code", demo["error_code"])
    purchase = st.text_input("Bought on (YYYY-MM)", demo["purchase_date"])
    years = st.number_input("Warranty (years, from official page)", 0, 10, int(demo["warranty_years"]))
    problem = st.text_area("What's wrong?", demo["problem"])
    with st.expander("Sources the agent may visit (one URL per line)"):
        sources = st.text_area("Official support pages / manual PDFs", "\n".join(demo["official_sources"]))
        part_name = st.text_input("Likely part", demo.get("part_name", ""))
        part_sources = st.text_area("Part shop pages", "\n".join(demo.get("part_sources", [])))
    go = st.button("Start investigation", type="primary", use_container_width=True)
    st.caption("Reads official sources first. Never submits anything without you.")

# ---------------------------------------------------------------- 2. run the agent with a live trace
with right, st.container(border=True):
    st.markdown("<div class='mm-eyebrow'>Step 2 · Agent Trace - every site the agent visits</div>",
                unsafe_allow_html=True)
    if go:
        case = dict(demo)  # keep extra fields (prices, customer name) from demo_case.json
        case.update(brand=brand, model=model, category=category, error_code=error_code,
                    purchase_date=purchase, warranty_years=years, problem=problem, part_name=part_name,
                    official_sources=[u.strip() for u in sources.splitlines() if u.strip()],
                    part_sources=[u.strip() for u in part_sources.splitlines() if u.strip()])
        with st.status("Agent working...", expanded=True) as status:
            def show(s):
                st.markdown(step_html(s), unsafe_allow_html=True)
                if s.get("shot"):   # what the agent's browser saw on this page
                    st.image(s["shot"], width=440)
            st.session_state.passport = agent.run(case, on_step=show)
            # keep the trace open after the run so every step + screenshot stays visible
            status.update(label="Done - paused for your confirmation", state="complete", expanded=True)
    elif "passport" in st.session_state:
        for s in st.session_state.passport["trace"]:
            st.markdown(step_html(s), unsafe_allow_html=True)
    else:
        st.markdown("<div class='mm-quote'>Fill in your product and press <b>Start investigation</b>. "
                    "Each page the agent opens will appear here with a screenshot.</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------- 3. the Repair Passport
p = st.session_state.get("passport")
if p:
    st.write("")
    c = p["case"]
    st.markdown(f"<div class='mm-eyebrow'>Step 3 · Repair Passport</div>"
                f"<h2 style='margin:0 0 8px'>{html.escape(c['brand'])} {html.escape(c['model'])} · "
                f"<span class='mono'>{html.escape(c['error_code'])}</span></h2>", unsafe_allow_html=True)
    d, w, r = st.columns([1.5, 1, 1.2], gap="medium")

    with d, st.container(border=True):
        st.markdown("**Diagnosis** - every claim has a source")
        if not p["findings"]:
            st.write("No evidence found. Add an official source and run again.")
        for f in p["findings"]:
            bg, fg = agent.COLORS.get(f["label"], ("#d9cbad", "#2b3f45"))
            quote = ""
            if f.get("excerpt"):
                page = f" · p.{f['page']}" if f.get("page") else ""
                quote = (f"<div class='mm-quote'>“{html.escape(f['excerpt'])}”</div>"
                         f"<div class='mm-src'>{html.escape(f.get('source', ''))}{page}</div>")
            st.markdown(f"<div style='margin:10px 0'><span class='mm-chip' style='background:{bg};color:{fg};"
                        f"border-color:{fg}55'>{f['label']}</span> <b>{html.escape(f['title'])}</b>"
                        f"<div style='color:var(--ink2)'>{html.escape(f['why'])}</div>{quote}</div>",
                        unsafe_allow_html=True)

    with w, st.container(border=True):
        st.markdown("**Warranty**")
        (st.success if p["warranty"]["inside"] else st.warning)(
            f"{p['warranty']['status']} (until {p['warranty']['ends']})")
        st.caption(p["warranty"]["note"])

    with r, st.container(border=True):
        st.markdown("**Repair or replace?**")
        for o in p["options"]:
            st.markdown(f"<div style='margin:8px 0'><span class='mm-cost'>{html.escape(o['cost'])}</span> · "
                        f"<b>{html.escape(o['name'])}</b><div class='mm-note'>{html.escape(o['note'])}</div></div>",
                        unsafe_allow_html=True)

    st.error("Unplug before any check. Anything marked **Unsafe** goes to an authorised technician.")

    st.markdown("<div class='mm-eyebrow'>Step 4 · Service request - pre-filled, NOT submitted</div>",
                unsafe_allow_html=True)
    if p["form_screenshot"] and pathlib.Path(p["form_screenshot"]).exists():
        st.image(p["form_screenshot"], caption="Stopped before Submit - review and submit yourself.")

    a, b = st.columns(2)
    a.download_button("Download Repair Passport (HTML)", (agent.OUT / "passport.html").read_bytes(),
                      "repair_passport.html", "text/html", use_container_width=True)
    b.download_button("Download Passport data (JSON)", (agent.OUT / "passport.json").read_bytes(),
                      "repair_passport.json", "application/json", use_container_width=True)

    # ------------------------------------------------------------ extra: hear the Passport (ElevenLabs)
    st.divider()
    x, y = st.columns(2, gap="large")
    with x:
        st.markdown("**Hear it (ElevenLabs voice)**")
        lang = st.selectbox("Language", ["English", "Hindi", "Kannada"])
        if st.button("Speak the Passport", use_container_width=True):
            top = p["findings"][0] if p["findings"] else {"label": "Unknown", "title": "no clear cause yet"}
            summary = (f"Your {c['brand']} {c['model']} shows error {c['error_code']}. "
                       f"Most likely: {top['title']}, marked {top['label']}. "
                       f"Warranty: {p['warranty']['status']}. Cheapest option: {p['options'][0]['name']}.")
            if lang != "English":
                try:
                    summary = ask_llm(f"Translate into simple spoken {lang}. Reply with only the translation:\n{summary}")
                except Exception:
                    st.caption("No AI configured - speaking in English.")
            key, voice = os.getenv("ELEVENLABS_API_KEY"), os.getenv("ELEVENLABS_VOICE_ID")
            if key and voice:
                res = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                                    headers={"xi-api-key": key, "Content-Type": "application/json"},
                                    json={"text": summary, "model_id": "eleven_multilingual_v2"}, timeout=60)
                if res.ok:
                    st.audio(res.content, format="audio/mpeg")
                else:
                    st.warning(f"ElevenLabs error {res.status_code}")
            else:
                st.info("Add ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID to .env to hear this.")
            st.caption(summary)

    # ------------------------------------------------------------ extra: escalate if the brand refuses
    with y:
        st.markdown("**Brand refused or overcharged? Escalate**")
        issue = st.text_input("What happened?", "Service centre refused warranty repair")
        if st.button("Draft complaint letter", use_container_width=True):
            facts = (f"Product: {c['brand']} {c['model']}, bought {c['purchase_date']}, "
                     f"warranty status: {p['warranty']['status']} (until {p['warranty']['ends']}). "
                     f"Fault: error {c['error_code']} - {c['problem'].rstrip('.')}. Issue: {issue.rstrip('.')}.")
            try:
                letter = ask_llm("Write a short, polite, firm consumer complaint letter to the brand's customer care "
                                 "using ONLY these facts. Leave [blanks] for anything unknown. Do not cite laws "
                                 f"you are not sure of.\n{facts}")
            except Exception:
                letter = (f"To: {c['brand']} Customer Care\n\nSubject: Complaint - {c['brand']} {c['model']}\n\n"
                          f"{facts}\n\nI request a repair or resolution within [7] days. If unresolved, I will "
                          f"escalate to the National Consumer Helpline (1915).\n\nRegards,\n[Your name]\n[Phone]")
            st.text_area("Draft (edit before sending)", letter, height=260)
