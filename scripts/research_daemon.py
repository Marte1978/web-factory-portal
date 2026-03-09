"""
Research Daemon — polls Supabase research_queue and processes jobs locally.
Runs on your PC, picks up research requests from the portal, investigates
companies and uploads results back to Supabase.

Run: py scripts/research_daemon.py
     py scripts/research_daemon.py --once   (process queue once, then exit)
"""
import sys, io, os, json, re, time, argparse, traceback
# Robust UTF-8 stdout
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    elif hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

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
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}

BASE_DIR     = Path(r"C:\Users\Willy\sistema de egocios")
PACKAGES_DIR = BASE_DIR / "packages"
POLL_INTERVAL = 8  # seconds between queue polls


# ─── Research imports ─────────────────────────────────────────────────────────
sys.path.insert(0, str(BASE_DIR))
from scripts.investigar_100 import (
    extraer, score_web, propuesta, tiene_chat, tiene_whatsapp,
    phones_from, emails_from, socials_from,
)
# Nuevos motores mejorados
from portal.services.search_engine import buscar_multi, detect_official_url
from portal.services.scraper import scrape_smart
from portal.services.maps_engine import get_maps_data
from portal.services.image_collector import get_logo, get_og_image, get_site_photos
from portal.services.color_extractor import extract_colors
from portal.services.brief_generator import generate_package
from portal.services.deep_extractor import deep_extract


# ─── Supabase helpers ─────────────────────────────────────────────────────────

def supabase_get(path: str, params: str = "") -> list:
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{path}?{params}",
                     headers=HEADERS, timeout=15)
    if r.status_code == 200:
        return r.json()
    return []


def supabase_patch(path: str, data: dict) -> bool:
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{path}",
                       headers={**HEADERS, "Prefer": "return=minimal"},
                       json=data, timeout=15)
    return r.status_code in (200, 204)


def supabase_upsert(table: str, data: dict) -> bool:
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}",
                      headers={**HEADERS, "Prefer": "return=minimal,resolution=merge-duplicates"},
                      json=data, timeout=20)
    return r.status_code in (200, 201)


def upload_file(local_path: Path, storage_path: str, content_type: str = None) -> bool:
    if not local_path.exists():
        return False
    if content_type is None:
        ext = local_path.suffix.lower()
        content_type = {
            ".png": "image/png", ".jpg": "image/jpeg",
            ".json": "application/json", ".md": "text/markdown",
            ".zip": "application/zip",
        }.get(ext, "application/octet-stream")
    with open(local_path, "rb") as f:
        data = f.read()
    r = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/packages/{storage_path}",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
                 "Content-Type": content_type, "x-upsert": "true"},
        data=data, timeout=90,
    )
    return r.status_code in (200, 201)


def slug(nombre: str) -> str:
    return re.sub(r"[^\w]", "_", nombre.lower())[:35]


# ─── Progress emitter ─────────────────────────────────────────────────────────

def make_emitter(queue_id: str, company_id: str):
    """Returns a sync emit function that updates Supabase research_queue."""
    def emit(event: str, data: dict):
        if event == "progress":
            supabase_patch(
                f"research_queue?id=eq.{queue_id}",
                {
                    "status":       "processing",
                    "progress_pct": data.get("pct", 0),
                    "progress_msg": data.get("msg", ""),
                    "updated_at":   datetime.now().isoformat(),
                }
            )
        elif event == "done":
            supabase_patch(
                f"research_queue?id=eq.{queue_id}",
                {
                    "status":       "done",
                    "progress_pct": 100,
                    "progress_msg": "Investigacion completada",
                    "updated_at":   datetime.now().isoformat(),
                }
            )
        elif event == "error":
            supabase_patch(
                f"research_queue?id=eq.{queue_id}",
                {
                    "status":    "error",
                    "error_msg": data.get("msg", "Unknown error"),
                    "updated_at": datetime.now().isoformat(),
                }
            )
    return emit


# ─── Research pipeline (sync version) ────────────────────────────────────────

def research_company_sync(company: dict, emit) -> dict:
    nombre = company.get("nombre", "")

    def step(event, msg, pct):
        print(f"    [{pct:3}%] {msg}")
        emit("progress", {"step": event, "msg": msg, "pct": pct,
                           "company_id": company.get("id", "")})

    step("start", f"Iniciando: {nombre}", 3)

    # 1. Búsqueda multi-fuente (DDG → Google → Bing)
    step("search", "Buscando en múltiples fuentes (DDG / Google / Bing)...", 8)
    try:
        results, nombre_limpio = buscar_multi(nombre)
        step("search", f"Encontrados {len(results)} resultados", 11)
    except Exception:
        results, nombre_limpio = [], nombre

    # 2. URL oficial
    step("url", "Detectando sitio web oficial...", 14)
    url_oficial = detect_official_url(results, nombre, nombre_limpio) or company.get("url", "")
    step("url", f"Web: {url_oficial or 'NO ENCONTRADA'}", 18)

    # 3. Scrape inteligente (requests → Playwright si necesario)
    soup, html, url_final = None, "", url_oficial
    if url_oficial:
        step("scrape", "Analizando sitio (con fallback JS si es necesario)...", 22)
        try:
            soup, html, url_final = scrape_smart(url_oficial)
            method = "Playwright" if (soup and len(html) > 2000 and "ng-version" not in html) else "requests"
            step("scrape", f"Sitio cargado — {len(html):,} chars", 26)
        except Exception:
            pass

    # 4. Basic extract
    step("extract", "Extrayendo informacion...", 28)
    info = extraer(soup, html, url_final)
    calidad, sc = score_web(soup, html, url_oficial)
    chat = tiene_chat(html)
    wa   = tiene_whatsapp(html)

    snippet_text = " ".join(r.get("body", "") for r in results)
    tels   = list(dict.fromkeys([t for t in ([company.get("telefono","")]
              + info["tel"].split(" | ") + phones_from(snippet_text)) if t]))
    emails = list(dict.fromkeys([e for e in info["email"].split(" | ")
              + emails_from(snippet_text) if e]))
    redes  = {**socials_from(snippet_text), **info["redes"]}
    desc   = info.get("desc","") or (results[0].get("body","")[:300] if results else "")

    # 5. Deep extract
    step("deep", "Extraccion profunda (horarios, FAQ, equipo)...", 33)
    base_c = {**company, "titulo_web": info.get("titulo",""), "descripcion": desc}
    try:
        deep = deep_extract(soup, html, base_c)
    except Exception:
        deep = {}
    if deep.get("tiktok"):
        redes["TikTok"] = deep["tiktok"]
    step("deep", f"Servicios: {len(deep.get('services',[]))} | FAQ: {len(deep.get('faq',[]))}", 38)

    # 6. Google Maps (API → Playwright → DDG snippets)
    step("maps", "Obteniendo datos de Google Maps...", 42)
    try:
        maps_data = get_maps_data(
            nombre,
            company.get("municipio", ""),
            company.get("direccion", ""),
        )
        rating_str = f"{maps_data['rating']}/5 ({maps_data.get('review_count',0)} reseñas)" if maps_data.get("rating") else "no encontrado"
        step("maps", f"Maps: {rating_str}", 46)
    except Exception:
        maps_data = {"maps_url": "", "rating": None, "review_count": None, "hours_text": "", "found": False}

    # 7. Logo
    step("logo", "Descargando logo...", 50)
    s = slug(nombre)
    pkg_dir   = PACKAGES_DIR / s
    img_dir   = pkg_dir / "images"
    logo_path = pkg_dir / "logo.png"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    logo_saved = get_logo(url_final, soup, logo_path) if soup and url_final else False
    step("logo", f"Logo: {'OK' if logo_saved else 'no disponible'}", 56)

    # 8. Photos
    step("images", "Recopilando fotos (hasta 12)...", 60)
    photos = []
    if soup and url_final:
        photos = get_site_photos(url_final, soup, img_dir, 12)
        og_dest = img_dir / "og_image.png"
        if get_og_image(url_final, soup, og_dest):
            photos = ["og_image.png"] + [p for p in photos if p != "og_image.png"]
    step("images", f"{len(photos)} imagenes", 68)

    # 9. Colors
    step("colors", "Extrayendo paleta de colores...", 72)
    colors_path = pkg_dir / "colors.json"
    colors = extract_colors(logo_path, colors_path)
    step("colors", f"Color: {colors.get('dominant','#2B5EA7')}", 77)

    # 10. Build company record
    updated = {
        **company,
        "url": url_final or url_oficial,
        "calidad_web": calidad, "score_web": sc,
        "chat_ia": "SI" if chat else "NO",
        "whatsapp": "SI" if wa else "NO",
        "es_target": "NO" if (calidad == "PROFESIONAL" and chat) else "SI",
        "telefonos": " | ".join(tels[:3]),
        "emails":    " | ".join(emails[:3]),
        "facebook":  redes.get("Facebook",""), "instagram": redes.get("Instagram",""),
        "linkedin":  redes.get("LinkedIn",""),  "twitter":   redes.get("Twitter",""),
        "youtube":   redes.get("YouTube",""),   "tiktok":    redes.get("TikTok",""),
        "whatsapp_link": redes.get("WhatsApp",""),
        "descripcion": desc, "servicios": info.get("servicios",""),
        "titulo_web": info.get("titulo",""),
        "propuesta": propuesta(nombre, calidad, chat, wa, company.get("sector","")),
        "gmaps_url": maps_data.get("maps_url",""),
        "gmaps_rating": maps_data.get("rating"),
        "gmaps_reviews": maps_data.get("review_count"),
        "gmaps_hours": maps_data.get("hours_text",""),
        "primary_color": colors.get("dominant","#2B5EA7"),
        "logo_available": logo_saved,
        "photo_count": len(photos),
        "researched": True, "package_ready": True,
        "research_date": datetime.now().isoformat(),
        "deep_data": deep,
    }

    # 11. Generate brief package
    step("brief", "Generando Website Brief Package...", 82)
    generate_package(updated, soup, html, photos, colors, logo_saved, maps_data, deep)
    step("brief", "Brief generado", 90)

    return updated, photos, colors


def upload_results(company: dict, photos: list, s: str):
    """Upload all package files to Supabase Storage."""
    import zipfile
    pkg_dir = PACKAGES_DIR / s

    # Upload files
    upload_file(pkg_dir / "logo.png",      f"{s}/logo.png")
    upload_file(pkg_dir / "brief.md",      f"{s}/brief.md",     "text/markdown")
    upload_file(pkg_dir / "content.json",  f"{s}/content.json")
    upload_file(pkg_dir / "colors.json",   f"{s}/colors.json")
    upload_file(pkg_dir / "seo.json",      f"{s}/seo.json")
    upload_file(pkg_dir / "chatbot.json",  f"{s}/chatbot.json")

    img_dir = pkg_dir / "images"
    if img_dir.exists():
        for img in img_dir.iterdir():
            if img.suffix.lower() in (".png",".jpg",".jpeg",".webp"):
                upload_file(img, f"{s}/images/{img.name}")

    # Create and upload ZIP (skip images > 5MB to keep zip small)
    zip_path = pkg_dir / "package.zip"
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for f in pkg_dir.rglob("*"):
            if f.is_file() and f.name != "package.zip":
                if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and f.stat().st_size > 500_000:
                    continue  # skip large images from zip (already uploaded individually)
                zf.write(str(f), f.relative_to(pkg_dir))
    if zip_path.stat().st_size < 20_000_000:  # only upload if < 20MB
        upload_file(zip_path, f"{s}/package.zip")


# ─── Main daemon loop ─────────────────────────────────────────────────────────

def process_one(job: dict):
    queue_id   = job["id"]
    company_id = job["company_id"]
    print(f"\n  Processing: {job['company_name']} (queue: {queue_id[:8]}...)")

    # Mark as processing
    supabase_patch(f"research_queue?id=eq.{queue_id}", {
        "status": "processing",
        "progress_pct": 1,
        "progress_msg": "Iniciando investigacion...",
        "updated_at": datetime.now().isoformat(),
    })

    # Fetch company from DB
    rows = supabase_get("companies", f"id=eq.{company_id}&limit=1")
    if not rows:
        supabase_patch(f"research_queue?id=eq.{queue_id}", {
            "status": "error",
            "error_msg": f"Company {company_id} not found in DB",
            "updated_at": datetime.now().isoformat(),
        })
        return

    company = rows[0]
    emit = make_emitter(queue_id, company_id)

    try:
        updated, photos, colors = research_company_sync(company, emit)

        # Upload to Storage
        s = slug(company.get("nombre", company_id))
        print(f"  Uploading files to Supabase Storage...")
        upload_results(updated, photos, s)

        # Update DB record
        db_record = {k: v for k, v in updated.items()
                     if k not in ("deep_data", "logo", "package_path")}
        db_record["id"] = company_id
        supabase_upsert("companies", db_record)

        emit("done", {"company_id": company_id})
        print(f"  Done: {company.get('nombre','')} — {len(photos)} fotos subidas")

    except Exception as e:
        err = str(e)
        print(f"  ERROR: {err}")
        traceback.print_exc()
        emit("error", {"msg": err})


def main():
    parser = argparse.ArgumentParser(description="Research Daemon")
    parser.add_argument("--once", action="store_true", help="Process queue once then exit")
    args = parser.parse_args()

    print("=" * 60)
    print("  RESEARCH DAEMON — Web Factory Portal")
    print("  Escuchando Supabase research_queue...")
    print("  Ctrl+C para detener")
    print("=" * 60)

    while True:
        try:
            # Poll for pending jobs
            jobs = supabase_get(
                "research_queue",
                "status=eq.pending&order=created_at.asc&limit=3"
            )

            if jobs:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {len(jobs)} trabajo(s) en cola")
                for job in jobs:
                    process_one(job)
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] En espera...", end="\r")

        except KeyboardInterrupt:
            print("\n\nDaemon detenido.")
            break
        except Exception as e:
            print(f"\nERROR en daemon: {e}")

        if args.once:
            break

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
