"""In-memory state + JSON persistence."""
import json
from pathlib import Path
from portal.config import PROGRESS_FILE

# id (str) -> dict with all company + research data
companies: dict[str, dict] = {}

# job_id -> {"company_id": str, "status": pending|running|done|error}
jobs: dict[str, dict] = {}

# company_id -> job_id (active)
active: dict[str, str] = {}


def load_from_progress():
    """Pre-load any previously researched companies from progress file."""
    if not PROGRESS_FILE.exists():
        return
    try:
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for nombre, info in data.items():
            cid = _slug(nombre)
            if cid in companies:
                companies[cid].update(info)
    except Exception:
        pass


def _slug(name: str) -> str:
    import re
    return re.sub(r"[^\w]", "_", name.lower())[:40]


def upsert_company(company: dict) -> str:
    """Add or update company. Returns the id."""
    cid = _slug(company["nombre"])
    if cid not in companies:
        companies[cid] = {}
    companies[cid].update(company)
    companies[cid]["id"] = cid
    return cid


def get_all() -> list[dict]:
    return sorted(companies.values(), key=lambda c: c.get("score", 0), reverse=True)


def get_by_id(cid: str) -> dict | None:
    return companies.get(cid)


def mark_research_done(cid: str, result: dict):
    if cid in companies:
        companies[cid].update(result)
        companies[cid]["researched"] = True
