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
# Colours = black / burgundy (#6D001A) / white. Motion inspired by the wHACKiest 2026 site (not a copy): heavy display type,
# a square accent full stop, blue mono labels, and bold "lift with a hard shadow" hover motion on cards.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@112,700;112,800;112,900&family=Space+Grotesk:wght@500;600;700&family=Space+Mono:wght@400;700&display=swap');
:root { /* Black / Burgundy / White palette */
        --paper:#000000; --card:#111111; --sunk:#1a1a1a; --grid:transparent; --line:#2a2a2a;
        --edge:#333333; --shade:#2a2a2a;
        --ink:#ffffff; --ink2:#c9c9c9; --ink3:#8a8a8a;
        --orange:#6d001a;        /* burgundy: fills (buttons, step blocks, dot, hover shadow) */
        --orange-ink:#e2365b;    /* brighter burgundy for small accent text on black */
        --blue:#d6d6d6; --blue-line:#333333; --amber:#d9a441; --green:#8fb573;
        --flow: cubic-bezier(.22, 1, .36, 1);            /* soft glide-and-settle */
        --spring: cubic-bezier(.34, 1.56, .64, 1); }     /* tiny overshoot, feels alive */

/* plain dark background */
.stApp { background-color: var(--paper); }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.4rem; max-width: 1280px; }

/* fonts: Space Grotesk for text, Archivo (wide + heavy) for headings, Space Mono for labels/numbers */
.stApp, .stApp p, .stApp div, .stApp span:not([data-testid="stIconMaterial"]), .stApp label,
.stApp input, .stApp textarea, .stApp button { font-family: "Space Grotesk", "Segoe UI", sans-serif; color: var(--ink); }
.stApp h1, .stApp h2, .stApp h3, .stApp .mm-display { font-family: "Archivo", "Arial Black", sans-serif !important;
    font-stretch: 112%; font-weight: 900 !important; letter-spacing: -0.025em; color: var(--ink); }
.stApp code, .stApp .mono, .stApp .mm-label, .stApp .mm-label *, .stApp .mm-step .n, .stApp .mm-src, .stApp .mm-cost {
    font-family: "Space Mono", monospace !important; }

/* bold, readable text */
.stMarkdown p, .stMarkdown li, .stCaption, [data-testid="stCaptionContainer"] { font-size: 17px; font-weight: 500; }
[data-testid="stWidgetLabel"] p { font-size: 15px !important; font-weight: 700 !important; color: var(--ink) !important; }
.stTextInput input, .stTextArea textarea, .stNumberInput input { font-size: 16.5px !important; font-weight: 600 !important;
    color: var(--ink) !important; background: var(--card) !important; }
.stTextInput > div, .stTextArea > div, .stNumberInput > div > div { border: 1.5px solid var(--edge) !important; border-radius: 4px !important; }
.stMarkdown b, .stMarkdown strong { font-weight: 700; }

/* ---------------- header ---------------- */
.mm-hero { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; flex-wrap: wrap;
           padding: 8px 0 22px; border-bottom: 1.5px solid var(--edge); margin-bottom: 18px; }
.stApp .mm-display { font-size: clamp(54px, 8vw, 104px); line-height: .95; margin: 6px 0 0; }
.mm-display .w { display: inline-block; animation: mm-word .9s var(--flow) both; }
.mm-dot { display: inline-block; width: .16em; height: .16em; background: var(--orange-ink); margin-left: .04em;
          animation: mm-dot 1s var(--spring) .55s both, mm-blink 2.4s ease-in-out 1.6s infinite; }
.mm-sub { font-size: 20px; font-weight: 500; color: var(--ink2); max-width: 420px; line-height: 1.5;
          animation: mm-rise .9s var(--flow) .25s both; }
.mm-label { color: var(--blue); font-size: 13.5px; letter-spacing: .22em; text-transform: uppercase; font-weight: 700; }
.mm-flow { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.mm-flow span { border: 1.5px solid var(--edge); background: var(--card); padding: 5px 10px; font-size: 12.5px;
                box-shadow: 3px 3px 0 var(--shade); transition: transform .35s var(--spring), box-shadow .35s var(--spring),
                background .2s; animation: mm-rise .7s var(--flow) both; }
.mm-flow span:nth-child(2) { animation-delay: .08s; } .mm-flow span:nth-child(3) { animation-delay: .16s; }
.mm-flow span:nth-child(4) { animation-delay: .24s; } .mm-flow span:nth-child(5) { animation-delay: .32s; }
.mm-flow span:hover { transform: translate(-3px, -3px); box-shadow: 6px 6px 0 var(--shade); background: var(--orange); }
.mm-flow b { color: var(--orange-ink); }
.mm-flow span:hover b { color: #fff; }

/* section labels: "01 / YOUR PRODUCT" in blue mono */
.mm-eyebrow { font-family: "Space Mono", monospace !important; color: var(--blue); font-size: 13.5px; font-weight: 700;
              letter-spacing: .2em; text-transform: uppercase; margin: 4px 0 6px; animation: mm-rise .7s var(--flow) both; }

/* ---------------- cards: lift with a hard black shadow + orange edge on hover ---------------- */
.stApp [class*="st-key-card"] { background: var(--card); border: 1.5px solid var(--edge) !important; border-radius: 6px !important;
    box-shadow: 4px 4px 0 var(--shade); animation: mm-rise .85s var(--flow) both;
    transition: transform .4s var(--spring), box-shadow .4s var(--spring), border-color .25s; }
.stApp .st-key-card_trace, .stApp .st-key-card_warranty { animation-delay: .12s; }
.stApp .st-key-card_options { animation-delay: .24s; }
.stApp [class*="st-key-card"]:hover { transform: translate(-4px, -4px); box-shadow: 9px 9px 0 var(--orange);
    border-color: var(--orange) !important; }

/* ---------------- buttons ---------------- */
.stButton > button, .stDownloadButton > button { border-radius: 4px; border: 1.5px solid var(--edge); background: var(--card);
    color: var(--ink); box-shadow: 3px 3px 0 var(--shade);
    transition: transform .3s var(--spring), box-shadow .3s var(--spring), background .2s; }
.stButton > button p, .stDownloadButton > button p { font-size: 16.5px; font-weight: 700; letter-spacing: .01em; }
.stButton > button:hover, .stDownloadButton > button:hover { transform: translate(-3px, -3px); box-shadow: 6px 6px 0 var(--orange);
    background: var(--sunk); border-color: var(--ink); color: var(--ink); }
.stButton > button:active, .stDownloadButton > button:active { transform: translate(2px, 2px); box-shadow: 1px 1px 0 var(--shade); }
.stButton > button[kind="primary"] { background: var(--orange); border-color: var(--orange); color: #fff; }
.stButton > button[kind="primary"]:hover { background: #8a0022; color: #fff; }
.stButton > button[kind="primary"]:hover { box-shadow: 6px 6px 0 var(--shade); }

/* ---------------- Agent Trace as a timeline: orange line that draws itself, numbered boxes ---------------- */
.mm-step { position: relative; display: flex; gap: 14px; align-items: flex-start; padding: 8px 0 12px;
           animation: mm-slide .6s var(--flow) both; }
.mm-step::before { content: ""; position: absolute; left: 21px; top: 44px; bottom: -6px; width: 2px; background: var(--orange-ink);
                   transform-origin: top; animation: mm-draw .7s var(--flow) .2s both; }
.mm-step .n { flex: 0 0 auto; width: 44px; height: 36px; display: grid; place-items: center; background: var(--orange); color: #fff;
              border: 1.5px solid var(--edge); box-shadow: 3px 3px 0 var(--shade); font-size: 15px; font-weight: 700;
              animation: mm-pop .55s var(--spring) both; transition: transform .3s var(--spring), box-shadow .3s var(--spring); }
.mm-step:hover .n { transform: translate(-2px, -2px) rotate(-4deg); box-shadow: 5px 5px 0 var(--orange); }
.mm-step .t { font-weight: 700; font-size: 17.5px; }
.mm-step .d { color: var(--ink2); font-weight: 500; font-size: 16px; }
.mm-step.needs_you .n { background: #ffffff; color: #000000; }
.mm-step.needs_you .t { color: #ffffff; text-decoration: underline 2px var(--orange-ink); }
.mm-step.failed .n { background: #e8553e; }
.mm-src { font-size: 12.5px; color: var(--ink3); word-break: break-all; }

/* screenshots: framed like little windows, tilt slightly when hovered */
[data-testid="stImage"] img { border: 1.5px solid var(--edge); border-radius: 4px; box-shadow: 4px 4px 0 var(--shade);
    animation: mm-rise .8s var(--flow) both; transition: transform .4s var(--spring), box-shadow .4s var(--spring); }
[data-testid="stImage"] img:hover { transform: translate(-3px, -3px) rotate(-.6deg); box-shadow: 8px 8px 0 var(--orange); }

/* evidence */
.mm-chip { display: inline-block; padding: 3px 10px; border-radius: 3px; font-weight: 700; font-size: 13.5px;
           border: 1.5px solid var(--edge) !important; box-shadow: 2px 2px 0 var(--shade); animation: mm-pop .55s var(--spring) both; }
.mm-quote { border-left: 4px solid var(--orange-ink); background: var(--sunk); padding: 8px 12px; margin: 6px 0 3px;
            color: var(--ink); font-weight: 600; font-size: 17px; animation: mm-rise .7s var(--flow) both; }
.mm-opt { padding: 8px 10px; margin: 0 -10px; border-radius: 4px; transition: background .25s, transform .35s var(--spring); }
.mm-opt:hover { background: var(--sunk); transform: translateX(6px); }
.mm-note { font-size: 14.5px; font-weight: 500; color: var(--ink2); }
.mm-cost { font-weight: 700; font-size: 18px; color: var(--orange-ink); }

/* ---------------- keyframes ---------------- */
@keyframes mm-rise  { from { opacity: 0; transform: translateY(22px); } to { opacity: 1; transform: none; } }
@keyframes mm-word  { from { opacity: 0; transform: translateY(60%) skewY(6deg); } to { opacity: 1; transform: none; } }
@keyframes mm-slide { from { opacity: 0; transform: translateX(-16px); } to { opacity: 1; transform: none; } }
@keyframes mm-pop   { 0% { opacity: 0; transform: scale(.6); } 100% { opacity: 1; transform: none; } }
@keyframes mm-dot   { 0% { transform: scale(0) rotate(-90deg); } 100% { transform: none; } }
@keyframes mm-blink { 0%, 100% { opacity: 1; } 50% { opacity: .35; } }
@keyframes mm-draw  { from { transform: scaleY(0); } to { transform: scaleY(1); } }

/* sections reveal as you scroll down to them (browsers that support scroll-driven animations) */
@supports (animation-timeline: view()) {
  .stApp [class*="st-key-card"], [data-testid="stImage"] img {
      animation: mm-rise linear both; animation-timeline: view(); animation-range: entry 0% entry 40%; }
}

/* respect people who turn motion off in their OS settings */
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
</style>
""", unsafe_allow_html=True)

# (HTML kept on single lines: Streamlit's markdown turns indented lines into code blocks)
flow = "".join(f"<span><b>{i:02d}</b> {w}</span>" for i, w in
               enumerate(["Identify", "Investigate", "Verify", "Decide", "Fix"], 1))
st.markdown(
    f"<div class='mm-hero'><div>"
    f"<div class='mm-label'>wHACKiest 2026 · Track 2 · Beyond the Browser</div>"
    f"<div class='mm-display' role='heading' aria-level='1'><span class='w'>{APP_NAME}</span><span class='mm-dot'></span></div>"
    f"<div class='mm-flow mm-label'>{flow}</div></div>"
    f"<div class='mm-sub'>{TAGLINE} A browser agent that proves the fix from the manufacturer, then gets it done.</div>"
    f"</div>", unsafe_allow_html=True)
st.write("")


def step_html(s):
    """One Agent Trace row: number, title, detail, source URL."""
    src = f"<div class='mm-src'>{html.escape(s['source'])}</div>" if s["source"] else ""
    return (f"<div class='mm-step {s['status']}'><span class='n'>{s['n']:02d}</span><div>"
            f"<span class='t'>{html.escape(s['title'])}</span> <span class='d'>· {html.escape(s['detail'])}</span>"
            f"{src}</div></div>")

left, right = st.columns([1, 1.4], gap="large")

# ---------------------------------------------------------------- 1. the input form
with left, st.container(border=True, key="card_form"):
    st.markdown("<div class='mm-eyebrow'>01 / Your product</div>", unsafe_allow_html=True)
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
with right, st.container(border=True, key="card_trace"):
    st.markdown("<div class='mm-eyebrow'>02 / Agent trace - every site it visits</div>",
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
    st.markdown(f"<div class='mm-eyebrow'>03 / Repair passport</div>"
                f"<h2 style='margin:0 0 8px'>{html.escape(c['brand'])} {html.escape(c['model'])} · "
                f"<span class='mono'>{html.escape(c['error_code'])}</span></h2>", unsafe_allow_html=True)
    d, w, r = st.columns([1.5, 1, 1.2], gap="medium")

    with d, st.container(border=True, key="card_diagnosis"):
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

    with w, st.container(border=True, key="card_warranty"):
        st.markdown("**Warranty**")
        (st.success if p["warranty"]["inside"] else st.warning)(
            f"{p['warranty']['status']} (until {p['warranty']['ends']})")
        st.caption(p["warranty"]["note"])

    with r, st.container(border=True, key="card_options"):
        st.markdown("**Repair or replace?**")
        for o in p["options"]:
            st.markdown(f"<div class='mm-opt'><span class='mm-cost'>{html.escape(o['cost'])}</span> · "
                        f"<b>{html.escape(o['name'])}</b><div class='mm-note'>{html.escape(o['note'])}</div></div>",
                        unsafe_allow_html=True)

    st.error("Unplug before any check. Anything marked **Unsafe** goes to an authorised technician.")

    st.markdown("<div class='mm-eyebrow'>04 / Service request - pre-filled, NOT submitted</div>",
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
