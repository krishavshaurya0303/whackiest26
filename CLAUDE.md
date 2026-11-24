# CLAUDE.md - project context for Claude Code

## What this is
**MendMap** (name may change to "Theek" - only `APP_NAME` in app.py + PPT title) is our team's entry for
**wHACKiest 2026** (CodeRIT, Ramaiah Institute of Technology, Bengaluru), **Track 2: Beyond the Browser**
("build browser-based agents that navigate sites, find what matters, compare options and complete complicated
online workflows; make the web smoother, more accessible and more intuitive").

We are 2nd-year CSE students. Keep code simple, commented and beginner-readable.

## Deadlines and judging
- Round 1 due **24 Nov 2026, 11:59 PM IST** on Devnovate: PPT (official template only, no extra slides,
  named TeamName_2, Drive link "anyone can view"), 3-5 min YouTube video (problem, solution, architecture),
  compulsory GitHub repo with a basic working demo, track number.
- Repo can keep improving until the online ideation round on 26-27 Nov. Shortlist 28 Nov.
  Offline 24-hour build 1-2 Dec at MSRIT.
- Judges mainly score: problem understanding, thinking behind the solution, clarity. Then architecture, MVP, innovation.
- Sponsor prizes: using **ElevenLabs** or **AWS** in the real architecture.

## The product
A browser agent for repairs. Input: brand, exact model, error code, purchase date, problem.
Flow (memory hook): **Identify -> Investigate -> Verify -> Decide -> Fix**
1. Identify the exact product.
2. Investigate: Playwright opens OFFICIAL support pages + manual PDFs (pypdf), keeps the most relevant passages.
3. Verify: LLM labels findings Verified / Likely / Unknown / Unsafe with an exact excerpt + source.
   Reliability layers: a quote not found on the page is downgraded to Unknown; electrical/gas/motor/battery work = Unsafe.
4. Decide: warranty status (purchase date + period), part price from 2 shop pages, repair-vs-replace options.
5. Fix: pre-fills the service request form (mock_service_form.html) and **STOPS before Submit**. The user submits.
Output: **Repair Passport** (HTML + JSON) + **Agent Trace** (every site visited, every excerpt).
Extras already built: ElevenLabs voice summary (English/Hindi/Kannada), "Draft complaint letter" if the brand refuses.

Pitch line: "Other repair bots guess from a photo. MendMap proves it from the manufacturer, then gets it fixed."

## Non-negotiable rules for any code change
- Never auto-submit forms, never pay, never enter OTPs/passwords. The user makes every final click.
- Never present a guess as Verified. Every claim needs a source.
- Never invent statistics, prices or manual text. Unknown values stay as [placeholders].
- Keep the demo working offline: every fetched page is cached in cache/; `local:` sources read local text files.

## Files
- `app.py` - Streamlit website (form, live Agent Trace, Passport, voice, complaint letter). `streamlit run app.py`
- `agent.py` - the agent: fetch_text (Playwright/PDF/cache), chunk + score, verify (LLM or rules fallback),
  warranty, find_price, decide, fill_service_form, run(), passport_html()
- `llm.py` - ask_llm(): LLM_PROVIDER = mock | gemini | bedrock (set in .env)
- `demo_case.json` - the demo product. REPLACE the placeholder URLs with a real product's official pages.
- `mock_service_form.html` - demo copy of a brand service form
- `.env.example` - copy to .env (never commit .env)

Setup: `pip install -r requirements.txt && playwright install chromium && cp .env.example .env`
Status: tested end to end in mock mode on a sample manual (all 5 steps run, form filled, not submitted).

## TODO tonight (in order)
1. Fill demo_case.json with ONE real product (brand, model, error code, official support URL, manual PDF URL, 2 part URLs).
2. Run once online so cache/ fills. Set LLM_PROVIDER=gemini or bedrock.
3. Push to GitHub. Record the video. Submit.

## Known weaknesses (be honest in the pitch)
- Repair chatbots are common on Devpost; our edge = official sources + quote checking + Agent Trace + doing the steps.
- Live sites change/break -> cache fallback; service form is a demo copy.
- Part price = first price found on the page; warranty uses the period the user enters.

## Vision (PPT only, not built)
Repair Court (brand -> National Consumer Helpline -> consumer commission escalation), Brand Repair Leaderboard
(public ranking of brands that honour repairs), Snap-to-fix (photo -> exact model), Fix-or-flip
(exchange value + CPCB-authorised e-waste recycler), Right to Repair Portal India integration. Verify every
statistic and government detail before it goes on a slide.
