"""
Motor de búsqueda multi-estrategia para empresas dominicanas.
Prioridad: URL directa verificada → DDG API (retry) → Bing requests → fallback
"""
import re
import time
import random
import requests
from typing import List, Dict, Tuple
from urllib.parse import urlparse, quote


# ─── User-Agent pool ──────────────────────────────────────────────────────────

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

def random_ua() -> str:
    return random.choice(_UA_POOL)

def random_delay(base: float = 0.8, jitter: float = 1.2):
    time.sleep(base + random.random() * jitter)

def get_headers() -> Dict:
    return {
        "User-Agent": random_ua(),
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    }


# ─── Limpieza de nombre ───────────────────────────────────────────────────────

_ABBREVS = {
    " STO DGO": " SANTO DOMINGO",
    " STO. DGO": " SANTO DOMINGO",
    " STO.DGO": " SANTO DOMINGO",
}

def clean_company_name(nombre: str) -> str:
    upper = nombre.upper()
    for abbr, full in _ABBREVS.items():
        upper = upper.replace(abbr, full)
    cleaned = re.sub(
        r"\b(S\.?\s*A\.?S?|SRL|EIRL|LTD|INC|CORP|S\.?\s*A\.?|CIA|COMPANIA|COMPANY|"
        r"C\s*POR\s*A|SAS|RL|LDC|LLC|S\.R\.L\.)\b",
        "", upper, flags=re.IGNORECASE
    )
    return re.sub(r"\s+", " ", cleaned).strip()


# ─── Sitios a ignorar ─────────────────────────────────────────────────────────

_BASURA = {
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "google.com", "wikipedia.org", "wikimedia.org",
    "tripadvisor.com", "booking.com", "trustpilot.com", "glassdoor.com",
    "reddit.com", "quora.com", "amazon.com", "ebay.com", "mercadolibre.com",
    "indeed.com", "bing.com", "yahoo.com", "tiktok.com",
    "dondeir.com", "donde.com.do", "1411.com.do",
    "hotels.com", "expedia.com", "airbnb.com", "despegar.com", "agoda.com",
    "kayak.com", "trivago.com", "orbitz.com", "priceline.com",
    "support.google", "dgii.gov", "rccmdo.do",
    "zhihu.com", "baidu.com", "openai.com", "chatgpt.com",
    "yelu.do", "yelu.com", "paginas-amarillas.do", "empresa.info",
    "jooble.org", "computrabajo.com", "bumeran.com",
}

def _is_basura(url: str) -> bool:
    url_l = url.lower()
    return any(b in url_l for b in _BASURA)


# ─── Estrategia 1: URL directa verificada ────────────────────────────────────

_STOP = {"de","del","la","el","los","las","y","e","a","en","con","por",
         "para","sa","sas","srl","ltd","inc","corp","cia","the","and",
         "santo","domingo","republica","dominicana","norte","este","oeste",
         "produccion","internacional","empresa"}

def _key_words(nombre_limpio: str) -> List[str]:
    return [w.lower() for w in re.split(r"[\s\-_&.,/]+", nombre_limpio)
            if len(w) >= 3 and w.lower() not in _STOP]

_RD_BODY_MARKERS = ("dominicana", "santo domingo", "republica dominicana",
                    "santiago de los caballeros", "la romana", "san pedro de macoris",
                    "dgii", "republica dom")

def _verify_url(url: str, keywords: List[str], timeout: int = 6) -> bool:
    try:
        r = requests.get(url, timeout=timeout, headers=get_headers(),
                         allow_redirects=True)
        if r.status_code not in (200, 403):
            return False
        body = r.text.lower()
        final_url = r.url.lower()

        kw_matches = sum(1 for kw in keywords if len(kw) > 3 and kw in body)
        if kw_matches == 0:
            return False

        # .do TLD domains are RD by definition — accept with any keyword match
        is_do_domain = (re.search(r'\.(com\.do|org\.do|edu\.do|net\.do|gob\.do|do)(/|$)', final_url) is not None)
        if is_do_domain:
            return True

        # For generic TLDs (.com/.net), require RD geographic context in body
        has_rd_context = any(m in body for m in _RD_BODY_MARKERS)
        return has_rd_context and kw_matches >= 1
    except Exception:
        return False

_GENERIC_WORDS = {"hotel", "editorial", "clinica", "hospital", "empresa", "grupo",
                  "centro", "club", "colegio", "academia", "escuela", "school",
                  "institute", "comercial", "industrial", "constructora"}

def guess_url(nombre_limpio: str) -> str:
    """Construye y verifica URLs candidatas para una empresa."""
    words = _key_words(nombre_limpio)
    if not words:
        return ""

    kw = words[:5]  # palabras para verificar

    # Generar slugs candidatos en orden de especificidad descendente
    slugs = []
    # Combinaciones multi-palabra (más específicas primero)
    if len(words) >= 3:
        slugs.append(words[0] + words[1] + words[2])
        slugs.append(words[0] + "-" + words[1] + "-" + words[2])
    if len(words) >= 2:
        slugs.append(words[0] + words[1])
        slugs.append(words[0] + "-" + words[1])
    # Palabras 2+3 (útil para "HOTEL VILLA TAINA" → villataina)
    if len(words) >= 3:
        slugs.append(words[1] + words[2])
        slugs.append(words[1] + "-" + words[2])
    # Palabras solas: solo si tienen 5+ caracteres Y no son genéricas
    for w in words[:3]:
        if len(w) >= 5 and w not in _GENERIC_WORDS:
            slugs.append(w)

    checked = set()
    for slug in slugs[:6]:
        for tld in [".com.do", ".do", ".com", ".net"]:
            for prefix in ["www.", ""]:
                url = f"https://{prefix}{slug}{tld}"
                if url in checked:
                    continue
                checked.add(url)
                try:
                    # HEAD rápido primero
                    r = requests.head(url, timeout=4, headers=get_headers(), allow_redirects=True)
                    if r.status_code in (200, 301, 302, 403):
                        if _verify_url(url, kw, timeout=5):
                            return r.url or url  # URL final tras redirects
                except Exception:
                    continue
    return ""


# ─── Estrategia 2: DuckDuckGo API con reintentos ─────────────────────────────

def search_ddg(nombre_limpio: str, max_results: int = 8) -> List[Dict]:
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                return []

        words = _key_words(nombre_limpio)[:4]
        short = " ".join(words)

        # Intentar varias queries de más estricta a más amplia
        queries = [
            f'"{short}" site:.do',
            f'"{short}" "santo domingo" OR "dominicana"',
            f'{short} republica dominicana web',
        ]

        results = []
        for q in queries:
            for attempt in range(2):  # reintentar hasta 2 veces por query
                try:
                    with DDGS() as d:
                        hits = list(d.text(q, max_results=max_results, region="es-419"))
                    # Filtrar basura
                    hits = [h for h in hits if h.get("href") and not _is_basura(h.get("href",""))]
                    results.extend(hits)
                    random_delay(0.6, 0.8)
                    break
                except Exception:
                    random_delay(2.0, 1.0)
            if len(results) >= 4:
                break

        return results
    except Exception:
        return []


# ─── Estrategia 3: Yahoo search (más permisivo) ───────────────────────────────

def search_yahoo(nombre_limpio: str, max_results: int = 8) -> List[Dict]:
    try:
        from bs4 import BeautifulSoup
        words = _key_words(nombre_limpio)[:4]
        short = " ".join(words)
        q = f"{short} dominicana"
        url = f"https://search.yahoo.com/search?p={quote(q)}&ei=UTF-8&fl=1&vl=lang_es"
        r = requests.get(url, headers=get_headers(), timeout=10)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "lxml")
        results = []
        for h3 in soup.find_all("h3", class_=re.compile(r"title|heading", re.I)):
            a = h3.find("a")
            if not a:
                continue
            href = a.get("href", "")
            # Yahoo redirige por /RU= — extraer URL real
            ru = re.search(r"/RU=([^/]+)/", href)
            if ru:
                import urllib.parse
                href = urllib.parse.unquote(ru.group(1))
            if not href.startswith("http") or _is_basura(href):
                continue
            title = a.get_text(strip=True)
            # Buscar snippet
            parent = h3.find_parent("div")
            body = ""
            if parent:
                p = parent.find(["p", "span"], class_=re.compile(r"abs|desc|snippet", re.I))
                if p:
                    body = p.get_text(strip=True)[:250]
            results.append({"href": href, "title": title, "body": body})
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


# ─── Detección de URL oficial ─────────────────────────────────────────────────

_AGGREGATORS = [
    "hotels.com","booking.com","tripadvisor","expedia","airbnb","despegar",
    "hoteles.com","hotel.com","agoda","kayak","trivago","hotels-",
    "orbitz.com","priceline","hostelworld","hostelz",
    "comcaribbean.com","caribe.com","caribetours","caribehotels",
    "support.google","paginas-amarillas","yelp.com","yellowpages",
    "dondeir.com","donde.com.do","1411.com.do","telefono.do","paginasamarillas",
    "jooble.","indeed.","glassdoor.","linkedin.com/company",
    "bancos.do","directoriotelefonica","directorioempresa",
]

def detect_official_url(results: List[Dict], nombre: str, nombre_limpio: str) -> str:
    words = _key_words(nombre_limpio)

    scored = []
    seen_domains = set()

    for r in results:
        url = r.get("href", "")
        if not url or _is_basura(url):
            continue
        if any(agg in url.lower() for agg in _AGGREGATORS):
            continue
        # Skip documents (PDFs, DOCs, etc.) — these are not websites
        if re.search(r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx)(\?|$)', url, re.I):
            continue

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            path = parsed.path
        except Exception:
            domain = ""
            path = ""

        title = (r.get("title") or "").lower()
        body  = (r.get("body")  or "").lower()
        url_l  = url.lower()

        sc = 0
        for w in words:
            if w in domain:   sc += 8   # en dominio = señal fuerte
            if w in url_l:    sc += 4
            if w in title:    sc += 3
            if w in body:     sc += 1

        if domain.endswith(".do"): sc += 8
        if ".do/" in url_l:       sc += 4
        if any(k in body for k in ["santo domingo","republica dominicana","dominicana"]): sc += 3
        if path in ("/", "", "/es/", "/es", "/inicio", "/home"): sc += 2

        # Require at least one keyword in domain or strong body evidence
        domain_match = any(w in domain for w in words)
        if sc > 0 and (domain_match or sc >= 6):
            scored.append((sc, url))

    scored.sort(reverse=True)
    return scored[0][1] if scored else ""


# ─── Motor principal ──────────────────────────────────────────────────────────

def buscar_multi(nombre: str) -> Tuple[List[Dict], str]:
    """
    Búsqueda multi-fuente con fallbacks.
    Retorna (results, nombre_limpio).
    """
    nombre_limpio = clean_company_name(nombre)
    nombre_limpio = re.sub(r"\s+", " ", nombre_limpio).strip()

    results: List[Dict] = []

    # 1. URL directa verificada (más confiable para empresas RD)
    direct_url = guess_url(nombre_limpio)
    if direct_url:
        results.insert(0, {
            "href": direct_url,
            "title": nombre_limpio,
            "body": "dominicana santo domingo empresa",
        })

    # 2. DDG API
    if len(results) < 3:
        results += search_ddg(nombre_limpio)

    # 3. Yahoo (generalmente sin bloqueo)
    if len(results) < 3:
        results += search_yahoo(nombre_limpio)

    return results, nombre_limpio
