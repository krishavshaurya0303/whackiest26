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
import streamlit.components.v1 as components
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
# Colours = Black Pearl #04141E, Turquoise Sea #64DBE8, Flush Orange #FF6D04. Motion inspired by the wHACKiest 2026 site (not a copy): heavy display type,
# a square accent full stop, blue mono labels, and bold "lift with a hard shadow" hover motion on cards.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@112,700;112,800;112,900&family=Space+Grotesk:wght@500;600;700&family=Space+Mono:wght@400;700&display=swap');
:root { /* Palette: Black Pearl #04141E, Turquoise Sea #64DBE8, Flush Orange #FF6D04 */
        --pink:#ff6d04;  /* flush orange  - fills: button, trace blocks, hover shadow */
        --cyan:#64dbe8;  /* turquoise sea - accents: numbers, Verified, hover edges   */
        --purple:#3fa7b4; /* deeper turquoise - labels, glow                          */
        --peach:#ff9a4d; /* lighter orange - prices, Likely                          */
        --night:#04141e; /* black pearl - background                                 */
        --paper:#04141e; --card:rgba(10,36,50,.72); --sunk:#0b2633; --grid:transparent; --line:#163a48;
        --edge:#1d4656; --shade:#010a0f;
        --ink:#eaf6f8; --ink2:#b5cdd3; --ink3:#7b98a1;
        --orange:#ff6d04; --orange-ink:#64dbe8;
        --blue:#3fa7b4; --blue-line:#1d4656; --amber:#ff9a4d; --green:#64dbe8;
        --flow: cubic-bezier(.22, 1, .36, 1);            /* soft glide-and-settle */
        --spring: cubic-bezier(.34, 1.56, .64, 1); }     /* tiny overshoot, feels alive */

/* black pearl night: turquoise fog at the top, an orange neon glow along the bottom */
.stApp { background-color: var(--night); background-attachment: fixed;
         background-image: radial-gradient(ellipse 80% 50% at 10% -10%, rgba(100,219,232,.22), transparent 70%),
                           radial-gradient(ellipse 70% 45% at 95% 0%, rgba(63,167,180,.14), transparent 70%),
                           radial-gradient(ellipse 110% 50% at 50% 118%, rgba(255,109,4,.38), rgba(255,154,77,.08) 45%, transparent 75%); }
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

/* dot-matrix background (drawn by the script below): sits behind everything, content stays on top */
#mm-dots { position: fixed; inset: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 1; }
.stApp [data-testid="stMain"] { position: relative; z-index: 2; }
header[data-testid="stHeader"] { z-index: 3; }

/* cards: a soft spotlight follows the mouse inside the card (colour set in the neon section) */
.stApp [class*="st-key-card"] { background-image: radial-gradient(320px circle at var(--mx, -400px) var(--my, -400px),
                                                  rgba(100,219,232,.13), transparent 60%); }

/* ---------------- neon touches (turquoise + orange glows) ---------------- */
/* title: white -> turquoise gradient letters with a soft glow, orange full stop */
.stApp .mm-display .w { background: linear-gradient(95deg, #ffffff 0%, #c9f3f7 40%, var(--cyan) 100%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
    filter: drop-shadow(0 0 18px rgba(100,219,232,.35)); }
.mm-dot { background: var(--pink); box-shadow: 0 0 14px var(--pink), 0 0 28px rgba(255,109,4,.55); }
.mm-hero { border-bottom: 1.5px solid transparent;
    border-image: linear-gradient(90deg, var(--cyan), var(--purple) 45%, var(--pink) 80%, transparent) 1; }

/* glassy neon cards: see-through panel, glowing edge on hover */
.stApp [class*="st-key-card"] { backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
    border-color: rgba(63,167,180,.35) !important; box-shadow: 4px 4px 0 var(--shade), 0 0 0 rgba(0,0,0,0); }
.stApp [class*="st-key-card"]:hover { border-color: var(--cyan) !important;
    box-shadow: 9px 9px 0 var(--pink), 0 0 34px rgba(100,219,232,.25); }
.stApp [class*="st-key-card"] { background-image: radial-gradient(340px circle at var(--mx, -400px) var(--my, -400px),
                                                  rgba(63,167,180,.20), transparent 60%); }

/* inputs: glow cyan when focused */
.stTextInput > div:focus-within, .stTextArea > div:focus-within, .stNumberInput > div > div:focus-within {
    border-color: var(--cyan) !important; box-shadow: 0 0 0 3px rgba(100,219,232,.18), 0 0 18px rgba(100,219,232,.25); }

/* main button: flush orange neon */
.stButton > button[kind="primary"] { background: var(--pink); border-color: transparent;
    color: var(--night); box-shadow: 3px 3px 0 var(--shade), 0 0 22px rgba(255,109,4,.45); }
.stButton > button[kind="primary"] p { color: var(--night); font-weight: 800; }
.stButton > button[kind="primary"]:hover { background: #ff8a33; color: var(--night);
    box-shadow: 6px 6px 0 var(--cyan), 0 0 36px rgba(255,109,4,.7); }
.stButton > button:hover, .stDownloadButton > button:hover { border-color: var(--cyan); }

/* header step chips */
.mm-flow span { border-color: rgba(63,167,180,.45); }
.mm-flow b { color: var(--cyan); text-shadow: 0 0 10px rgba(100,219,232,.6); }
.mm-flow span:hover { background: var(--pink); box-shadow: 6px 6px 0 var(--cyan), 0 0 20px rgba(255,109,4,.6); }
.mm-flow span:hover, .mm-flow span:hover b { color: var(--night); text-shadow: none; }

/* labels glow turquoise */
.mm-label, .mm-eyebrow { color: var(--purple); text-shadow: 0 0 12px rgba(63,167,180,.45); }

/* Agent Trace timeline: orange blocks, an orange -> turquoise line, turquoise for "your turn" */
.mm-step .n { background: var(--pink); color: var(--night); border-color: transparent;
              box-shadow: 3px 3px 0 var(--shade), 0 0 16px rgba(255,109,4,.55); }
.mm-step:hover .n { box-shadow: 5px 5px 0 var(--cyan), 0 0 22px rgba(255,109,4,.8); }
.mm-step::before { background: linear-gradient(var(--pink), var(--purple)); box-shadow: 0 0 8px rgba(255,109,4,.6); }
.mm-step.needs_you .n { background: var(--cyan); color: var(--night); box-shadow: 3px 3px 0 var(--shade), 0 0 18px rgba(100,219,232,.7); }
.mm-step.needs_you .t { color: var(--cyan); text-decoration: none; }
.mm-step.failed .n { background: var(--peach); }
.mm-src { color: #7fc9d3; }

/* evidence + prices */
.mm-quote { border-left-color: var(--cyan); background: rgba(11,38,51,.85); box-shadow: inset 4px 0 14px -8px var(--cyan); }
.mm-cost { color: var(--peach); text-shadow: 0 0 12px rgba(255,154,77,.45); }
.mm-chip { border-color: currentColor !important; box-shadow: 0 0 12px -2px currentColor; }
[data-testid="stImage"] img:hover { box-shadow: 8px 8px 0 var(--pink), 0 0 30px rgba(100,219,232,.25); }

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

# ---------------------------------------------------------------- background animation (dot field that follows the mouse)
# Streamlit doesn't run <script> tags inside st.markdown, so we use a tiny invisible component.
# Its iframe is on the same origin as the page, so the script can add the cursor to the main page.
components.html("""
<script>
(function () {
  const doc = window.parent.document, win = window.parent;
  if (doc.getElementById('mm-dots')) return;                      // already added (Streamlit reruns)
  if (win.matchMedia('(pointer: coarse)').matches) return;        // touch screens: skip
  if (win.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  // ---- setup: one full-screen canvas behind the page content ----
  const canvas = doc.createElement('canvas'); canvas.id = 'mm-dots';
  doc.body.prepend(canvas);
  const ctx = canvas.getContext('2d');
  const GAP = 18;            // distance between dots (px)
  const R = 240;             // radius of the light around the mouse (px)
  let W, H, dpr, grid;       // grid = the faint dots, drawn once and reused every frame

  function resize() {
    dpr = win.devicePixelRatio || 1; W = win.innerWidth; H = win.innerHeight;
    canvas.width = W * dpr; canvas.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    grid = doc.createElement('canvas'); grid.width = W * dpr; grid.height = H * dpr;
    const g = grid.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.fillStyle = 'rgba(100,219,232,0.08)';
    for (let y = GAP / 2; y < H; y += GAP) for (let x = GAP / 2; x < W; x += GAP) {
      g.beginPath(); g.arc(x, y, 0.8, 0, Math.PI * 2); g.fill();
    }
  }
  win.addEventListener('resize', resize); resize();

  // ---- colours: deep turquoise (edge) -> flush orange -> warm white (centre) ----
  const STOPS = [[63, 167, 180], [255, 109, 4], [255, 226, 190]];
  function colour(k) {                                  // k: 0 at the edge .. 1 at the centre
    const i = k < 0.5 ? 0 : 1, f = k < 0.5 ? k / 0.5 : (k - 0.5) / 0.5, a = STOPS[i], b = STOPS[i + 1];
    return [a[0] + (b[0] - a[0]) * f | 0, a[1] + (b[1] - a[1]) * f | 0, a[2] + (b[2] - a[2]) * f | 0];
  }
  const smooth = (x) => x * x * (3 - 2 * x);           // smoothstep: soft start, soft end

  // ---- state ----
  let mx = W * 0.7, my = H * 0.25;                     // mouse
  let lx = mx, ly = my;                                 // light: chases the mouse slowly (silky trail)
  let power = 0;                                        // light fades in when the mouse moves, out when idle
  let lastMove = 0;
  const ripples = [];                                   // click -> a ring of light spreads out

  doc.addEventListener('mousemove', (e) => { mx = e.clientX; my = e.clientY; lastMove = performance.now(); });
  doc.addEventListener('mousedown', (e) => ripples.push({ x: e.clientX, y: e.clientY, t0: performance.now() }));

  // light one dot (strength k = 0..1)
  function dot(x, y, k, rgb) {
    const [r, g, b] = rgb || colour(k);
    ctx.fillStyle = `rgba(${r},${g},${b},${0.10 + k * 0.9})`;
    ctx.beginPath(); ctx.arc(x, y, 0.9 + k * 2.4, 0, Math.PI * 2); ctx.fill();
  }

  function frame(now) {
    // ease everything: the light glides after the mouse and breathes in/out
    lx += (mx - lx) * 0.06; ly += (my - ly) * 0.06;
    const moving = now - lastMove < 1200;
    power += ((moving ? 1 : 0.6) - power) * 0.04;

    ctx.clearRect(0, 0, W, H);
    ctx.drawImage(grid, 0, 0, W, H);

    // soft turquoise -> orange bloom under the light (no hard edges)
    const bloom = ctx.createRadialGradient(lx, ly, 0, lx, ly, R * 1.6);
    bloom.addColorStop(0, `rgba(63,167,180,${0.30 * power})`);
    bloom.addColorStop(0.45, `rgba(255,109,4,${0.10 * power})`);
    bloom.addColorStop(1, 'rgba(255,109,4,0)');
    ctx.fillStyle = bloom; ctx.fillRect(0, 0, W, H);

    // the light also "breathes" slowly so it never looks frozen
    const breathe = 1 + Math.sin(now / 1400) * 0.06, rad = R * breathe;

    // dots inside the light
    const x0 = Math.max(GAP / 2, Math.floor((lx - rad) / GAP) * GAP + GAP / 2);
    const y0 = Math.max(GAP / 2, Math.floor((ly - rad) / GAP) * GAP + GAP / 2);
    for (let y = y0; y < Math.min(H, ly + rad); y += GAP)
      for (let x = x0; x < Math.min(W, lx + rad); x += GAP) {
        const d = Math.hypot(x - lx, y - ly); if (d > rad) continue;
        dot(x, y, smooth(1 - d / rad) * power);
      }

    // click ripples: a thin ring of light that grows and fades
    for (let i = ripples.length - 1; i >= 0; i--) {
      const rp = ripples[i], age = (now - rp.t0) / 1600;          // 0 -> 1 over 1.6 s
      if (age >= 1) { ripples.splice(i, 1); continue; }
      const front = smooth(age) * 520, fade = 1 - age, band = 26;
      const xa = Math.max(GAP / 2, Math.floor((rp.x - front - band) / GAP) * GAP + GAP / 2);
      const ya = Math.max(GAP / 2, Math.floor((rp.y - front - band) / GAP) * GAP + GAP / 2);
      for (let y = ya; y < Math.min(H, rp.y + front + band); y += GAP)
        for (let x = xa; x < Math.min(W, rp.x + front + band); x += GAP) {
          const off = Math.abs(Math.hypot(x - rp.x, y - rp.y) - front); if (off > band) continue;
          dot(x, y, smooth(1 - off / band) * fade * 0.9, [100, 219, 232]);   // cyan ripple
        }
    }
    win.requestAnimationFrame(frame);
  }
  win.requestAnimationFrame(frame);

  // cards: tell the card under the mouse where the mouse is (for its soft inner spotlight)
  doc.addEventListener('mousemove', (e) => {
    const card = e.target.closest('[class*="st-key-card"]'); if (!card) return;
    const r = card.getBoundingClientRect();
    card.style.setProperty('--mx', (e.clientX - r.left) + 'px'); card.style.setProperty('--my', (e.clientY - r.top) + 'px');
  });
})();
</script>
""", height=0)

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
