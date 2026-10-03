import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()
from . import db
from .ai import analyze_lead, classify_reply, write_followup
from .gmail import gmail_available, send_email
from .icp import evaluate, load_icp
from .notify import hot_lead_alert
from .research import fetch_website_text

ROOT = Path(__file__).resolve().parent.parent

@asynccontextmanager
async def lifespan(_):
    db.init_db()
    yield

app = FastAPI(title="ScaleBuild AI - AI Sales Agent", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

def need(lead_id: int) -> dict:
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead

# ---------------- read ----------------
@app.get("/", response_class=HTMLResponse)
def home():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")

@app.get("/api/leads")
def leads():
    return db.all_leads()

@app.get("/api/stats")
def stats():
    return db.stats()

@app.get("/api/config")
def config():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return {
        "icp": load_icp(),
        "ai_mode": "LIVE GEMINI" if key and not key.startswith("YOUR_") else "SIMULATED (no key)",
        "email_mode": "LIVE GMAIL" if gmail_available() else "SIMULATED (nothing is sent)",
        "test_recipient": os.getenv("TEST_RECIPIENT", "").strip() or None,
        "n8n_webhook": bool(os.getenv("N8N_WEBHOOK_URL", "").strip()),
    }

@app.get("/api/leads/{lead_id}/events")
def events(lead_id: int):
    return db.lead_events(lead_id)

# ---------------- lead intake ----------------
@app.post("/api/leads")
def add_lead(lead: dict = Body(...)):
    if not (lead.get("company") or "").strip():
        raise HTTPException(400, "company is required")
    return {"added": db.add_leads([lead])}

@app.post("/api/leads/upload")
async def upload(file: UploadFile = File(...)):
    text = (await file.read()).decode("utf-8-sig", errors="ignore")
    n = db.add_leads(db.read_csv_text(text))
    if not n:
        raise HTTPException(400, "No rows imported. CSV needs a header row with at least: company")
    return {"added": n}

@app.delete("/api/leads/{lead_id}")
def remove(lead_id: int):
    need(lead_id)
    db.delete_lead(lead_id)
    return {"deleted": lead_id}

# ---------------- core actions ----------------
def do_analyze(lead_id: int) -> dict:
    lead = need(lead_id)
    web = fetch_website_text(lead.get("website"))                # REAL research (if site reachable)
    ai = analyze_lead(lead, web["text"])                         # Gemini or simulated
    verdict = evaluate(lead, ai)                                 # RULES decide, not the LLM
    ok = verdict["qualified"]
    db.update_lead(
        lead_id, analyzed=1, qualified=int(ok), fit_score=ai["fit_score"],
        status="Qualified" if ok else "Disqualified", stopped=0 if ok else 1,
        pain_points=json.dumps(ai["pain_points"]),
        research=ai["research"] + (f"\n\nReason to contact: {ai['reason_to_contact']}" if ai["reason_to_contact"] else ""),
        outreach_subject=ai["subject"] if ok else "", outreach_body=ai["body"] if ok else "",
        qualification_checks=json.dumps(verdict["checks"]), ai_source=ai["source"],
        research_note=web["note"], last_action=f"Analyzed ({ai['source']}; {web['note']})",
    )
    db.log_event(lead_id, "analyzed", f"Score {ai['fit_score']} -> {'QUALIFIED' if ok else 'DISQUALIFIED'} [{ai['source']}] [{web['note']}]")
    return db.get_lead(lead_id)

def do_send(lead_id: int, subject: str, body: str, kind: str) -> dict:
    lead = need(lead_id)
    result = send_email(lead.get("email"), subject, body)
    sent = bool(result.get("sent"))
    fields = {"send_count": (lead["send_count"] or 0) + 1, "last_contacted": db.now(),
              "status": "Contacted", "last_action": f"{kind}: {'LIVE sent' if sent else 'SIMULATED send'}"}
    if kind.startswith("Follow-up"):
        fields["followup_count"] = (lead["followup_count"] or 0) + 1
    db.update_lead(lead_id, **fields)
    db.log_event(lead_id, "email", f"{kind} - {result['message']}")
    return result

@app.post("/api/leads/{lead_id}/analyze")
def analyze(lead_id: int):
    return do_analyze(lead_id)

@app.post("/api/leads/{lead_id}/send")
def send(lead_id: int):
    lead = need(lead_id)
    if not lead["qualified"] or not lead["outreach_body"]:
        raise HTTPException(400, "Only qualified leads with generated outreach can be emailed. Run analysis first.")
    if lead["stopped"]:
        raise HTTPException(400, "Automation is stopped for this lead.")
    return do_send(lead_id, lead["outreach_subject"], lead["outreach_body"], "Initial email")

@app.post("/api/leads/{lead_id}/reply")
def reply(lead_id: int, payload: dict = Body(...)):
    lead = need(lead_id)
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Paste the reply text.")
    c = classify_reply(text)
    intent = c["intent"]
    fields = {"reply_text": text, "reply_intent": intent}
    note = ""
    if intent in ("POSITIVE", "QUESTION"):
        fields.update(status="Interested", stopped=1)
        note = hot_lead_alert(lead, text)
    elif intent == "NEGATIVE":
        fields.update(status="Not Interested", stopped=1)
    elif intent == "UNCLEAR":
        fields.update(status="Needs Review", stopped=1)
    # OUT_OF_OFFICE: keep status, automation continues
    fields["last_action"] = f"Reply classified {intent} ({c['source']})"
    db.update_lead(lead_id, **fields)
    db.log_event(lead_id, "reply", f"{intent}: {c.get('summary','')} [{c['source']}] {note}")
    return {**c, "alert": note, "lead": db.get_lead(lead_id)}

@app.post("/api/leads/{lead_id}/simulate-reply")
def simulate_reply(lead_id: int):
    """Demo button: feeds a sample positive reply through the REAL classifier."""
    return reply(lead_id, {"text": "Interesting - can you send me more information about how this works?"})

# ---------------- follow-ups ----------------
def due_for_followup(lead: dict, icp: dict, force: bool) -> bool:
    n = lead["followup_count"] or 0
    if lead["status"] != "Contacted" or lead["stopped"] or lead["reply_text"] or n >= icp["max_followups"]:
        return False
    if force:
        return True
    try:
        last = datetime.fromisoformat(lead["last_contacted"])
    except Exception:
        return False
    wait = icp["followup_days"][min(n, len(icp["followup_days"]) - 1)]
    return (datetime.now(timezone.utc) - last).days >= wait

@app.post("/api/leads/{lead_id}/followup")
def followup(lead_id: int):
    lead = need(lead_id)
    n = (lead["followup_count"] or 0) + 1
    if lead["stopped"] or lead["reply_text"]:
        raise HTTPException(400, "Automation stopped (reply received or disqualified).")
    if n > load_icp()["max_followups"]:
        raise HTTPException(400, "Max follow-ups reached.")
    if lead["status"] != "Contacted":
        raise HTTPException(400, "Send the initial email first.")
    f = write_followup(lead, n)
    res = do_send(lead_id, f["subject"], f["body"], f"Follow-up #{n}")
    db.update_lead(lead_id, outreach_subject=f["subject"], outreach_body=f["body"])
    return {**res, "followup": f}

@app.post("/api/followups/run")
def run_followups(force: bool = False):
    """Called by the dashboard button or by n8n on a schedule. force=true ignores the 3/4-day wait (for demos)."""
    icp = load_icp()
    done = []
    for l in db.all_leads():
        if due_for_followup(l, icp, force):
            followup(l["id"])
            done.append(l["company"])
    return {"followed_up": done}

# ---------------- full pipeline ----------------
@app.post("/api/pipeline/run")
def run_pipeline(send_emails: bool = True):
    """New leads -> research -> score -> rules -> outreach -> send (simulated unless Gmail is live)."""
    out = {"analyzed": [], "qualified": [], "disqualified": [], "sent": []}
    for l in db.all_leads():
        if l["status"] != "New":
            continue
        r = do_analyze(l["id"])
        out["analyzed"].append(r["company"])
        (out["qualified"] if r["qualified"] else out["disqualified"]).append(r["company"])
        if r["qualified"] and send_emails and (r["ai_source"].startswith("LIVE") or "no Gemini key" in r["ai_source"]):
            send(r["id"])
            out["sent"].append(r["company"])
    return out
