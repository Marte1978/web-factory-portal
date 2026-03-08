"""
Upload all local research results to Supabase.
- Uploads company records to `companies` table
- Uploads logos, images, briefs and ZIPs to Supabase Storage bucket `packages`

Run: py scripts/upload_to_supabase.py
     py scripts/upload_to_supabase.py --only-data   (skip file uploads)
     py scripts/upload_to_supabase.py --only-files  (skip data, only files)
"""
import sys, io, os, json, re, zipfile, time, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
from pathlib import Path
from datetime import datetime

# ─── Credentials ──────────────────────────────────────────────────────────────
SUPABASE_URL  = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SERVICE_KEY   = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SERVICE_KEY:
    print("ERROR: Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars")
    sys.exit(1)

HEADERS = {
    "apikey":         SERVICE_KEY,
    "Authorization":  f"Bearer {SERVICE_KEY}",
    "Content-Type":   "application/json",
    "Prefer":         "return=representation,resolution=merge-duplicates",
}

BASE_DIR     = Path(r"C:\Users\Willy\sistema de egocios")
PACKAGES_DIR = BASE_DIR / "packages"
DATA_JSON    = BASE_DIR / "portal" / "data" / "companies.json"
PROGRESS_F   = BASE_DIR / "research" / "progress_100.json"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def slug(nombre: str) -> str:
    return re.sub(r"[^\w]", "_", nombre.lower())[:35]


def upsert_companies(companies: list) -> int:
    """Upsert list of company dicts into Supabase companies table."""
    ok = 0
    batch_size = 50
    for i in range(0, len(companies), batch_size):
        batch = companies[i:i+batch_size]
        # Clean batch: remove keys not in schema
        clean = []
        for c in batch:
            row = {k: v for k, v in c.items()
                   if k not in ("logo", "package_path", "deep_data", "salarios", "propuesta_generada")}
            # Ensure id exists
            if "id" not in row:
                row["id"] = slug(row.get("nombre", f"company_{i}"))
            # Coerce types
            for bool_field in ("researched", "package_ready", "logo_available"):
                if bool_field in row:
                    row[bool_field] = bool(row[bool_field])
            for int_field in ("empleados", "score_web", "gmaps_reviews", "photo_count"):
                if int_field in row and row[int_field] is not None:
                    try: row[int_field] = int(row[int_field])
                    except (ValueError, TypeError): row[int_field] = None
            for float_field in ("score", "gmaps_rating"):
                if float_field in row and row[float_field] is not None:
                    try: row[float_field] = float(row[float_field])
                    except (ValueError, TypeError): row[float_field] = None
            clean.append(row)

        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/companies",
            headers=HEADERS,
            json=clean,
            timeout=30,
        )
        if r.status_code in (200, 201):
            ok += len(batch)
            print(f"  Subidas {ok}/{len(companies)} empresas...")
        else:
            print(f"  ERR upsert batch {i}: {r.status_code} {r.text[:150]}")
        time.sleep(0.3)
    return ok


def upload_file(local_path: Path, storage_path: str, content_type: str = None) -> bool:
    """Upload a file to Supabase Storage packages bucket."""
    if not local_path.exists():
        return False

    if content_type is None:
        ext = local_path.suffix.lower()
        content_type = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".json": "application/json",
            ".md": "text/markdown", ".zip": "application/zip",
        }.get(ext, "application/octet-stream")

    with open(local_path, "rb") as f:
        data = f.read()

    headers = {
        "apikey":        SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type":  content_type,
        "x-upsert":      "true",
    }

    r = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/packages/{storage_path}",
        headers=headers,
        data=data,
        timeout=30,
    )
    return r.status_code in (200, 201)


def make_zip(pkg_dir: Path, slug_name: str) -> Path:
    """Create a ZIP of the package folder."""
    zip_path = pkg_dir / "package.zip"
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for f in pkg_dir.rglob("*"):
            if f.is_file() and f.name != "package.zip":
                zf.write(str(f), f.relative_to(pkg_dir))
    return zip_path


def upload_package(nombre: str) -> dict:
    """Upload all files for one company package to Storage."""
    s = slug(nombre)
    pkg_dir = PACKAGES_DIR / s
    if not pkg_dir.exists():
        return {"uploaded": 0, "slug": s}

    uploaded = 0
    errors = 0

    # Logo
    logo = pkg_dir / "logo.png"
    if upload_file(logo, f"{s}/logo.png"):
        uploaded += 1

    # JSON files
    for fname in ("content.json", "colors.json", "seo.json", "chatbot.json"):
        if upload_file(pkg_dir / fname, f"{s}/{fname}"):
            uploaded += 1

    # Brief
    if upload_file(pkg_dir / "brief.md", f"{s}/brief.md", "text/markdown"):
        uploaded += 1

    # Images
    img_dir = pkg_dir / "images"
    if img_dir.exists():
        for img in img_dir.iterdir():
            if img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                if upload_file(img, f"{s}/images/{img.name}"):
                    uploaded += 1
                else:
                    errors += 1

    # ZIP
    zip_path = make_zip(pkg_dir, s)
    if upload_file(zip_path, f"{s}/package.zip"):
        uploaded += 1

    return {"uploaded": uploaded, "errors": errors, "slug": s}


def update_company_assets(nombre: str, s: str, photo_count: int, logo: bool):
    """Update company record with asset info after upload."""
    url = f"{SUPABASE_URL}/rest/v1/companies?id=eq.{s}"
    r = requests.patch(
        url,
        headers={**HEADERS, "Prefer": "return=minimal"},
        json={
            "package_ready":  True,
            "logo_available": logo,
            "photo_count":    photo_count,
            "primary_color":  _read_primary_color(s),
        },
        timeout=15,
    )
    return r.status_code in (200, 204)


def _read_primary_color(s: str) -> str:
    colors_f = PACKAGES_DIR / s / "colors.json"
    try:
        return json.loads(colors_f.read_text(encoding="utf-8")).get("dominant", "#2B5EA7")
    except Exception:
        return "#2B5EA7"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Upload research results to Supabase")
    parser.add_argument("--only-data",  action="store_true", help="Skip file uploads")
    parser.add_argument("--only-files", action="store_true", help="Skip data upload")
    parser.add_argument("--company",    type=str, default=None, help="Upload one company by name")
    args = parser.parse_args()

    print("=" * 60)
    print("  UPLOAD TO SUPABASE — Web Factory Portal")
    print("=" * 60)

    # Load companies
    companies = []
    if DATA_JSON.exists():
        companies = json.loads(DATA_JSON.read_text(encoding="utf-8"))
        print(f"\nCompanias en companies.json: {len(companies)}")

    # Load progress (has research results)
    progress = {}
    if PROGRESS_F.exists():
        try:
            progress = json.loads(PROGRESS_F.read_text(encoding="utf-8"))
            print(f"Companias investigadas en progress.json: {len(progress)}")
        except Exception:
            pass

    # Merge research results into company records
    comp_map = {c.get("id", slug(c["nombre"])): c for c in companies}
    for nombre, res in progress.items():
        s = slug(nombre)
        if s in comp_map:
            comp_map[s].update({k: v for k, v in res.items() if k != "logo"})
            comp_map[s]["researched"] = True
        else:
            res["id"] = s
            res["researched"] = True
            comp_map[s] = res

    all_companies = list(comp_map.values())

    # Filter by company name if specified
    if args.company:
        target = args.company.lower()
        all_companies = [c for c in all_companies if target in c.get("nombre", "").lower()]
        print(f"\nFiltrando por: '{args.company}' → {len(all_companies)} empresa(s)")

    # ── Upload data ──
    if not args.only_files:
        print(f"\n1. Subiendo {len(all_companies)} empresas a Supabase DB...")
        ok = upsert_companies(all_companies)
        print(f"   Completado: {ok} empresas en DB")

    # ── Upload files ──
    if not args.only_data:
        researched = [c for c in all_companies
                      if c.get("researched") or c.get("package_ready")
                      or (PACKAGES_DIR / slug(c.get("nombre",""))).exists()]
        print(f"\n2. Subiendo archivos de {len(researched)} paquetes a Storage...")

        total_files = 0
        for i, c in enumerate(researched, 1):
            nombre = c.get("nombre", "")
            s = slug(nombre)
            print(f"  [{i:3}/{len(researched)}] {nombre[:40]}...", end="", flush=True)

            result = upload_package(nombre)
            total_files += result["uploaded"]

            # Count photos
            img_dir = PACKAGES_DIR / s / "images"
            photo_count = len(list(img_dir.glob("*.png"))) if img_dir.exists() else 0
            logo_exists = (PACKAGES_DIR / s / "logo.png").exists()

            update_company_assets(nombre, s, photo_count, logo_exists)
            print(f" {result['uploaded']} archivos subidos")
            time.sleep(0.2)

        print(f"\n   Total archivos subidos: {total_files}")

    print("\n" + "=" * 60)
    print("  UPLOAD COMPLETADO")
    print(f"  Portal: https://willymartetirado.gitlab.io/web-factory-portal")
    print("=" * 60)


if __name__ == "__main__":
    main()
