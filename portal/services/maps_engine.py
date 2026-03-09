"""
Google Maps data enrichment — cuatro estrategias:
  0. Apify Google Places Actor (si hay APIFY_API_TOKEN)
  1. Google Places API (si hay GOOGLE_MAPS_API_KEY)
  2. Scraping directo de ficha de Maps con Playwright
  3. DDG/Bing snippets como fallback
"""
import re
import os
import time
import requests
from typing import Dict
from portal.services.search_engine import get_headers, random_delay, _BASURA


# ─── Estrategia 0: Apify Google Places Actor ─────────────────────────────────

def _apify_maps(nombre: str, municipio: str) -> Dict:
    """Usa Apify Google Maps Scraper — más confiable que Playwright."""
    api_token = os.getenv("APIFY_API_TOKEN", "")
    try:
        import requests as _req
        city = municipio.replace("DISTRITO NACIONAL", "Santo Domingo").title()
        clean = re.sub(r"\b(S\.?A\.?S?|SRL|EIRL|LTD|INC|CORP)\b", "", nombre, flags=re.IGNORECASE).strip()
        query = f"{clean} {city} Dominican Republic"

        # Run actor synchronously (waits for result, max 60s)
        run_resp = _req.post(
            "https://api.apify.com/v2/acts/compass~crawler-google-places/run-sync-get-dataset-items",
            params={"token": api_token, "timeout": 55, "memory": 256},
            json={
                "searchStringsArray": [query],
                "language": "es",
                "maxCrawledPlacesPerSearch": 3,
                "includeReviews": False,
                "scrapeReviewsPersonalData": False,
            },
            timeout=65,
        )

        if run_resp.status_code not in (200, 201):
            return {}

        items = run_resp.json()
        if not items:
            return {}

        place = items[0]

        # Build hours text
        hours_parts = []
        for day in (place.get("openingHours") or []):
            hours_parts.append(f"{day.get('day','')}: {day.get('hours','')}")

        return {
            "rating":       place.get("totalScore"),
            "review_count": place.get("reviewsCount"),
            "maps_url":     place.get("url", ""),
            "hours_text":   " | ".join(hours_parts)[:300],
            "address":      place.get("address", ""),
            "phone":        place.get("phone", ""),
            "website":      place.get("website", ""),
            "found":        True,
        }
    except Exception as e:
        return {}


# ─── Estrategia 1: Google Places API ─────────────────────────────────────────

def _places_api(nombre: str, municipio: str) -> Dict:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return {}
    try:
        city = municipio.replace("DISTRITO NACIONAL", "Santo Domingo").title()
        query = f"{nombre} {city} Dominican Republic"
        r = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": query, "language": "es", "key": api_key},
            timeout=8,
        )
        data = r.json()
        if data.get("status") != "OK" or not data.get("results"):
            return {}

        place = data["results"][0]
        place_id = place.get("place_id", "")

        # Detalles completos
        d = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={
                "place_id": place_id,
                "fields": "name,rating,user_ratings_total,formatted_phone_number,website,opening_hours,formatted_address",
                "language": "es",
                "key": api_key,
            },
            timeout=8,
        ).json().get("result", {})

        hours_text = ""
        if d.get("opening_hours", {}).get("weekday_text"):
            hours_text = " | ".join(d["opening_hours"]["weekday_text"])

        return {
            "rating":       d.get("rating"),
            "review_count": d.get("user_ratings_total"),
            "maps_url":     f"https://www.google.com/maps/place/?q=place_id:{place_id}",
            "hours_text":   hours_text,
            "address":      d.get("formatted_address", ""),
            "found":        True,
        }
    except Exception:
        return {}


# ─── Estrategia 2: Playwright scraping de Maps ───────────────────────────────

def _scrape_maps(nombre: str, municipio: str) -> Dict:
    try:
        from playwright.sync_api import sync_playwright
        import json as _json

        city = municipio.replace("DISTRITO NACIONAL", "Santo Domingo").title()
        clean = re.sub(r"\b(S\.?A\.?S?|SRL|EIRL|LTD|INC|CORP)\b", "", nombre, flags=re.IGNORECASE).strip()
        query = f"{clean} {city}"
        search_url = f"https://www.google.com/maps/search/{requests.utils.quote(query)}"

        result = {"found": False, "maps_url": search_url}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(
                locale="es-419",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            )
            page = ctx.new_page()
            page.route("**/*.{png,jpg,jpeg,gif,webp,ico,mp4}", lambda r: r.abort())

            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(3000)

                # Click primer resultado
                first = page.query_selector("a[href*='/maps/place/']")
                if first:
                    first.click()
                    page.wait_for_timeout(3000)
                    result["maps_url"] = page.url
                    result["found"] = True

                # Extraer rating
                rating_el = page.query_selector("div[role='img'][aria-label*='estrella'], span[aria-hidden='true']:has-text('.')")
                if rating_el:
                    txt = rating_el.get_attribute("aria-label") or rating_el.inner_text()
                    m = re.search(r"(\d[.,]\d)", txt)
                    if m:
                        result["rating"] = float(m.group(1).replace(",", "."))

                # Extraer reseñas
                review_el = page.query_selector("button[aria-label*='reseña'], span[aria-label*='reseña']")
                if review_el:
                    txt = review_el.get_attribute("aria-label") or review_el.inner_text()
                    m = re.search(r"(\d[\d,.]+)", txt)
                    if m:
                        result["review_count"] = int(m.group(1).replace(",", "").replace(".", ""))

                # Extraer horarios
                hours_el = page.query_selector("div[aria-label*='Horario'], table[aria-label*='Horario']")
                if hours_el:
                    result["hours_text"] = hours_el.inner_text()[:300].replace("\n", " | ")

            except Exception:
                pass

            browser.close()
        return result
    except Exception:
        return {}


# ─── Estrategia 3: DDG/Bing snippets (fallback rápido) ───────────────────────

def _snippet_maps(nombre: str, municipio: str) -> Dict:
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        clean = re.sub(r"\b(S\.?A\.?S?|SRL|EIRL|LTD|INC|CORP)\b", "", nombre, flags=re.IGNORECASE).strip()
        city = municipio.replace("DISTRITO NACIONAL", "Santo Domingo").title()
        q = f"{clean} {city} reseñas calificacion google maps"

        snippets = []
        with DDGS() as d:
            for h in d.text(q, max_results=5, region="es-419"):
                snippets.append(h.get("body", ""))
                url = h.get("href", "")
                if "maps.google" in url or "goo.gl/maps" in url:
                    return {"maps_url": url, "found": True,
                            **_parse_snippet_rating(" ".join(snippets))}

        combined = " ".join(snippets)
        return _parse_snippet_rating(combined)
    except Exception:
        return {}


def _parse_snippet_rating(text: str) -> Dict:
    result = {}
    m = re.search(r"\b([1-5](?:[.,]\d)?)\s*/?\s*5\b", text)
    if m:
        try:
            result["rating"] = float(m.group(1).replace(",", "."))
        except Exception:
            pass
    m2 = re.search(r"(\d+[\d,\.]*)\s*(?:rese[ñn]as?|reviews?|calificaciones?)", text, re.I)
    if m2:
        try:
            result["review_count"] = int(m2.group(1).replace(",", "").replace(".", ""))
        except Exception:
            pass
    m3 = re.search(r"(?:abierto|cierra|horario)[^\n.]{5,80}", text, re.I)
    if m3:
        result["hours_text"] = m3.group(0).strip()[:120]
    return result


# ─── Función principal ────────────────────────────────────────────────────────

def get_maps_data(nombre: str, municipio: str, direccion: str = "") -> Dict:
    """
    Obtiene datos de Google Maps con 3 estrategias de fallback.
    Siempre devuelve un dict con keys: maps_url, rating, review_count, hours_text, found.
    """
    city = municipio.replace("DISTRITO NACIONAL", "Santo Domingo").title()
    clean = re.sub(r"\b(S\.?A\.?S?|SRL|EIRL|LTD|INC|CORP)\b", "", nombre, flags=re.IGNORECASE).strip()
    fallback_url = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(clean + ' ' + city)}"

    base = {"maps_url": fallback_url, "rating": None, "review_count": None,
            "hours_text": "", "address": direccion, "found": False}

    # 0. Apify si hay token
    apify_data = _apify_maps(nombre, municipio)
    if apify_data.get("rating") or apify_data.get("found"):
        return {**base, **apify_data}

    # 1. API si hay key
    api_data = _places_api(nombre, municipio)
    if api_data.get("rating"):
        return {**base, **api_data}

    # 2. Playwright scraping
    playwright_data = _scrape_maps(nombre, municipio)
    if playwright_data.get("rating") or playwright_data.get("found"):
        return {**base, **playwright_data}

    # 3. Snippets DDG
    snippet_data = _snippet_maps(nombre, municipio)
    return {**base, **snippet_data}
