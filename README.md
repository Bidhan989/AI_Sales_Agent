# AI Sales Agent

Lead intake → website research → AI scoring → **rule-based qualification** → personalized email → follow-ups → reply classification → CRM log + hot-lead alert, orchestrated with n8n.

**Stack:** Python, FastAPI, SQLite, Gemini API, Gmail API, n8n, vanilla JavaScript.

## Working vs simulated

| Step | Status |
|---|---|
| Lead intake (CSV upload, add form, sample CSV) | **WORKING** |
| Apollo lead sourcing | **SIMULATED** (sample/uploaded CSV, no Apollo account) |
| Clay enrichment | **SIMULATED** (no Clay account) |
| Company research | **IMPLEMENTED** for real public websites (fetches site text). Sample `.example` domains can't load, so research is skipped and labelled |
| AI scoring, pain points, email writing | **WORKING with Gemini key**, otherwise **SIMULATED** (labelled per lead) |
| ICP qualification | **WORKING** (rules in `data/icp.json`, not the LLM) |
| Gmail sending | **WORKING** (tested; all mail redirected to `TEST_RECIPIENT` in demo) |
| Follow-ups (day 3, day 4, then stop) | **WORKING** logic; dashboard button forces them for demos; n8n triggers them on a schedule |
| Reply classification | **WORKING** on pasted reply text (Gemini, or keyword fallback labelled SIMULATED) |
| Automatic inbox polling | **NOT BUILT** — replies are pasted in |
| Stop on reply / negative / disqualified | **WORKING** |
| Hot-lead alert | **WORKING**: dashboard banner, plus an n8n webhook alert (tested) |
| n8n orchestration | **WORKING** (tested): pipeline and follow-up runs, hot-lead webhook |

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

## Gmail
1. Google Cloud → new project → enable **Gmail API** → OAuth consent screen (External, add your Gmail as a test user).
2. Credentials → Create OAuth client ID → **Desktop app** → download JSON → save as `credentials.json` in this folder.
3. In `.env`: `SEND_EMAILS=true` and `TEST_RECIPIENT=your.own@gmail.com` (**all mail is redirected there**, so leads are never emailed).
4. First send opens a browser to authorize.

Emails send from the Google account you authorize on first run. With `TEST_RECIPIENT` set, they go to that address instead of the lead's.

## n8n
1. Run n8n locally and import `n8n/workflow_demo.json` (**Workflows → ⋯ → Import from file**).
2. **Pipeline branch:** a daily schedule calls `POST http://127.0.0.1:8000/api/pipeline/run`, then `POST http://127.0.0.1:8000/api/followups/run`. Click **Execute workflow** to run it manually. (If n8n runs in Docker, use `host.docker.internal` instead of `127.0.0.1`.)
3. **Hot-lead branch:** open the **Hot lead webhook** node, copy its Test URL, and set it as `N8N_WEBHOOK_URL` in `.env`. Restart the app, click **Listen for test event**, then classify a positive reply in the dashboard. For always-on use, publish the workflow and use the Production URL.

Publishing activates the daily schedule, which uses AI requests. Test with manual execution first.

## Demo script
1. Add a lead (**+ Add lead**), or open an existing one and click **Run AI analysis**: see the rule checks, pain points and generated email.
2. Run the pipeline from n8n (**Execute workflow**) or the dashboard (**Run full pipeline**). Each new lead uses one AI request.
3. **Run follow-ups (demo)**: follow-up #1 goes out for contacted leads.
4. Paste "Interesting, send me more info" → POSITIVE → HOT LEAD banner, and the n8n webhook fires. Paste "remove me" → automation stops.
5. For live research: **Upload CSV** with real company websites.

## Security
`.env`, `credentials.json`, `token.json` and the local database are git-ignored. Never commit API keys.