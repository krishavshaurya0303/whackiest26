# MendMap

**From broken to fixed. Without the guesswork.**
wHACKiest 2026 · Track 2: Beyond the Browser

MendMap is a browser agent for repairs. Tell it your exact product, error code and purchase date. It opens the official support pages and manuals in a real browser, labels every finding with evidence (Verified / Likely / Unknown / Unsafe), checks warranty and part prices, pre-fills the service request **and stops before Submit**. Everything ends up in a shareable **Repair Passport**, with an **Agent Trace** showing every site visited.

> Other repair bots guess from a photo. MendMap proves it from the manufacturer, then gets it fixed.

## How it works

```
Your product + error code + purchase date
        ↓
1 IDENTIFY     exact model
2 INVESTIGATE  Playwright opens official support pages + manual PDFs
3 VERIFY       AI labels evidence: Verified / Likely / Unknown / Unsafe
               + every quote is checked against the real page (no made-up quotes)
4 DECIDE       warranty status + part prices + repair-vs-replace
5 FIX          pre-fills the service request form, STOPS before Submit
        ↓
Repair Passport (HTML/JSON) + Agent Trace
Extras: hear it in English/Hindi/Kannada (ElevenLabs) · draft a complaint if the brand refuses
```

## Tech stack

| Part | Tool |
|---|---|
| Browser agent | Python + Playwright (headless Chrome) |
| AI brain | AWS Bedrock or Google Gemini (or `mock` rules, no AI) |
| Manuals | pypdf |
| Website | Streamlit |
| Voice | ElevenLabs text-to-speech |

## Run it

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env        # then edit .env
streamlit run app.py
```

1. Edit `demo_case.json` with a real product: brand, model, error code, the **official support page URL** and **manual PDF URL**, plus 2 part shop URLs.
2. Run once with internet. Every page read is cached in `cache/`, so the demo still works if a site fails later.
3. If a site blocks bots, save its text to `cache/manual.txt` and use the source `local:cache/manual.txt`.

## Safety and control

- Reads official sources first. Every claim shows its source and quote.
- A quote that can't be found on the page is downgraded to **Unknown**.
- Electrical, gas, motor and battery work is always **Unsafe**: call a technician.
- Never submits forms, never pays. The user makes every final click.

## Honest limits (MVP)

- The service request form is a demo copy. Real brand forms differ.
- Part prices come from the first price found on the page; always double-check.
- Warranty is calculated from the purchase date and period you enter.

## Roadmap

Photo to exact model · live-site service booking · price history for parts · Right to Repair Portal India integration · repair-cost and failure map across users.
