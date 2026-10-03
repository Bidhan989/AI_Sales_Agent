# ScaleBuild AI — AI Sales Agent

Lead intake → website research → AI scoring → **rule-based qualification** → personalized email → follow-ups → reply classification → CRM log + hot-lead alert.

## Working vs simulated

| Step | Status |
|---|---|
| Lead intake (CSV upload, add form, sample CSV) | **WORKING** |
| Apollo lead sourcing | **SIMULATED** (sample/uploaded CSV, no Apollo account) |
| Clay enrichment | **SIMULATED** (no Clay account) |
| Company research | **IMPLEMENTED** for real public websites (fetches site text). Sample `.example` domains can't load, so research is skipped and labelled |
| AI scoring, pain points, email writing | **WORKING with Gemini key**, otherwise **SIMULATED** (labelled per lead) |
| ICP qualification | **WORKING** (rules in `data/icp.json`, not the LLM) |
| Gmail sending | **IMPLEMENTED**, requires Gmail OAuth setup; otherwise **SIMULATED** |
| Follow-ups (day 3, day 4, then stop) | **WORKING** logic; dashboard button forces them for demos; n8n can trigger on a schedule |
| Reply classification | **WORKING** on pasted reply text (Gemini, or keyword fallback labelled SIMULATED) |
| Automatic inbox polling | **NOT BUILT** — replies are pasted in |
| Stop on reply / negative / disqualified | **WORKING** |
| Hot-lead alert | Dashboard banner **WORKING**; n8n webhook alert works if `N8N_WEBHOOK_URL` is set |
| n8n workflow | Importable file included; **not required** to run the app |

## Setup (Windows, PowerShell, in this folder)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env        # paste GEMINI_API_KEY, save
python -m uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

If activation is blocked: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

## Gemini
Key from https://aistudio.google.com/apikey → `GEMINI_API_KEY` in `.env`.
Set `GEMINI_MODEL=gemini-3.8-flash` (the model this project was built and tested with). The badge on each lead shows LIVE GEMINI (model name) or SIMULATED plus the reason.

**Free-tier limits:** the free tier allows about 20 requests per day per project for this model. Each lead analysis, follow-up and reply classification uses one request, so avoid re-running the full pipeline repeatedly. Calls are paced by `GEMINI_MIN_GAP` (default 13 seconds). When the quota is hit, the app falls back to clearly labelled SIMULATED output instead of crashing.

## Gmail (optional, do last)
1. Google Cloud → new project → enable **Gmail API** → OAuth consent screen (External, add your Gmail as a test user).
2. Credentials → Create OAuth client ID → **Desktop app** → download JSON → save as `credentials.json` in this folder.
3. In `.env`: `SEND_EMAILS=true` and `TEST_RECIPIENT=your.own@gmail.com` (**all mail is redirected there**, so leads are never emailed).
4. First send opens a browser to authorize.

## Demo script
1. Open a lead and click **Re-run AI analysis**: see the rule checks, pain points and generated email.
2. Click **Run full pipeline** to process all new leads (uses one AI request per lead).
3. **Run follow-ups (demo)**: follow-up #1 goes out for contacted leads.
4. Paste "Interesting, send me more info" → POSITIVE → HOT LEAD banner. Paste "remove me" → automation stops.
5. For live research: **Upload CSV** with real company websites.

## n8n (optional)
Import `n8n/workflow_demo.json`: daily schedule → `/api/pipeline/run` → `/api/followups/run`, plus a `hot-lead` webhook. Put the webhook's production URL in `N8N_WEBHOOK_URL`. (Not tested against a live n8n instance.)

## Security
`.env`, `credentials.json`, `token.json` and the local database are git-ignored. Never commit API keys.