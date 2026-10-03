import json
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

load_dotenv()

def _demo_result(lead: dict) -> dict:
    employees = lead.get("employees") or 0
    score = 92 if employees >= 50 else 78 if employees >= 20 else 55
    pain = [
        "Lead research and qualification can become repetitive as the sales team grows.",
        "Manual prospect enrichment and personalized outreach can consume seller time."
    ] if score >= 80 else [
        "The company is relatively small, so the immediate need for outbound automation is less clear."
    ]
    research = (
        f"{lead.get('company', 'Prospect')} operates in {lead.get('industry') or 'a business market'} "
        f"with approximately {employees} employees. Based on the supplied description, "
        "an outbound automation workflow could reduce repetitive prospect research, qualification, "
        "and first-touch personalization."
    )
    subject = f"Quick question about {lead.get('company', 'Prospect')}'s outbound workflow"
    body = (
        f"Hi {lead.get('contact_name') or 'there'},\n\n"
        f"I was looking at {lead.get('company', 'your company')} and noticed the team is growing. "
        "I was curious whether prospect research and first-touch qualification are still handled manually.\n\n"
        "We are building an AI-assisted workflow that can research prospects, qualify leads, "
        "and prepare personalized outreach while keeping a human in control of interested replies.\n\n"
        "Would it be useful to compare notes?\n\n"
        "Best,\nBidhan"
    )
    return {
        "fit_score": score,
        "pain_points": pain,
        "research": research,
        "subject": subject,
        "body": body,
        "source": "SIMULATED DEMO",
    }

def analyze_lead_with_gemini(lead_data: dict) -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return _demo_result(lead_data)

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash") # Or your configured model string

    prompt = f"""
You are an AI Sales Agent for ScaleBuild AI. Analyze this prospect:
- Company: {lead_data.get('company')}
- Website: {lead_data.get('website')}
- Industry: {lead_data.get('industry')}
- Employees: {lead_data.get('employees')}
- Contact: {lead_data.get('contact_name')}
- Role: {lead_data.get('contact_role')}
- Description: {lead_data.get('description')}

Return ONLY a raw JSON object matching this schema:
{{
  "fit_score": <number between 0 and 100>,
  "pain_points": [<string>, <string>],
  "research": <string summary value proposition>,
  "subject": <string outreach email subject line>,
  "body": <string email body text>
}}

Rules:
- Do not invent facts beyond the supplied information.
- Treat inferred pain points as hypotheses.
- Keep the email concise, specific, professional, and non-deceptive.
- Do not claim you personally observed facts that were not supplied.
"""

    client = genai.Client(api_key=api_key)
    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            text = (response.text or "").strip()
            if text.startswith("```"):
                text = text.replace("```json", "").replace("```", "").strip()
            
            data = json.loads(text)
            data["source"] = "LIVE GEMINI"
            return data

        except ServerError as e:
            # Retry on transient 503 high-demand errors
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            # If all retries fail, return safe demo fallback with error details
            result = _demo_result(lead_data)
            result["source"] = f"SIMULATED DEMO (Gemini 503 Busy: retry limit reached)"
            return result

        except Exception as exc:
            result = _demo_result(lead_data)
            result["source"] = f"SIMULATED DEMO (Gemini unavailable: {type(exc).__name__})"
            return result

# Maintain backward compatibility alias
analyze_lead = analyze_lead_with_gemini