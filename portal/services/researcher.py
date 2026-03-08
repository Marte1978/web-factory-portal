"""
Core research engine — wraps investigar_100.py functions
and emits SSE progress events at each step.
"""
import asyncio
import re
import shutil
import time
from pathlib import Path
from typing import Callable, Awaitable

from portal.config import PACKAGES_DIR, LOGOS_DIR, HTTP_TIMEOUT
from portal.services.image_collector import get_logo, get_og_image, get_site_photos
from portal.services.color_extractor import extract_colors
from portal.services.brief_generator import generate_package

# ─── Import research functions from existing scripts ──────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.investigar_100 import (
    buscar, detectar_url, scrape, extraer,
    score_web, propuesta, tiene_chat, tiene_whatsapp,
    phones_from, emails_from, socials_from,
)

Emitter = Callable[[str, dict], Awaitable[None]]


async def research_company(company: dict, emit: Emitter) -> dict:
    """
    Full research pipeline for one company.
    emit(event_type, data) sends SSE events to the browser.
    Returns updated company dict with research results.
    """
    nombre = company["nombre"]
    cid    = company["id"]

    async def step(event: str, msg: str, pct: int, extra: dict = {}):
        await emit("progress", {"step": event, "msg": msg, "pct": pct,
                                "company_id": cid, **extra})

    await step("start", f"Iniciando investigacion de {nombre}", 5)

    # ── 1. DDG Search ─────────────────────────────────────────────────────────
    await step("search", "Buscando en DuckDuckGo...", 10)
    try:
        loop = asyncio.get_event_loop()
        results, nombre_limpio = await loop.run_in_executor(None, buscar, nombre)
    except Exception as e:
        results, nombre_limpio = [], nombre
        await emit("progress", {"step": "search_warn", "msg": f"Busqueda limitada: {e}",
                                "pct": 15, "company_id": cid})

    await asyncio.sleep(0.3)

    # ── 2. Find official URL ───────────────────────────────────────────────────
    await step("url", "Detectando sitio web oficial...", 20)
    url_oficial = detectar_url(results, nombre, nombre_limpio)
    if not url_oficial and company.get("url"):
        url_oficial = company["url"]
    await step("url", f"Web: {url_oficial or 'NO ENCONTRADA'}", 25, {"url": url_oficial})

    # ── 3. Scrape site ────────────────────────────────────────────────────────
    soup, html, url_final = None, "", url_oficial
    if url_oficial:
        await step("scrape", f"Analizando sitio web...", 30)
        try:
            soup, html, url_final = await loop.run_in_executor(None, scrape, url_oficial)
        except Exception as e:
            await emit("progress", {"step": "scrape_warn", "msg": f"Error accediendo al sitio: {e}",
                                    "pct": 35, "company_id": cid})

    # ── 4. Extract web info ───────────────────────────────────────────────────
    await step("extract", "Extrayendo informacion del sitio...", 40)
    info = extraer(soup, html, url_final)
    calidad, sc = score_web(soup, html, url_oficial)
    chat = tiene_chat(html)
    wa   = tiene_whatsapp(html)

    # Combine phones/emails from all sources
    snippet_text = " ".join(r.get("body", "") for r in results)
    tels = list(dict.fromkeys(
        [t for t in ([company.get("telefono","")] + info["tel"].split(" | ") + phones_from(snippet_text)) if t]
    ))
    emails = list(dict.fromkeys(
        [e for e in (info["email"].split(" | ") + emails_from(snippet_text)) if e]
    ))
    redes = {**socials_from(snippet_text), **info["redes"]}

    desc = info.get("desc", "")
    if not desc and results:
        desc = results[0].get("body", "")[:300]

    # ── 5. Download logo ──────────────────────────────────────────────────────
    await step("logo", "Descargando logo de la empresa...", 50)
    slug = re.sub(r"[^\w]", "_", nombre.lower())[:35]
    pkg_dir   = PACKAGES_DIR / slug
    img_dir   = pkg_dir / "images"
    logo_path = pkg_dir / "logo.png"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    logo_saved = False
    if soup and url_final:
        logo_saved = await loop.run_in_executor(None, get_logo, url_final, soup, logo_path)
    if not logo_saved:
        # Try copying from existing logos dir
        existing = LOGOS_DIR / f"{slug[:20]}.png"
        if existing.exists():
            shutil.copy(str(existing), str(logo_path))
            logo_saved = True
    await step("logo", f"Logo: {'descargado' if logo_saved else 'no disponible'}", 58)

    # ── 6. Collect photos ─────────────────────────────────────────────────────
    await step("images", "Recopilando imagenes y fotos del sitio...", 62)
    photos = []
    if soup and url_final:
        photos = await loop.run_in_executor(None, get_site_photos, url_final, soup, img_dir, 6)
        # Also get OG image specifically
        og_dest = img_dir / "og_image.png"
        await loop.run_in_executor(None, get_og_image, url_final, soup, og_dest)
        if og_dest.exists():
            photos = ["og_image.png"] + [p for p in photos if p != "og_image.png"]

    await step("images", f"Imagenes guardadas: {len(photos)}", 70, {"photo_count": len(photos)})

    # ── 7. Extract colors ─────────────────────────────────────────────────────
    await step("colors", "Extrayendo paleta de colores de marca...", 75)
    colors_path = pkg_dir / "colors.json"
    colors = await loop.run_in_executor(None, extract_colors, logo_path, colors_path)
    await step("colors", f"Color dominante: {colors.get('dominant','#2B5EA7')}", 80,
               {"primary_color": colors.get("dominant", "#2B5EA7")})

    # ── 8. Generate brief package ─────────────────────────────────────────────
    await step("brief", "Generando Website Brief Package...", 85)

    updated_company = {
        **company,
        "url":          url_final or url_oficial,
        "calidad_web":  calidad,
        "score_web":    sc,
        "chat_ia":      "SI" if chat else "NO",
        "whatsapp":     "SI" if wa else "NO",
        "es_target":    "NO" if (calidad == "PROFESIONAL" and chat) else "SI",
        "telefonos":    " | ".join(tels[:3]),
        "emails":       " | ".join(emails[:2]),
        "facebook":     redes.get("Facebook", company.get("facebook", "")),
        "instagram":    redes.get("Instagram", company.get("instagram", "")),
        "linkedin":     redes.get("LinkedIn", company.get("linkedin", "")),
        "whatsapp_link":redes.get("WhatsApp", ""),
        "descripcion":  desc,
        "servicios":    info.get("servicios", ""),
        "titulo_web":   info.get("titulo", ""),
        "propuesta":    propuesta(nombre, calidad, chat, wa, company.get("sector", "")),
        "researched":   True,
        "package_path": str(pkg_dir),
    }

    await loop.run_in_executor(
        None, generate_package,
        updated_company, soup, html, photos, colors, logo_saved
    )

    await step("brief", "Brief.md y content.json generados", 95)
    await asyncio.sleep(0.2)

    # ── Done ──────────────────────────────────────────────────────────────────
    await emit("done", {
        "company_id":   cid,
        "nombre":       nombre,
        "calidad_web":  calidad,
        "es_target":    updated_company["es_target"],
        "chat_ia":      "SI" if chat else "NO",
        "url":          url_final or "",
        "logo":         logo_saved,
        "photos":       len(photos),
        "primary_color":colors.get("dominant", "#2B5EA7"),
        "package_path": str(pkg_dir),
        "pct":          100,
    })

    return updated_company
