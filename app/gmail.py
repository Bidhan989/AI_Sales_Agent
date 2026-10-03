import base64
import os
from email.mime.text import MIMEText
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
ROOT = Path(__file__).resolve().parent.parent

def gmail_available():
    return (
        os.getenv("SEND_EMAILS", "false").lower() == "true"
        and (ROOT / "credentials.json").exists()
    )

def send_email(to, subject, body):
    if not gmail_available():
        return {
            "sent": False, 
            "status": "drafted", 
            "mode": "SIMULATED", 
            "message": "Gmail sending is disabled or credentials.json is missing."
        }

    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token_path = ROOT / "token.json"
    creds = None
    if token_path.exists():
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(ROOT / "credentials.json"), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service = build("gmail", "v1", credentials=creds)
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {
        "sent": True, 
        "status": "sent", 
        "mode": "LIVE", 
        "message": "Email sent through Gmail API."
    }

def create_email_draft(to, subject, body):
    """Wrapper function to maintain compatibility with app/main.py imports."""
    return send_email(to, subject, body)