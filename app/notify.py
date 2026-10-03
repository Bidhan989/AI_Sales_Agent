"""Optional: POST a JSON alert to an n8n webhook when a lead turns Interested.
Set N8N_WEBHOOK_URL in .env to enable. If unset, nothing is sent (simulated)."""
import json
import os
import urllib.request

def hot_lead_alert(lead: dict, reply: str) -> str:
    url = os.getenv("N8N_WEBHOOK_URL", "").strip()
    payload = {"event": "hot_lead", "company": lead["company"], "contact": lead.get("contact_name"),
               "email": lead.get("email"), "reply": reply, "action": "Contact within 24 hours"}
    if not url:
        return "Alert shown in dashboard only (N8N_WEBHOOK_URL not set)"
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=6)
        return "Alert sent to n8n webhook"
    except Exception as e:
        return f"n8n webhook failed ({type(e).__name__})"
