"""
Google Maps data extraction via DDG search.
Fetches: rating, review_count, hours, category, address, maps_url.
"""
import re
import time
import requests
from portal.config import HTTP_HEADERS, HTTP_TIMEOUT

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", str(t or "")).strip()


def _extract_rating(text: str) -> dict:
    """Extracts rating (4.5) and review count from text."""
    result = {}
    rating_m = re.search(r"\b([1-5](?:[.,]\d)?)\s*/?\s*5?\b", text)
    if rating_m:
        try:
            result["rating"] = float(rating_m.group(1).replace(",", "."))
        except ValueError:
            pass

    reviews_m = re.search(r"(\d+[\d,\.]*)\s*(?:rese[ñn]as?|reviews?|calificaciones?|opiniones?)", text, re.I)
    if reviews_m:
        num_str = reviews_m.group(1).replace(",", "").replace(".", "")
        try:
            result["review_count"] = int(num_str)
        except ValueError:
            pass

    return result


def search_google_maps(nombre: str, municipio: str, direccion: str = "") -> dict:
    """
    Searches for business on Google Maps via DDG and returns metadata.
    Returns: {maps_url, rating, review_count, category, address, hours_text}
    """
    nombre_limpio = re.sub(
        r"\b(S\.?A\.?S?|SRL|EIRL|LTD|INC|CORP|S\.?A\.?|CIA|COMPANIA|COMPANY|C\s*POR\s*A|SAS|RL|LDC|LLC)\b",
        "", nombre, flags=re.IGNORECASE
    ).strip()

    city = municipio.replace("DISTRITO NACIONAL", "Santo Domingo").title()
    queries = [
        f'"{nombre_limpio}" site:maps.google.com OR site:goo.gl',
        f'"{nombre_limpio}" {city} maps google reseñas',
        f'{nombre_limpio} {city} calificacion google maps',
    ]

    result = {
        "maps_url": "",
        "rating": None,
        "review_count": None,
        "category": "",
        "address": direccion or "",
        "hours_text": "",
        "found": False,
    }

    all_snippets = []
    for q in queries[:2]:
        try:
            with DDGS() as d:
                hits = d.text(q, max_results=5, region="es-419")
                for h in hits:
                    url  = h.get("href", "")
                    body = h.get("body", "")
                    all_snippets.append(body)

                    # Capture Google Maps URL
                    if not result["maps_url"]:
                        if "maps.google" in url or "goo.gl/maps" in url:
                            result["maps_url"] = url
                            result["found"] = True
                        # Extract embedded maps link from snippet
                        maps_in_body = re.search(r"https?://(?:maps\.google\.com|goo\.gl/maps)[^\s\"'<]+", body)
                        if maps_in_body:
                            result["maps_url"] = maps_in_body.group(0)
                            result["found"] = True

            time.sleep(0.5)
        except Exception:
            time.sleep(1)
            continue

    # Parse rating and reviews from snippets
    combined = " ".join(all_snippets)
    rating_data = _extract_rating(combined)
    result.update(rating_data)

    # Extract hours from snippet
    hours_m = re.search(
        r"(?:abierto|open|horario|cierra|closes?)[^\n.]{5,80}",
        combined, re.IGNORECASE
    )
    if hours_m:
        result["hours_text"] = _clean(hours_m.group(0))[:120]

    # Extract category from snippet
    cat_m = re.search(
        r"(?:categoría|category|tipo)[\s:]+([A-Za-záéíóúÁÉÍÓÚ\s]{5,50})",
        combined, re.IGNORECASE
    )
    if cat_m:
        result["category"] = _clean(cat_m.group(1))[:60]

    # Fallback maps URL: generate search link
    if not result["maps_url"]:
        q = f"{nombre_limpio} {direccion or ''} {city}"
        q_enc = re.sub(r"\s+", "+", q.strip())
        result["maps_url"] = f"https://www.google.com/maps/search/?api=1&query={q_enc}"

    return result


def enrich_with_maps(company: dict) -> dict:
    """Wrapper: returns maps metadata merged into a dict."""
    nombre   = company.get("nombre", "")
    municipio = company.get("municipio", "Santo Domingo")
    direccion = company.get("direccion", "")
    try:
        return search_google_maps(nombre, municipio, direccion)
    except Exception:
        return {
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={nombre.replace(' ', '+')}",
            "rating": None,
            "review_count": None,
            "category": "",
            "address": direccion,
            "hours_text": "",
            "found": False,
        }
