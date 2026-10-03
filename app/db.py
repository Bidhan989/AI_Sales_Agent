import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "sales_agent.db"
CSV_PATH = ROOT / "data" / "leads.csv"

COLUMNS = {  # name -> definition (new columns are auto-added to old databases)
    "company": "TEXT NOT NULL", "website": "TEXT", "industry": "TEXT", "employees": "INTEGER",
    "contact_name": "TEXT", "contact_role": "TEXT", "email": "TEXT", "description": "TEXT",
    "fit_score": "INTEGER DEFAULT 0", "status": "TEXT DEFAULT 'New'",
    "pain_points": "TEXT DEFAULT ''", "research": "TEXT DEFAULT ''",
    "outreach_subject": "TEXT DEFAULT ''", "outreach_body": "TEXT DEFAULT ''",
    "last_action": "TEXT DEFAULT ''",
    "data_source": "TEXT DEFAULT 'Sample CSV (simulated Apollo/Clay)'",
    "analyzed": "INTEGER DEFAULT 0", "qualified": "INTEGER DEFAULT 0",
    "qualification_checks": "TEXT DEFAULT ''", "ai_source": "TEXT DEFAULT ''",
    "research_note": "TEXT DEFAULT ''", "send_count": "INTEGER DEFAULT 0",
    "followup_count": "INTEGER DEFAULT 0", "last_contacted": "TEXT DEFAULT ''",
    "reply_text": "TEXT DEFAULT ''", "reply_intent": "TEXT DEFAULT ''", "stopped": "INTEGER DEFAULT 0",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL)")
    conn.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, ts TEXT, kind TEXT, detail TEXT)""")
    have = {r["name"] for r in conn.execute("PRAGMA table_info(leads)")}
    for name, ddl in COLUMNS.items():
        if name not in have:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {name} {ddl}")
    conn.commit()
    if conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0 and CSV_PATH.exists():
        import_rows(conn, read_csv_text(CSV_PATH.read_text(encoding="utf-8-sig")))
        conn.commit()
    conn.close()

def read_csv_text(text: str) -> List[dict]:
    return list(csv.DictReader(text.splitlines()))

def import_rows(conn, rows: List[dict]) -> int:
    n = 0
    for r in rows:
        r = {(k or "").strip().lower(): str(v if v is not None else "").strip() for k, v in r.items()}
        if not r.get("company"):
            continue
        try:
            emp = int(float(r.get("employees") or 0))
        except ValueError:
            emp = 0
        conn.execute(
            """INSERT INTO leads (company, website, industry, employees, contact_name, contact_role, email, description)
               VALUES (?,?,?,?,?,?,?,?)""",
            (r["company"], r.get("website"), r.get("industry"), emp, r.get("contact_name"),
             r.get("contact_role"), r.get("email"), r.get("description")))
        n += 1
    return n

def add_leads(rows: List[dict]) -> int:
    conn = get_conn()
    n = import_rows(conn, rows)
    conn.commit()
    conn.close()
    return n

def all_leads() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM leads ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_lead(lead_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_lead(lead_id: int, **fields):
    fields = {k: v for k, v in fields.items() if k in COLUMNS and k != "company"}
    if not fields:
        return
    sql = ", ".join(f"{k}=?" for k in fields)
    conn = get_conn()
    conn.execute(f"UPDATE leads SET {sql} WHERE id=?", list(fields.values()) + [lead_id])
    conn.commit()
    conn.close()

def log_event(lead_id: int, kind: str, detail: str):
    conn = get_conn()
    conn.execute("INSERT INTO events (lead_id, ts, kind, detail) VALUES (?,?,?,?)", (lead_id, now(), kind, detail))
    conn.commit()
    conn.close()

def lead_events(lead_id: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute("SELECT ts, kind, detail FROM events WHERE lead_id=? ORDER BY id DESC", (lead_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_lead(lead_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM leads WHERE id=?", (lead_id,))
    conn.execute("DELETE FROM events WHERE lead_id=?", (lead_id,))
    conn.commit()
    conn.close()

def stats() -> Dict[str, int]:
    conn = get_conn()
    q = lambda sql: conn.execute(sql).fetchone()[0]
    out = {
        "leads": q("SELECT COUNT(*) FROM leads"),
        "researched": q("SELECT COUNT(*) FROM leads WHERE analyzed=1"),
        "qualified": q("SELECT COUNT(*) FROM leads WHERE qualified=1"),
        "emails_generated": q("SELECT COUNT(*) FROM leads WHERE qualified=1 AND outreach_body!=''"),
        "emails_sent": q("SELECT COUNT(*) FROM leads WHERE send_count>0"),
        "replies": q("SELECT COUNT(*) FROM leads WHERE reply_text!=''"),
        "interested": q("SELECT COUNT(*) FROM leads WHERE status='Interested'"),
    }
    conn.close()
    return out
