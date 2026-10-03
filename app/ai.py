import json
import os
import re
import time
from dotenv import load_dotenv

load_dotenv()
SENDER = os.getenv("SENDER_NAME", "Bidhan")
DEFAULT_MODEL = "gemini-3.8-flash"

def _models() -> list:
    """Only the model from .env (or the default). No fallbacks."""
    return [os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL]

_last_call = 0.0

def _wait_hint(err: str) -> float:
    """Pull Google's suggested retry delay out of a 429 message, else 20s."""
    m = re.search(r"retry in ([\d.]+)s", err) or re.search(r"retryDelay'?:?\s*'?(\d+)s", err)
    return min(float(m.group(1)) + 1, 60) if m else 20.0

def _call_gemini(prompt: str):
    """Returns (data_dict, source_label). Falls back to (None, reason) on failure."""
    global _last_call
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key or key.startswith("YOUR_"):
        return None, "SIMULATED (no Gemini key)"
    try:
        from google import genai
        client = genai.Client(api_key=key)
    except Exception as e:
        return None, f"SIMULATED (Gemini setup failed: {type(e).__name__})"
    gap = float(os.getenv("GEMINI_MIN_GAP", "13"))   # seconds between calls
    last = ""
    for model in _models():
        for attempt in range(2):
            wait = gap - (time.time() - _last_call)
            if wait > 0:
                time.sleep(wait)
            _last_call = time.time()
            try:
                r = client.models.generate_content(
                    model=model, contents=prompt,
                    config={"response_mime_type": "application/json"})
                text = (r.text or "").strip().replace("```json", "").replace("```", "").strip()
                return json.loads(text), f"LIVE GEMINI ({model})"
            except Exception as e:
                last = f"{model}: {type(e).__name__}: {str(e)[:700]}"
                if "429" in last or "RESOURCE_EXHAUSTED" in last:
                    if "PerDay" in last:
                        break                      # daily quota gone: retrying won't help
                elif "503" in last or "UNAVAILABLE" in last:
                    time.sleep(4 * (attempt + 1))  # overloaded: wait and retry
                else:
                    break                          # bad model name etc: stop
    return None, f"SIMULATED (Gemini failed: {last[:700]})"

# ---------- 1. Lead analysis ----------
def _demo_analysis(lead: dict, web: str) -> dict:
    emp = lead.get("employees") or 0
    score = 92 if emp >= 50 else 78 if emp >= 20 else 55
    co = lead.get("company", "your company")
    return {
        "fit_score": score,
        "pain_points": ["Manual lead research and qualification as the sales team grows",
                        "Time spent on first-touch personalization"] if score >= 70 else [],
        "reason_to_contact": f"{co} appears to be scaling its outbound motion.",
        "research": f"{co} ({lead.get('industry') or 'business'}, ~{emp} employees). {lead.get('description') or ''}",
        "subject": f"Quick question about {co}'s outbound workflow",
        "body": (f"Hi {lead.get('contact_name') or 'there'},\n\nI saw that {co} is growing its sales operation. "
                 "I'm curious whether prospect research and first-touch qualification are still handled manually.\n\n"
                 "We build AI workflows that research prospects and draft personalized outreach, with a human "
                 "staying in control of every interested reply.\n\nWorth comparing notes?\n\n"
                 f"Best,\n{SENDER}"),
    }

def analyze_lead(lead: dict, website_text: str = "") -> dict:
    prompt = f"""You are an AI SDR for Sales_agent, which sells AI sales-automation workflows to B2B companies.
Analyze this prospect.

Company: {lead.get('company')}
Website: {lead.get('website')}
Industry: {lead.get('industry')}
Employees: {lead.get('employees')}
Contact: {lead.get('contact_name')} ({lead.get('contact_role')})
Description: {lead.get('description')}
Website text (may be empty): {website_text or 'NONE'}

Return ONLY JSON:
{{"fit_score": <0-100>, "pain_points": [<string>], "reason_to_contact": <string>,
  "research": <2-3 sentence account summary>, "subject": <string>, "body": <string>}}

Rules:
- Use ONLY the facts above. Never invent facts, funding, news or quotes.
- Pain points are hypotheses; word them as such.
- If website text is NONE, do not claim you read their site.
- Email: under 110 words, specific, no "I hope you're well", no hype, sign off as {SENDER}.
- If fit is poor, still return fields but fit_score must be low and pain_points may be empty."""
    data, source = _call_gemini(prompt)
    if data is None:
        data = _demo_analysis(lead, website_text)
    try:
        data["fit_score"] = max(0, min(100, int(float(data.get("fit_score", 0)))))
    except Exception:
        data["fit_score"] = 0
    pp = data.get("pain_points") or []
    data["pain_points"] = [str(p) for p in pp] if isinstance(pp, list) else [str(pp)]
    for k in ("research", "subject", "body", "reason_to_contact"):
        data[k] = str(data.get(k) or "")
    data["source"] = source
    return data

# ---------- 2. Reply classification ----------
INTENTS = ["POSITIVE", "NEGATIVE", "QUESTION", "OUT_OF_OFFICE", "UNCLEAR"]

def _demo_classify(text: str) -> dict:
    t = text.lower()
    if any(w in t for w in ["unsubscribe", "remove me", "not interested", "stop emailing", "no thanks", "don't contact"]):
        return {"intent": "NEGATIVE", "summary": "Declined / asked to stop."}
    if any(w in t for w in ["out of office", "on vacation", "auto-reply", "automatic reply"]):
        return {"intent": "OUT_OF_OFFICE", "summary": "Automatic out-of-office reply."}
    if any(w in t for w in ["interested", "send me", "more info", "tell me more", "book", "call", "demo", "let's talk", "sounds good"]):
        return {"intent": "POSITIVE", "summary": "Shows interest / asks for next step."}
    if "?" in t:
        return {"intent": "QUESTION", "summary": "Asked a question."}
    return {"intent": "UNCLEAR", "summary": "Could not determine intent."}

def classify_reply(text: str) -> dict:
    prompt = f"""Classify this reply to a cold sales email.
Reply: \"\"\"{text}\"\"\"
Return ONLY JSON: {{"intent": one of {INTENTS}, "summary": <one short sentence>}}
NEGATIVE includes unsubscribe/remove-me requests. POSITIVE means interest or a request for info/meeting."""
    data, source = _call_gemini(prompt)
    if not data or str(data.get("intent", "")).upper() not in INTENTS:
        data = _demo_classify(text)
        source = source if source.startswith("SIMULATED") else "SIMULATED (keyword fallback)"
    data["intent"] = str(data["intent"]).upper()
    data["source"] = source
    return data

# ---------- 3. Follow-ups ----------
def write_followup(lead: dict, n: int) -> dict:
    final = n >= 2
    prompt = f"""Write follow-up #{n} for a cold email that got no reply.
Company: {lead.get('company')}; Contact: {lead.get('contact_name')} ({lead.get('contact_role')})
Original subject: {lead.get('outreach_subject')}
Original email: {lead.get('outreach_body')}
Return ONLY JSON: {{"subject": <string>, "body": <string>}}
Rules: under 60 words, add one NEW angle, no guilt-tripping, no invented facts.
{'This is the FINAL follow-up: be polite and say you will not email again.' if final else ''}
Sign off as {SENDER}."""
    data, source = _call_gemini(prompt)
    if not data or not data.get("body"):
        co = lead.get("company", "your team")
        data = {
            "subject": "Re: " + (lead.get("outreach_subject") or f"{co} outbound workflow"),
            "body": (f"Hi {lead.get('contact_name') or 'there'},\n\nJust floating this back up. "
                     + ("I won't email again after this one, but if automating prospect research ever becomes a priority, I'm happy to help.\n\n"
                        if final else "Even a 15-minute chat on how teams automate prospect research could be useful.\n\n")
                     + f"Best,\n{SENDER}"),
        }
        source = source if source.startswith("SIMULATED") else "SIMULATED"
    data["source"] = source
    return data