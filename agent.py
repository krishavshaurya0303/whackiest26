"""
agent.py - MendMap's browser agent.

Memory hook: IDENTIFY -> INVESTIGATE -> VERIFY -> DECIDE -> FIX

  1 IDENTIFY     pin down the exact product (brand + model + error code)
  2 INVESTIGATE  open official support pages / manual PDFs in a real browser (Playwright)
  3 VERIFY       AI labels each finding Verified / Likely / Unknown / Unsafe,
                 and we CHECK that every quote really exists on the source page
  4 DECIDE       warranty status + part price + repair-vs-replace options
  5 FIX          pre-fill the service request form and STOP before Submit (the user submits)

Every step is logged into the "Agent Trace", so the user sees exactly what the agent did.
"""
import asyncio
import datetime
import html
import io
import json
import hashlib
import pathlib
import re
import sys

import requests
from pypdf import PdfReader

from llm import PROVIDER, ask_llm

# Windows + Streamlit + Playwright needs this event-loop setting, otherwise Playwright crashes
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

BASE = pathlib.Path(__file__).parent
CACHE = BASE / "cache"      # every page we read is saved here -> offline fallback for the demo
OUT = BASE / "outputs"      # screenshots + exported passports
CACHE.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Words that mean "do NOT do this yourself - call a technician"
UNSAFE_WORDS = ["mains wiring", "live wire", "capacitor", "control board", "pcb", "refrigerant",
                "gas leak", "compressor", "swollen battery", "motor wiring", "high voltage"]

STOPWORDS = {"the", "and", "after", "ends", "shows", "with", "that", "this", "stays", "display",
             "error", "code", "not", "for", "from", "are", "was", "has", "have", "when"}


# ---------------------------------------------------------------- 2. INVESTIGATE helpers

def slug(url: str) -> str:
    """Turn a URL into a short, safe file name for the cache (short = no Windows path-length errors)."""
    readable = re.sub(r"[^a-zA-Z0-9]+", "_", url)[-40:]
    return readable + "_" + hashlib.md5(url.encode()).hexdigest()[:8]


SHOTS = OUT / "shots"       # one screenshot per web page the agent opens
SHOTS.mkdir(exist_ok=True)


def shot_path(url: str) -> pathlib.Path:
    return SHOTS / (slug(url) + ".png")


def fetch_text(url: str):
    """
    Read one source and return (text, how).
      - 'local:path/to/file.txt'  -> read a local text file (use if a site blocks bots)
      - '...pdf'                  -> download the PDF and extract text page by page
      - anything else             -> open in a real headless Chrome with Playwright
    If the live fetch fails, fall back to the cached copy from an earlier run.
    """
    if url.startswith("local:"):
        return (BASE / url[len("local:"):]).read_text(encoding="utf-8"), "local file"

    cache_file = CACHE / (slug(url) + ".txt")
    try:
        if url.lower().split("?")[0].endswith(".pdf"):
            r = requests.get(url, timeout=30, headers={"User-Agent": BROWSER_UA})
            r.raise_for_status()
            reader = PdfReader(io.BytesIO(r.content))
            # keep page numbers so the Passport can say "manual p.12"
            text = "\n".join(f"[page {i + 1}]\n{p.extract_text() or ''}" for i, p in enumerate(reader.pages))
        else:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=BROWSER_UA)
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)           # let JavaScript-built content appear
                # Privacy-first: decline optional cookies if a banner shows, then take a screenshot
                # of what the agent "sees" - shown in the Agent Trace so judges watch it browse
                try:
                    page.get_by_text("Decline all", exact=True).first.click(timeout=1500)
                    page.wait_for_timeout(500)
                except Exception:
                    pass
                # hide "Delivering to <area PIN>" so the screenshot never shows the user's location
                page.evaluate("""() => {
                    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    let n; while ((n = w.nextNode())) {
                        if (/Delivering to|Deliver to/i.test(n.textContent)) n.textContent = 'Delivering to [hidden]';
                        else if (/^\\s*\\d{6}\\s*$/.test(n.textContent)) n.textContent = '';
                    }
                }""")
                page.screenshot(path=str(shot_path(url)))
                # Prefer the page's <main> content: skips menus, headers and cookie banners
                text = ""
                if page.locator("main").count() > 0:
                    text = page.locator("main").first.inner_text()
                if len(text.strip()) < 200:
                    text = page.inner_text("body")

                browser.close()
        if len(text.strip()) < 50:
            raise ValueError("page looked empty")
        # Shops show "Delivering to <your area + PIN code>" - don't keep the user's location
        text = re.sub(r"Delivering to [^\n]*", "Delivering to [location removed]", text)
        cache_file.write_text(text, encoding="utf-8")  # save for offline demo
        return text, "read live"
    except Exception as e:
        if cache_file.exists():
            return cache_file.read_text(encoding="utf-8"), f"used cached copy (live failed: {type(e).__name__})"
        raise


def chunk(text: str, size: int = 700):
    """Split a long page into ~700-character passages, remembering the PDF page number."""
    chunks, cur, page, cur_page = [], [], None, None
    for line in text.splitlines():
        m = re.match(r"\[page (\d+)\]", line)
        if m:
            page = int(m.group(1))
            continue
        if not line.strip():
            continue
        if not cur:
            cur_page = page
        cur.append(line.strip())
        if sum(len(x) for x in cur) > size:
            chunks.append({"text": " ".join(cur), "page": cur_page})
            cur = []
    if cur:
        chunks.append({"text": " ".join(cur), "page": cur_page})
    return chunks


def keywords(case):
    words = re.findall(r"[a-zA-Z0-9]+", f"{case['error_code']} {case['problem']}".lower())
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]


def score(text: str, case, kws) -> int:
    """How relevant is this passage? Error code match counts a lot, symptom words a little."""
    t = text.lower()
    s = sum(t.count(k) for k in kws)
    code = case["error_code"].strip().lower()
    if code and code in t:
        s += 10
    return s


# ---------------------------------------------------------------- 3. VERIFY

VERIFY_PROMPT = """You are MendMap's evidence checker for home-appliance and electronics repair.

Product: {brand} {model} ({category})
Error code: {error_code}
User's problem: {problem}

EVIDENCE - use ONLY this. Each item has an id and a source:
{evidence}

Return ONLY a JSON list (at most 4 items). Each item exactly like:
{{"label": "Verified|Likely|Unknown|Unsafe", "title": "short finding", "why": "one sentence", "excerpt": "exact words copied from ONE evidence item, max 30 words", "evidence_id": 1}}

Rules:
- Verified = the evidence directly states it for this error code / model.
- Likely   = the evidence supports it but does not confirm it.
- Unknown  = a possible cause with weak evidence.
- Unsafe   = anything involving mains wiring, internal electrics, motor, control board, gas/refrigerant
             or batteries -> the user must call a technician.
- Never invent facts. If the evidence is weak, use Unknown.
"""


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def quote_found(excerpt: str, source_text: str) -> bool:
    """Reliability check: does the AI's quote really appear on the page? (first 60 chars)"""
    return bool(excerpt) and norm(excerpt)[:60] in norm(source_text)


def verify_with_llm(case, evidence):
    ev_text = "\n\n".join(
        f"[id {e['id']}] source: {e['source']}{' (page ' + str(e['page']) + ')' if e['page'] else ''}\n{e['text']}"
        for e in evidence
    )
    reply = ask_llm(VERIFY_PROMPT.format(evidence=ev_text, **case))
    raw = reply[reply.find("["): reply.rfind("]") + 1]   # cut out the JSON list
    return json.loads(raw)


def looks_like_menu(sentence: str) -> bool:
    """Website menus read like 'Products Offers Service Contact Us' - mostly Capitalised words."""
    words = [w for w in sentence.split() if w[:1].isalpha()]
    return bool(words) and sum(w[0].isupper() for w in words) / len(words) > 0.5


def verify_with_rules(case, evidence):
    """No-AI fallback so the demo never breaks."""
    findings = []
    code = case["error_code"].strip().lower()
    for e in evidence:
        sentences = re.split(r"(?<=[.!?])\s+", e["text"])
        hit = next((s for s in sentences if code and code in s.lower()), None)
        if hit and not any(f["label"] == "Verified" for f in findings):
            findings.append({"label": "Verified", "title": f"Official source mentions {case['error_code']}",
                             "why": "The error code appears in an official passage.",
                             "excerpt": hit[:200], "evidence_id": e["id"]})
        elif len(findings) < 3:
            # quote the sentence that best matches the symptoms (skip tiny fragments like "6.")
            kws = keywords(case)
            useful = [s for s in sentences if 40 <= len(s) <= 300 and not looks_like_menu(s)]
            best = max(useful, key=lambda s: sum(k in s.lower() for k in kws), default=None)
            if best and sum(k in best.lower() for k in kws) > 0:
                findings.append({"label": "Likely", "title": "Related troubleshooting step",
                                 "why": "Passage matches the reported symptoms but does not confirm the cause.",
                                 "excerpt": best[:200], "evidence_id": e["id"]})
        if any(w in e["text"].lower() for w in UNSAFE_WORDS) and not any(f["label"] == "Unsafe" for f in findings):
            findings.append({"label": "Unsafe", "title": "Involves internal electrical parts",
                             "why": "This needs an authorised technician.",
                             "excerpt": "", "evidence_id": e["id"]})
    # strongest evidence first: Verified, then Unsafe (safety warning), then Likely, then Unknown
    rank = {"Verified": 0, "Unsafe": 1, "Likely": 2, "Unknown": 3}
    findings.sort(key=lambda f: rank.get(f["label"], 9))
    return findings[:4]


def verify(case, evidence, texts):
    try:
        findings = verify_with_llm(case, evidence)
        method = f"AI ({PROVIDER})"
    except Exception:
        findings = verify_with_rules(case, evidence)
        method = "rules (no AI)"

    by_id = {e["id"]: e for e in evidence}
    for f in findings:
        e = by_id.get(f.get("evidence_id"))
        f["source"] = e["source"] if e else ""
        f["page"] = e["page"] if e else None
        # Reliability layer 1: if the quote is not really on the page, downgrade it
        if f.get("excerpt") and e and not quote_found(f["excerpt"], texts[e["source"]]):
            f["label"] = "Unknown"
            f["why"] += " (Quote not found on the source page - downgraded.)"
        # Reliability layer 2: dangerous work is always Unsafe
        if any(w in (f.get("title", "") + " " + f.get("why", "")).lower() for w in UNSAFE_WORDS):
            f["label"] = "Unsafe"
    return findings, method


# ---------------------------------------------------------------- 4. DECIDE

PRICE_RE = re.compile(r"(?:₹|Rs\.?|INR)\s?([\d,]+(?:\.\d+)?)")


def find_price(text: str):
    """
    Find the selling price on a shop page.
    Shop pages also show struck-out MRPs ("Original price was: ₹3,480") and menu links
    ("Under ₹500"), so we can't just take the first ₹ amount we see.
    """
    # 1. Many shops label the real price: "Current price is: ₹2,250.00" -> trust that first
    m = re.search(r"current price[^₹\d]{0,20}" + PRICE_RE.pattern, text, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))

    # 2. Otherwise take the first sensible price that is NOT an MRP / menu link
    for m in PRICE_RE.finditer(text):
        before = text[max(0, m.start() - 25):m.start()].lower()
        if any(w in before for w in ["under", "original", "was", "mrp", "m.r.p"]):
            continue                 # skip "Under ₹500", "Original price was ₹3,480", "M.R.P.: ₹2,999"
        val = float(m.group(1).replace(",", ""))
        if 50 <= val <= 300000:      # ignore silly numbers
            return val
    return None


def compatibility(case, text: str) -> str:
    """Does the shop page name the user's exact model, or is it a generic 'suitable for' part?"""
    if case["model"].lower() in text.lower():
        return "page names your model"
    return "generic part - compatibility with your model NOT confirmed"


def warranty(case):
    y, m = map(int, case["purchase_date"].split("-")[:2])
    years = int(case.get("warranty_years") or 0)
    end = datetime.date(y + years, m, 1)
    inside = datetime.date.today() < end
    return {"status": "Likely in warranty" if inside else "Out of warranty",
            "ends": end.strftime("%b %Y"), "inside": inside,
            "note": "From your purchase date and the warranty period. Confirm with your invoice."}


def rupees(x):
    return f"₹{x:,.0f}" if x else "[check price]"


def decide(case, findings, w, part):
    # DIY is "not advised" only if the MAIN finding itself is unsafe (warnings elsewhere stay as notes)
    unsafe = bool(findings) and findings[0]["label"] == "Unsafe"
    svc = "₹0 (in warranty)" if w["inside"] else rupees(case.get("service_visit_cost"))
    return [
        {"name": "DIY: follow the manual's check", "cost": "Not advised" if unsafe else "₹0",
         "note": "Only Verified/Likely steps that are not Unsafe"},
        {"name": f"Buy the part: {case.get('part_name') or 'part'}", "cost": rupees(part.get("price")),
         "note": part.get("note", "")},
        {"name": "Authorised service visit", "cost": svc, "note": "Use the pre-filled request below"},
        {"name": "Replace the product", "cost": rupees(case.get("replacement_price")),
         "note": "Rule of thumb: replace if repair costs more than about half a new one"},
    ]


# ---------------------------------------------------------------- 5. FIX

def fill_service_form(case, likely_cause: str):
    """Open the service request form, fill it in, take a screenshot, and STOP before Submit."""
    from playwright.sync_api import sync_playwright

    form_url = (BASE / "mock_service_form.html").resolve().as_uri()
    shot = OUT / "service_form_prefilled.png"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(form_url)
        page.fill("#name", case.get("customer_name", ""))
        page.fill("#brand", case["brand"])
        page.fill("#model", case["model"])
        page.fill("#purchase", case["purchase_date"])
        page.fill("#fault", f"Error {case['error_code']}: {case['problem']} Likely cause: {likely_cause}")
        page.screenshot(path=str(shot), full_page=True)
        browser.close()   # <- we NEVER click Submit. The user reviews and submits.
    return shot


# ---------------------------------------------------------------- RUN EVERYTHING

def run(case, on_step=lambda s: None):
    trace = []

    def step(title, detail, source="", status="done"):
        # attach the screenshot of this page, if the agent took one
        shot = str(shot_path(source)) if source.startswith("http") and shot_path(source).exists() else None
        s = {"n": len(trace) + 1, "title": title, "detail": detail, "source": source, "status": status,
             "shot": shot}
        trace.append(s)
        on_step(s)

    # 1 IDENTIFY
    step("Identified exact product", f"{case['brand']} {case['model']} · {case['category']} · error {case['error_code']}")

    # 2 INVESTIGATE
    evidence, texts, kws = [], {}, keywords(case)
    for url in case["official_sources"]:
        try:
            text, how = fetch_text(url)
            texts[url] = text
            best = sorted(chunk(text), key=lambda c: score(c["text"], case, kws), reverse=True)[:3]
            for c in best:
                evidence.append({"id": len(evidence) + 1, "source": url, "page": c["page"], "text": c["text"]})
            step("Read official source", f"{how}; kept the {len(best)} most relevant passages", url)
        except Exception as e:
            step("Could not read source", f"{type(e).__name__}: {str(e)[:120]}", url, "failed")

    # 3 VERIFY
    findings, method = verify(case, evidence, texts) if evidence else ([], "none")
    step("Labelled the evidence", f"{len(findings)} findings via {method}; every quote checked against its page")

    # 4 DECIDE
    w = warranty(case)
    step("Checked warranty", f"{w['status']} (until {w['ends']})")

    part = {"price": None, "note": "No part source given"}
    for url in case.get("part_sources", []):
        try:
            text, how = fetch_text(url)
            price = find_price(text)
            fit = compatibility(case, text)
            if price and (part["price"] is None or price < part["price"]):
                part = {"price": price, "note": f"Lowest price found ({how}) · {fit}", "source": url}
            step("Checked part price", f"{rupees(price)} · {fit} · {how}", url)
        except Exception as e:
            step("Could not check part price", f"{type(e).__name__}", url, "failed")
    if part["price"] is None and case.get("part_price_fallback"):
        part = {"price": case["part_price_fallback"], "note": "Price you entered"}
    options = decide(case, findings, w, part)

    # 5 FIX
    likely = next((f["title"] for f in findings if f["label"] in ("Verified", "Likely")), "see Passport")
    shot = None
    try:
        shot = fill_service_form(case, likely)
        step("Pre-filled service request", "Form filled. Stopped before Submit - you review and submit.",
             "mock_service_form.html", "needs_you")
    except Exception as e:
        step("Could not fill service form", f"{type(e).__name__}", "", "failed")

    passport = {"case": case, "findings": findings, "warranty": w, "part": part, "options": options,
                "trace": trace, "form_screenshot": str(shot) if shot else None,
                "generated": datetime.datetime.now().strftime("%d %b %Y, %H:%M")}
    (OUT / "passport.json").write_text(json.dumps(passport, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "passport.html").write_text(passport_html(passport), encoding="utf-8")
    return passport


# ---------------------------------------------------------------- shareable Repair Passport (HTML)

COLORS = {"Verified": ("#DDF3EC", "#0B5A4E"), "Likely": ("#FBEBD3", "#8A4B06"),
          "Unknown": ("#E6E9EC", "#3D4650"), "Unsafe": ("#FBE0DE", "#9B1C1C")}


def passport_html(p):
    c, e = p["case"], html.escape
    rows = "".join(
        f"<div class='f'><span class='b' style='background:{COLORS[f['label']][0]};color:{COLORS[f['label']][1]}'>"
        f"{e(f['label'])}</span> <b>{e(f['title'])}</b><p>{e(f['why'])}</p>"
        + (f"<blockquote>“{e(f['excerpt'])}”</blockquote>" if f.get("excerpt") else "")
        + (f"<small>Source: <a href='{e(f['source'])}'>{e(f['source'])}</a>"
           f"{' · page ' + str(f['page']) if f.get('page') else ''}</small>" if f.get("source") else "")
        + "</div>"
        for f in p["findings"] if f.get("label") in COLORS
    )
    opts = "".join(f"<tr><td>{e(o['name'])}<br><small>{e(o['note'])}</small></td><td><b>{e(o['cost'])}</b></td></tr>"
                   for o in p["options"])
    trace = "".join(f"<li><b>{e(s['title'])}</b> - {e(s['detail'])}</li>" for s in p["trace"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Repair Passport</title>
<style>body{{font-family:system-ui,sans-serif;max-width:860px;margin:32px auto;padding:0 16px;color:#15181C}}
.f{{border:1px solid #D9DEE2;border-radius:10px;padding:12px;margin:10px 0}}.b{{padding:2px 9px;border-radius:99px;font-size:13px;font-weight:700}}
blockquote{{margin:6px 0;padding:6px 10px;background:#F2F4F5;border-radius:6px}}table{{width:100%;border-collapse:collapse}}
td{{border-bottom:1px solid #E5E8EB;padding:8px}}.warn{{background:#FBE0DE;color:#7A1616;padding:10px;border-radius:8px}}</style></head><body>
<p style="letter-spacing:.12em;font-size:12px;font-weight:700;color:#0E6E62">MENDMAP · REPAIR PASSPORT</p>
<h1>{e(c['brand'])} {e(c['model'])} · {e(c['error_code'])}</h1><p>{e(c['problem'])}</p>
<h2>Diagnosis</h2>{rows or '<p>No evidence found.</p>'}
<h2>Warranty</h2><p><b>{e(p['warranty']['status'])}</b> (until {e(p['warranty']['ends'])}). {e(p['warranty']['note'])}</p>
<h2>Repair or replace?</h2><table>{opts}</table>
<p class="warn"><b>Unplug before any check.</b> Anything marked Unsafe must be done by an authorised technician.</p>
<h2>Agent Trace</h2><ol>{trace}</ol><small>Generated {e(p['generated'])} by MendMap</small></body></html>"""
