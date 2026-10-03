from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .db import init_db, all_leads, get_lead, update_lead
from .ai import analyze_lead_with_gemini  # Ensure this function name matches your app/ai.py
from .gmail import create_email_draft     # Ensure this matches your app/gmail.py

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="ScaleBuild AI — AI Sales Agent")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

@app.on_event("startup")
def startup():
    init_db()

@app.get("/", response_class=HTMLResponse)
def home():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")

@app.get("/api/leads")
def leads():
    return all_leads()

@app.post("/api/leads/{lead_id}/analyze")
def analyze(lead_id: int):
    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # 1. Execute AI Analysis
    result = analyze_lead_with_gemini(lead)
    
    # 2. Safely extract fit/ICP score
    fit_score = int(result.get("icp_score") or result.get("fit_score") or 0)
    
    # 3. Format pain points safely
    pain_points_raw = result.get("pain_points") or result.get("key_pain_points") or []
    if isinstance(pain_points_raw, list):
        pain_points_str = "\n".join(pain_points_raw)
    else:
        pain_points_str = str(pain_points_raw)
        
    # 4. Extract outreach subject and body
    body = result.get("personalized_email") or result.get("outreach_body") or result.get("body") or ""
    subject = result.get("outreach_subject") or result.get("subject") or f"ScaleBuild AI x {lead.get('company', 'Prospect')}"
    
    # 5. Determine qualification status
    qual_status = result.get("qualification_status")
    if not qual_status:
        qual_status = "Qualified" if fit_score >= 80 else "Disqualified"

    # 6. Save update to SQLite
    update_lead(
        lead_id,
        fit_score=fit_score,
        pain_points=pain_points_str,
        research=result.get("value_proposition") or result.get("research") or "",
        outreach_subject=subject,
        outreach_body=body,
        status=qual_status,
        last_action=f"AI analysis completed via Gemini"
    )
    
    return {**result, "lead": get_lead(lead_id)}

@app.post("/api/leads/{lead_id}/send")
def send(lead_id: int):
    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.get("outreach_body"):
        raise HTTPException(status_code=400, detail="Analyze the lead first.")
    
    result = create_email_draft(
        lead.get("email"),
        lead.get("outreach_subject", "ScaleBuild AI Intro"),
        lead.get("outreach_body")
    )
    
    is_sent = result.get("sent") or result.get("status") == "sent"
    status_text = "Contacted" if is_sent else "Drafted"
    action_msg = result.get("message") or f"Email status: {status_text} ({result.get('mode', 'Simulation')})"
    
    update_lead(
        lead_id,
        status=status_text,
        last_action=action_msg
    )
    return result

@app.post("/api/leads/{lead_id}/simulate-reply")
def simulate_reply(lead_id: int):
    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    update_lead(
        lead_id,
        status="Interested",
        last_action="SIMULATED: Positive reply detected — human follow-up recommended"
    )
    return {"status": "Interested", "message": "Simulated positive reply detected. Human follow-up recommended."}