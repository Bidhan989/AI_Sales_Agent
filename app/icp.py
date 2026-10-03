"""ICP rules. Qualification is decided by CODE (these rules), not by the LLM.
Edit data/icp.json to change who counts as a good fit."""
import json
from pathlib import Path

ICP_PATH = Path(__file__).resolve().parent.parent / "data" / "icp.json"
DEFAULT = {
    "industries": ["saas", "software", "b2b"],
    "min_employees": 20, "max_employees": 200,
    "target_roles": ["founder", "ceo", "head of sales", "vp sales"],
    "min_score": 80, "followup_days": [3, 4], "max_followups": 2,
}

def load_icp() -> dict:
    try:
        return {**DEFAULT, **json.loads(ICP_PATH.read_text(encoding="utf-8"))}
    except Exception:
        return dict(DEFAULT)

def evaluate(lead: dict, ai: dict) -> dict:
    """Returns {qualified: bool, checks: [(label, passed, detail)]}."""
    icp = load_icp()
    emp = int(lead.get("employees") or 0)
    role = (lead.get("contact_role") or "").lower()
    industry = (lead.get("industry") or "").lower()
    checks = [
        (f"AI fit score >= {icp['min_score']}", ai["fit_score"] >= icp["min_score"], f"score {ai['fit_score']}"),
        (f"Company size {icp['min_employees']}-{icp['max_employees']}",
         icp["min_employees"] <= emp <= icp["max_employees"], f"{emp} employees"),
        ("Target role", any(r in role for r in icp["target_roles"]), lead.get("contact_role") or "no role"),
        ("Industry match", any(i in industry for i in icp["industries"]), lead.get("industry") or "no industry"),
        ("Automation pain point found", len(ai.get("pain_points", [])) > 0, f"{len(ai.get('pain_points', []))} found"),
    ]
    return {"qualified": all(c[1] for c in checks), "checks": checks}
