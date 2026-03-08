"""
Setup Supabase: creates tables, RLS policies and storage bucket.
Run once: py scripts/setup_supabase.py
"""
import sys, io, os, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
from pathlib import Path

# ─── Credentials ──────────────────────────────────────────────────────────────
URL         = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF")

if not URL or not SERVICE_KEY:
    print("ERROR: Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars")
    sys.exit(1)

HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
}

MGMT_HEADERS = {
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
}

SCHEMA_FILE = Path(__file__).parent.parent / "supabase" / "schema.sql"


def run_sql(sql: str, label: str = ""):
    """Execute SQL via Supabase REST RPC."""
    r = requests.post(
        f"{URL}/rest/v1/rpc/exec_sql",
        headers=HEADERS,
        json={"sql": sql},
        timeout=30,
    )
    if r.status_code in (200, 201):
        print(f"  OK  {label}")
        return True
    # Try management API
    r2 = requests.post(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        headers=MGMT_HEADERS,
        json={"query": sql},
        timeout=30,
    )
    if r2.status_code in (200, 201):
        print(f"  OK  {label}")
        return True
    print(f"  ERR {label}: {r2.status_code} {r2.text[:120]}")
    return False


def create_storage_bucket():
    """Create 'packages' bucket as public."""
    r = requests.post(
        f"{URL}/storage/v1/bucket",
        headers=HEADERS,
        json={"id": "packages", "name": "packages", "public": True},
        timeout=15,
    )
    if r.status_code in (200, 201):
        print("  OK  Storage bucket 'packages' created (public)")
    elif "already exists" in r.text.lower() or r.status_code == 409:
        print("  OK  Storage bucket 'packages' already exists")
    else:
        print(f"  ERR Storage bucket: {r.status_code} {r.text[:120]}")

    # Set public policy on bucket
    r2 = requests.put(
        f"{URL}/storage/v1/bucket/packages",
        headers=HEADERS,
        json={"public": True},
        timeout=15,
    )
    if r2.status_code in (200, 201):
        print("  OK  Bucket set to public")


def run_schema():
    """Run schema.sql split by statement."""
    if not SCHEMA_FILE.exists():
        print(f"  ERR Schema file not found: {SCHEMA_FILE}")
        return

    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    # Split on ; but ignore inline comments
    statements = []
    current = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(current).strip()
            if stmt and len(stmt) > 3:
                statements.append(stmt)
            current = []

    print(f"\nEjecutando {len(statements)} sentencias SQL...")
    ok = 0
    for i, stmt in enumerate(statements, 1):
        label = stmt[:60].replace("\n", " ").strip() + "..."
        if run_sql(stmt, label):
            ok += 1
        time.sleep(0.2)
    print(f"\n{ok}/{len(statements)} sentencias ejecutadas.")


def verify_tables():
    """Check tables exist."""
    for table in ["companies", "research_queue"]:
        r = requests.get(
            f"{URL}/rest/v1/{table}?limit=1",
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code == 200:
            print(f"  OK  Tabla '{table}' existe y es accesible")
        else:
            print(f"  ERR Tabla '{table}': {r.status_code} {r.text[:80]}")


def main():
    print("=" * 55)
    print("  SETUP SUPABASE — Web Factory Portal")
    print("=" * 55)
    print(f"\nProyecto: {PROJECT_REF}")
    print(f"URL: {URL}\n")

    print("1. Creando storage bucket...")
    create_storage_bucket()

    print("\n2. Ejecutando schema SQL...")
    run_schema()

    print("\n3. Verificando tablas...")
    verify_tables()

    print("\n" + "=" * 55)
    print("  SETUP COMPLETADO")
    print("  Proximos pasos:")
    print("  1. py scripts/upload_to_supabase.py")
    print("  2. py scripts/research_daemon.py")
    print("=" * 55)


if __name__ == "__main__":
    main()
