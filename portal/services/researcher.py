"""
Core research engine — full pipeline with deep extraction.
Emits SSE progress events at each step.
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
from portal.services.deep_extractor import deep_extract
from portal.services.google_maps import enrich_with_maps

# ─── Import core research functions ───────────────────────────────────────────
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
    Full 12-level research pipeline for one company.
    emit(event_type, data) sends SSE events to the browser.
    Returns updated company dict with all research results.
    """
    nombre = company["nombre"]
    cid    = company["id"]
    loop   = asyncio.get_event_loop()

    async def step(event: str, msg: str, pct: int, extra: dict = {}):
        await emit("progress", {"step": event, "msg": msg, "pct": pct,
                                "company_id": cid, **extra})

    await step("start", f"Iniciando investigacion de {nombre}", 3)

    # ── 1. DDG Search ─────────────────────────────────────────────────────────
    await step("search", "Buscando en DuckDuckGo...", 8)
    try:
        results, nombre_limpio = await loop.run_in_executor(None, buscar, nombre)
    except Exception as e:
        results, nombre_limpio = [], nombre
        await step("search_warn", f"Busqueda limitada: {e}", 10)
    await asyncio.sleep(0.3)

    # ── 2. Find official URL ───────────────────────────────────────────────────
    await step("url", "Detectando sitio web oficial...", 14)
    url_oficial = detectar_url(results, nombre, nombre_limpio)
    if not url_oficial and company.get("url"):
        url_oficial = company["url"]
    await step("url", f"Web: {url_oficial or 'NO ENCONTRADA'}", 18, {"url": url_oficial})

    # ── 3. Scrape site ────────────────────────────────────────────────────────
    soup, html, url_final = None, "", url_oficial
    if url_oficial:
        await step("scrape", "Analizando sitio web...", 22)
        try:
            soup, html, url_final = await loop.run_in_executor(None, scrape, url_oficial)
        except Exception as e:
            await step("scrape_warn", f"Error accediendo al sitio: {e}", 25)

    # ── 4. Extract basic web info ─────────────────────────────────────────────
    await step("extract", "Extrayendo informacion basica...", 28)
    info = extraer(soup, html, url_final)
    calidad, sc = score_web(soup, html, url_oficial)
    chat = tiene_chat(html)
    wa   = tiene_whatsapp(html)

    # Phones + emails + socials from all sources
    snippet_text = " ".join(r.get("body", "") for r in results)
    tels = list(dict.fromkeys(
        [t for t in ([company.get("telefono", "")] + info["tel"].split(" | ") + phones_from(snippet_text)) if t]
    ))
    emails = list(dict.fromkeys(
        [e for e in (info["email"].split(" | ") + emails_from(snippet_text)) if e]
    ))
    redes = {**socials_from(snippet_text), **info["redes"]}

    desc = info.get("desc", "")
    if not desc and results:
        desc = results[0].get("body", "")[:300]

    # ── 5. Deep extraction ────────────────────────────────────────────────────
    await step("deep", "Extrayendo informacion profunda (horarios, servicios, FAQ, equipo)...", 33)
    base_company = {
        **company,
        "titulo_web": info.get("titulo", ""),
        "descripcion": desc,
    }
    try:
        deep = await loop.run_in_executor(None, deep_extract, soup, html, base_company)
    except Exception as e:
        deep = {}
        await step("deep_warn", f"Extraccion profunda parcial: {e}", 36)

    tiktok = deep.get("tiktok", "")
    if tiktok:
        redes["TikTok"] = tiktok

    await step("deep", (
        f"Servicios: {len(deep.get('services', []))} | "
        f"FAQ: {len(deep.get('faq', []))} | "
        f"Equipo: {len(deep.get('team', []))}"
    ), 38)

    # ── 6. Google Maps ────────────────────────────────────────────────────────
    await step("maps", "Buscando en Google Maps...", 42)
    try:
        maps_data = await loop.run_in_executor(None, enrich_with_maps, {
            "nombre": nombre,
            "municipio": company.get("municipio", ""),
            "direccion": company.get("direccion", ""),
        })
    except Exception:
        maps_data = {"maps_url": "", "rating": None, "review_count": None}

    rating_str = f"{maps_data.get('rating', '-')}/5 ({maps_data.get('review_count', 0)} reseñas)" \
                 if maps_data.get("rating") else "no encontrado"
    await step("maps", f"Google Maps: {rating_str}", 46, {
        "maps_found": maps_data.get("found", False),
        "rating": maps_data.get("rating"),
    })

    # ── 7. Download logo ──────────────────────────────────────────────────────
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
        existing = LOGOS_DIR / f"{slug[:20]}.png"
        if existing.exists():
            shutil.copy(str(existing), str(logo_path))
            logo_saved = True
    await step("logo", f"Logo: {'descargado' if logo_saved else 'no disponible'}", 56)

    # ── 8. Collect photos ─────────────────────────────────────────────────────
    await step("images", "Recopilando fotos del sitio (hasta 12)...", 60)
    photos = []
    if soup and url_final:
        photos = await loop.run_in_executor(None, get_site_photos, url_final, soup, img_dir, 12)
        og_dest = img_dir / "og_image.png"
        og_ok = await loop.run_in_executor(None, get_og_image, url_final, soup, og_dest)
        if og_ok and og_dest.exists():
            photos = ["og_image.png"] + [p for p in photos if p != "og_image.png"]
    await step("images", f"{len(photos)} imagenes guardadas", 68, {"photo_count": len(photos)})

    # ── 9. Extract colors ─────────────────────────────────────────────────────
    await step("colors", "Extrayendo paleta de colores de marca...", 72)
    colors_path = pkg_dir / "colors.json"
    colors = await loop.run_in_executor(None, extract_colors, logo_path, colors_path)
    await step("colors", f"Color dominante: {colors.get('dominant', '#2B5EA7')}", 77,
               {"primary_color": colors.get("dominant", "#2B5EA7")})

    # ── 10. Build full company record ─────────────────────────────────────────
    updated_company = {
        **company,
        # Web presence
        "url":           url_final or url_oficial,
        "calidad_web":   calidad,
        "score_web":     sc,
        "chat_ia":       "SI" if chat else "NO",
        "whatsapp":      "SI" if wa else "NO",
        "es_target":     "NO" if (calidad == "PROFESIONAL" and chat) else "SI",
        # Contact
        "telefonos":     " | ".join(tels[:3]),
        "emails":        " | ".join(emails[:3]),
        # Social media
        "facebook":      redes.get("Facebook",  company.get("facebook", "")),
        "instagram":     redes.get("Instagram", company.get("instagram", "")),
        "linkedin":      redes.get("LinkedIn",  company.get("linkedin", "")),
        "twitter":       redes.get("Twitter",   ""),
        "youtube":       redes.get("YouTube",   ""),
        "tiktok":        redes.get("TikTok",    ""),
        "whatsapp_link": redes.get("WhatsApp",  ""),
        # Content
        "descripcion":   desc,
        "servicios":     info.get("servicios", ""),
        "titulo_web":    info.get("titulo", ""),
        "propuesta":     propuesta(nombre, calidad, chat, wa, company.get("sector", "")),
        # Google Maps
        "gmaps_url":     maps_data.get("maps_url", ""),
        "gmaps_rating":  maps_data.get("rating"),
        "gmaps_reviews": maps_data.get("review_count"),
        "gmaps_hours":   maps_data.get("hours_text", ""),
        # Deep data (structured)
        "deep_data":     deep,
        # Meta
        "researched":    True,
        "package_path":  str(pkg_dir),
    }

    # ── 11. Generate full package ─────────────────────────────────────────────
    await step("brief", "Generando Website Brief Package completo...", 82)
    await loop.run_in_executor(
        None, generate_package,
        updated_company, soup, html, photos, colors, logo_saved, maps_data, deep
    )
    await step("brief", "Brief completo generado (brief.md + content.json + seo.json + chatbot.json)", 95)
    await asyncio.sleep(0.2)

    # ── Done ──────────────────────────────────────────────────────────────────
    await emit("done", {
        "company_id":    cid,
        "nombre":        nombre,
        "calidad_web":   calidad,
        "es_target":     updated_company["es_target"],
        "chat_ia":       "SI" if chat else "NO",
        "url":           url_final or "",
        "logo":          logo_saved,
        "photos":        len(photos),
        "primary_color": colors.get("dominant", "#2B5EA7"),
        "package_path":  str(pkg_dir),
        "gmaps_rating":  maps_data.get("rating"),
        "services_count": len(deep.get("services", [])),
        "faq_count":     len(deep.get("faq", [])),
        "pct":           100,
    })

    return updated_company
