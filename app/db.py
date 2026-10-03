import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sales_agent.db"

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        website TEXT,
        industry TEXT,
        employees INTEGER,
        contact_name TEXT,
        contact_role TEXT,
        email TEXT,
        description TEXT,
        fit_score INTEGER DEFAULT 0,
        status TEXT DEFAULT 'New',
        pain_points TEXT DEFAULT '',
        research TEXT DEFAULT '',
        outreach_subject TEXT DEFAULT '',
        outreach_body TEXT DEFAULT '',
        last_action TEXT DEFAULT '',
        data_source TEXT DEFAULT 'Apollo.io Sourced -> Clay Enriched'
    );
    """)
    
    count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    if count == 0:
        seed = [
            ("FlowPilot", "https://flowpilot.example", "B2B SaaS", 82, "Maya Sharma", "VP Sales", "maya@flowpilot.example",
             "Workflow software for growing B2B teams. Expanding outbound sales operations."),
            ("Northstar CRM", "https://northstar.example", "Sales Tech", 145, "Daniel Lee", "Founder", "daniel@northstar.example",
             "CRM platform serving SMBs with a rapidly growing SDR team."),
            ("MetricLoop", "https://metricloop.example", "Analytics SaaS", 61, "Ava Wilson", "Head of Growth", "ava@metricloop.example",
             "Analytics platform helping revenue teams monitor pipeline and customer acquisition."),
            ("CloudDesk", "https://clouddesk.example", "B2B Software", 34, "Rohan Patel", "CEO", "rohan@clouddesk.example",
             "Cloud productivity startup with a lean sales team seeking automated qualification."),
            ("RetailForge", "https://retailforge.example", "E-commerce", 18, "Nina Park", "Co-founder", "nina@retailforge.example",
             "E-commerce tools provider. Smaller team with lower immediate outbound demand.")
        ]
        conn.executemany("""
            INSERT INTO leads
            (company, website, industry, employees, contact_name, contact_role, email, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, seed)
    
    conn.commit()
    conn.close()

def all_leads() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_lead(lead_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_lead(lead_id: int, **fields):
    allowed = {
        "fit_score", "status", "pain_points", "research",
        "outreach_subject", "outreach_body", "last_action",
        "description", "data_source"
    }
    filtered_fields = {k: v for k, v in fields.items() if k in allowed}
    if not filtered_fields:
        return
    
    sql = ", ".join(f"{k}=?" for k in filtered_fields)
    values = list(filtered_fields.values()) + [lead_id]
    
    conn = get_conn()
    conn.execute(f"UPDATE leads SET {sql} WHERE id=?", values)
    conn.commit()
    conn.close()