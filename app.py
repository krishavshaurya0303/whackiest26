"""
app.py - the website (built with Streamlit: a website written entirely in Python).

Run it with:   streamlit run app.py

Screen layout:
  left  = "Your product" form
  right = live Agent Trace (each step appears as the agent works)
  below = Repair Passport + pre-filled service form + extras (voice, complaint letter)
"""
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

st.title(APP_NAME)
st.caption(TAGLINE)

left, right = st.columns([1, 1.4], gap="large")

# ---------------------------------------------------------------- 1. the input form
with left:
    st.subheader("1 · Your product")
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
with right:
    st.subheader("2 · Agent Trace")
    if go:
        case = dict(demo)  # keep extra fields (prices, customer name) from demo_case.json
        case.update(brand=brand, model=model, category=category, error_code=error_code,
                    purchase_date=purchase, warranty_years=years, problem=problem, part_name=part_name,
                    official_sources=[u.strip() for u in sources.splitlines() if u.strip()],
                    part_sources=[u.strip() for u in part_sources.splitlines() if u.strip()])
        icon = {"done": "✅", "failed": "⚠️", "needs_you": "⏸️"}
        with st.status("Agent working...", expanded=True) as status:
            def show(s):
                st.write(f"{icon.get(s['status'], '•')} **{s['n']}. {s['title']}** - {s['detail']}")
                if s["source"]:
                    st.caption(s["source"])
            st.session_state.passport = agent.run(case, on_step=show)
            status.update(label="Done - paused for your confirmation", state="complete")
    elif "passport" in st.session_state:
        for s in st.session_state.passport["trace"]:
            st.write(f"**{s['n']}. {s['title']}** - {s['detail']}")
    else:
        st.info("Fill in your product and press **Start investigation**.")

# ---------------------------------------------------------------- 3. the Repair Passport
p = st.session_state.get("passport")
if p:
    st.divider()
    c = p["case"]
    st.subheader(f"Repair Passport · {c['brand']} {c['model']} · {c['error_code']}")
    d, w, r = st.columns(3, gap="large")

    with d:
        st.markdown("**Diagnosis**")
        if not p["findings"]:
            st.write("No evidence found. Add an official source and run again.")
        for f in p["findings"]:
            bg, fg = agent.COLORS.get(f["label"], ("#E6E9EC", "#3D4650"))
            st.markdown(f"<span style='background:{bg};color:{fg};padding:2px 9px;border-radius:99px;"
                        f"font-weight:700;font-size:13px'>{f['label']}</span> **{f['title']}**",
                        unsafe_allow_html=True)
            st.write(f["why"])
            if f.get("excerpt"):
                st.caption(f"“{f['excerpt']}” - {f.get('source', '')}"
                           f"{' p.' + str(f['page']) if f.get('page') else ''}")

    with w:
        st.markdown("**Warranty**")
        (st.success if p["warranty"]["inside"] else st.warning)(
            f"{p['warranty']['status']} (until {p['warranty']['ends']})")
        st.caption(p["warranty"]["note"])

    with r:
        st.markdown("**Repair or replace?**")
        for o in p["options"]:
            st.write(f"**{o['cost']}** · {o['name']}")
            st.caption(o["note"])

    st.error("Unplug before any check. Anything marked **Unsafe** goes to an authorised technician.")

    st.markdown("**Service request (pre-filled, NOT submitted)**")
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
                     f"Fault: error {c['error_code']} - {c['problem']}. Issue: {issue}.")
            try:
                letter = ask_llm("Write a short, polite, firm consumer complaint letter to the brand's customer care "
                                 "using ONLY these facts. Leave [blanks] for anything unknown. Do not cite laws "
                                 f"you are not sure of.\n{facts}")
            except Exception:
                letter = (f"To: {c['brand']} Customer Care\n\nSubject: Complaint - {c['brand']} {c['model']}\n\n"
                          f"{facts}\n\nI request a repair or resolution within [7] days. If unresolved, I will "
                          f"escalate to the National Consumer Helpline (1915).\n\nRegards,\n[Your name]\n[Phone]")
            st.text_area("Draft (edit before sending)", letter, height=260)
