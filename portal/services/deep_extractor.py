"""
Deep content extraction — extracts all business intelligence from a scraped page.
Covers: hours, mission/vision, team, FAQ, services (detailed), pricing,
TikTok, Google Maps link, SEO keywords, certifications, about-us.
"""
import re
from urllib.parse import urljoin, urlparse

# ─── Hours ────────────────────────────────────────────────────────────────────

_DAYS_ES = {
    "lunes": "Mon", "martes": "Tue", "miercoles": "Wed", "miércoles": "Wed",
    "jueves": "Thu", "viernes": "Fri", "sabado": "Sat", "sábado": "Sat",
    "domingo": "Sun", "lun": "Mon", "mar": "Tue", "mie": "Wed", "mié": "Wed",
    "jue": "Thu", "vie": "Fri", "sab": "Sat", "sáb": "Sat", "dom": "Sun",
    "monday": "Mon", "tuesday": "Tue", "wednesday": "Wed",
    "thursday": "Thu", "friday": "Fri", "saturday": "Sat", "sunday": "Sun",
}


def extract_hours(soup, html: str) -> dict:
    """Returns dict: {raw_text, structured: [{day, open, close}], all_day_text}"""
    if not soup:
        return {}

    text = soup.get_text(" ", strip=True).lower()
    hours_raw = []

    # Pattern: "Lunes - Viernes: 8:00am - 6:00pm"
    pat1 = re.findall(
        r"(lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo|"
        r"lun|mar|mié|mie|jue|vie|sáb|sab|dom|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"[\s\-–a-záéíóú]*"
        r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*[-–a]\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
        text, re.IGNORECASE
    )
    structured = []
    for day, open_t, close_t in pat1:
        structured.append({
            "day": _DAYS_ES.get(day.lower(), day.title()),
            "open": open_t.strip(),
            "close": close_t.strip(),
        })

    # Buscar bloque de horario en texto
    horario_match = re.search(
        r"(horario|hours|atenci[oó]n|abierto|open)[^\n]*\n?([\s\S]{0,300})",
        text, re.IGNORECASE
    )
    raw_text = ""
    if horario_match:
        raw_text = re.sub(r"\s+", " ", horario_match.group(0)[:200]).strip()

    # Detectar si trabajan fines de semana
    has_weekend = any(
        k in text for k in ["sábado", "sabado", "domingo", "saturday", "sunday", "fin de semana"]
    )
    # Detectar 24h
    open_24 = "24" in text and any(k in text for k in ["24 hora", "24h", "24/7", "abierto todo"])

    return {
        "raw_text": raw_text,
        "structured": structured[:7],
        "has_weekend": has_weekend,
        "open_24h": open_24,
        "inferred": _infer_hours(structured) if not structured else None,
    }


def _infer_hours(structured: list) -> str:
    return "Lunes a Viernes: 8:00am - 6:00pm (horario típico — confirmar)"


# ─── Mission / Vision ─────────────────────────────────────────────────────────

def extract_mission_vision(soup, html: str) -> dict:
    if not soup:
        return {}
    text = soup.get_text(" ", strip=True)
    result = {}

    for label, key in [
        (r"misi[oó]n", "mission"),
        (r"visi[oó]n", "vision"),
        (r"valores", "values"),
        (r"quienes somos|qui[eé]nes somos|about us|sobre nosotros|nuestra historia", "about"),
    ]:
        m = re.search(
            rf"(?:{label})[:\s]+([^.!?]{{20,400}}[.!?])",
            text, re.IGNORECASE
        )
        if m:
            result[key] = re.sub(r"\s+", " ", m.group(1)).strip()

    return result


# ─── Team ─────────────────────────────────────────────────────────────────────

def extract_team(soup) -> list:
    """Extracts team members: {name, role, photo_url}"""
    if not soup:
        return []

    team = []
    seen_names = set()

    # Look for structured team sections
    for section in soup.find_all(["section", "div", "article"],
                                  class_=re.compile(r"team|equipo|staff|directiv|personal", re.I)):
        for card in section.find_all(["div", "article", "li"],
                                      class_=re.compile(r"member|persona|card|item|col", re.I)):
            name_tag = card.find(["h2", "h3", "h4", "strong", "p"],
                                  class_=re.compile(r"name|nombre|title", re.I))
            if not name_tag:
                name_tag = card.find(["h2", "h3", "h4", "strong"])
            role_tag = card.find(["p", "span"],
                                  class_=re.compile(r"role|cargo|posicion|title|subtitle", re.I))
            img_tag = card.find("img")

            if name_tag:
                name = re.sub(r"\s+", " ", name_tag.get_text()).strip()
                if len(name) < 3 or name in seen_names:
                    continue
                seen_names.add(name)
                member = {"name": name}
                if role_tag:
                    member["role"] = re.sub(r"\s+", " ", role_tag.get_text()).strip()[:80]
                if img_tag and img_tag.get("src"):
                    member["photo_url"] = img_tag["src"]
                team.append(member)
                if len(team) >= 8:
                    break

    return team


# ─── FAQ ──────────────────────────────────────────────────────────────────────

def extract_faq(soup, html: str) -> list:
    """Extracts FAQ pairs: [{question, answer}]"""
    if not soup:
        return []

    faqs = []
    seen = set()

    # 1. Schema.org FAQ markup
    faq_sections = soup.find_all(attrs={"itemtype": re.compile(r"FAQPage|Question", re.I)})
    for section in faq_sections:
        q_tag = section.find(attrs={"itemprop": "name"})
        a_tag = section.find(attrs={"itemprop": "text"})
        if q_tag and a_tag:
            q = re.sub(r"\s+", " ", q_tag.get_text()).strip()
            a = re.sub(r"\s+", " ", a_tag.get_text()).strip()[:300]
            if q not in seen and len(q) > 5:
                seen.add(q)
                faqs.append({"question": q, "answer": a})

    # 2. Details/summary HTML elements
    for details in soup.find_all("details"):
        summary = details.find("summary")
        if summary:
            q = re.sub(r"\s+", " ", summary.get_text()).strip()
            answer_parts = [t for t in details.children if t != summary]
            a = re.sub(r"\s+", " ", " ".join(
                str(p.get_text() if hasattr(p, 'get_text') else p) for p in answer_parts
            )).strip()[:300]
            if q not in seen and len(q) > 5:
                seen.add(q)
                faqs.append({"question": q, "answer": a})

    # 3. h3/h4 followed by p (common FAQ pattern)
    if len(faqs) < 3:
        for h in soup.find_all(["h3", "h4"]):
            q = re.sub(r"\s+", " ", h.get_text()).strip()
            if "?" not in q and not any(k in q.lower() for k in ["preguntas", "faq", "frecuentes"]):
                continue
            nxt = h.find_next_sibling(["p", "div"])
            if nxt:
                a = re.sub(r"\s+", " ", nxt.get_text()).strip()[:300]
                if q not in seen and len(q) > 5:
                    seen.add(q)
                    faqs.append({"question": q, "answer": a})
            if len(faqs) >= 10:
                break

    return faqs[:10]


# ─── Services (detailed) ──────────────────────────────────────────────────────

def extract_services_detailed(soup, html: str) -> list:
    """Returns list of {name, description, price, icon_url}"""
    if not soup:
        return []

    services = []
    seen = set()

    # Common service card selectors
    for container in soup.find_all(
        ["div", "article", "li", "section"],
        class_=re.compile(r"service|servicio|product|producto|card|item|feature|oferta", re.I)
    ):
        name_tag = container.find(["h2", "h3", "h4", "h5", "strong"])
        if not name_tag:
            continue
        name = re.sub(r"\s+", " ", name_tag.get_text()).strip()
        if len(name) < 3 or len(name) > 120 or name in seen:
            continue
        seen.add(name)

        desc_tag = container.find(["p", "span"], class_=re.compile(r"desc|text|body|content", re.I))
        if not desc_tag:
            desc_tag = container.find("p")

        price_tag = container.find(
            ["span", "p", "div"],
            class_=re.compile(r"price|precio|costo|tarifa", re.I)
        )

        svc = {"name": name}
        if desc_tag:
            svc["description"] = re.sub(r"\s+", " ", desc_tag.get_text()).strip()[:250]
        if price_tag:
            price_text = price_tag.get_text()
            price_match = re.search(r"[\$RD][\s]?\d+[\d,\.]*|\d+[\d,\.]+\s*(?:USD|DOP|pesos?)", price_text)
            if price_match:
                svc["price"] = price_match.group(0).strip()

        img = container.find("img")
        if img and img.get("src"):
            svc["icon_url"] = img["src"]

        services.append(svc)
        if len(services) >= 12:
            break

    return services


# ─── Pricing ──────────────────────────────────────────────────────────────────

def extract_pricing(soup, html: str) -> list:
    """Returns list of detected prices/plans"""
    if not html:
        return []

    prices = []
    # Match: $1,500, RD$2,000, 500 USD, 3,500 DOP
    raw = re.findall(
        r"(?:RD\$|USD\$|\$|DOP)?\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|DOP|pesos?)?",
        html
    )
    seen = set()
    for p in raw:
        p = p.strip()
        if p and p not in seen and re.search(r"\d{3,}", p):
            seen.add(p)
            prices.append(p)
        if len(prices) >= 5:
            break

    return prices


# ─── TikTok ───────────────────────────────────────────────────────────────────

def extract_tiktok(html: str) -> str:
    if not html:
        return ""
    m = re.search(r"tiktok\.com/@[\w.\-]+", html, re.IGNORECASE)
    if m:
        link = m.group(0)
        return link if link.startswith("http") else "https://" + link
    return ""


# ─── Google Maps link ─────────────────────────────────────────────────────────

def extract_gmaps_link(soup, html: str, nombre: str, direccion: str, municipio: str) -> str:
    """Tries to find a Google Maps embed or link, or generates a search URL."""
    if not html:
        return ""

    # 1. Existing embed
    iframe_src = re.search(r'src="(https://www\.google\.com/maps[^"]+)"', html)
    if iframe_src:
        return iframe_src.group(1)

    # 2. maps.google.com link in page
    link_match = re.search(r"https?://(?:maps\.google\.com|goo\.gl/maps)[^\s\"'<]+", html)
    if link_match:
        return link_match.group(0)

    # 3. Generate search URL from known data
    query = f"{nombre} {direccion or ''} {municipio or 'Santo Domingo'}"
    query = re.sub(r"\s+", "+", query.strip())
    return f"https://www.google.com/maps/search/?api=1&query={query}"


# ─── Certifications / Awards ──────────────────────────────────────────────────

def extract_certifications(soup, html: str) -> list:
    if not soup:
        return []
    certs = []
    kw = ["iso", "certificad", "acreditad", "premio", "award", "reconocimiento",
          "membresía", "asociad", "afiliado", "licencia", "autorizado"]
    text = soup.get_text(" ", strip=True)
    for sent in re.split(r"[.!?\n]", text):
        s = sent.strip()
        if any(k in s.lower() for k in kw) and 10 < len(s) < 200:
            certs.append(s)
        if len(certs) >= 5:
            break
    return certs


# ─── About / History ──────────────────────────────────────────────────────────

def extract_about(soup) -> dict:
    """Extracts about-us, founding year, history narrative."""
    if not soup:
        return {}

    result = {}
    text = soup.get_text(" ", strip=True)

    # Founded year
    year_match = re.search(r"\b(19[89]\d|20[012]\d)\b", text)
    if year_match:
        result["founded_year"] = year_match.group(1)

    # About-us paragraph
    for tag in soup.find_all(["section", "div"],
                               class_=re.compile(r"about|nosotros|historia|story|empresa", re.I)):
        paragraphs = tag.find_all("p")
        if paragraphs:
            about_text = " ".join(p.get_text() for p in paragraphs[:3])
            about_text = re.sub(r"\s+", " ", about_text).strip()[:600]
            if len(about_text) > 50:
                result["about_text"] = about_text
                break

    # Experience mention
    exp_match = re.search(
        r"(\d+)\s+a[ñn]os?\s+(?:de\s+)?(?:experiencia|trayectoria|en\s+el\s+mercado)",
        text, re.IGNORECASE
    )
    if exp_match:
        result["years_experience"] = int(exp_match.group(1))

    return result


# ─── SEO Keywords ─────────────────────────────────────────────────────────────

def extract_seo_keywords(nombre: str, sector: str, municipio: str,
                          services: list, title: str, description: str) -> list:
    """Generates primary and secondary SEO keyword suggestions."""
    city = municipio.replace("DISTRITO NACIONAL", "Santo Domingo").title()
    sector_clean = re.sub(r"[/\\].*", "", sector).strip().lower()

    primary = []
    secondary = []

    # Sector-based primary keywords
    sector_kw = {
        "hoteles": ["hotel en santo domingo", "hospedaje santo domingo"],
        "turismo": ["agencia de turismo santo domingo", "tour republica dominicana"],
        "inmobiliaria": ["inmobiliaria santo domingo", "apartamentos en venta santo domingo"],
        "salud": ["clinica en santo domingo", "medico en santo domingo"],
        "medicina": ["medico en santo domingo", "clinica medica santo domingo"],
        "educacion": ["colegio en santo domingo", "escuela privada santo domingo"],
        "seguros": ["seguros en santo domingo", "seguro medico dominicana"],
        "finanzas": ["servicios financieros santo domingo", "prestamos santo domingo"],
        "construccion": ["constructora santo domingo", "empresa constructora rd"],
        "restaurante": ["restaurante en santo domingo", "comida en santo domingo"],
        "logistica": ["empresa logistica santo domingo", "transporte de carga rd"],
        "consultoria": ["consultoria empresarial santo domingo", "asesoria empresas rd"],
    }

    for k, v in sector_kw.items():
        if k in sector_clean:
            primary.extend(v)
            break

    if not primary:
        primary = [f"{sector_clean} en {city}", f"{sector_clean} santo domingo"]

    # Service-based secondary keywords
    for svc in services[:5]:
        svc_name = svc.get("name", "") if isinstance(svc, dict) else str(svc)
        svc_clean = re.sub(r"\s+", " ", svc_name).strip().lower()
        if len(svc_clean) > 3:
            secondary.append(f"{svc_clean} en {city}")

    # Brand keyword
    nombre_clean = re.sub(
        r"\b(S\.?A\.?S?|SRL|EIRL|LTD|INC|CORP)\b", "", nombre, flags=re.IGNORECASE
    ).strip()
    secondary.append(nombre_clean)

    return {
        "primary": primary[:3],
        "secondary": list(dict.fromkeys(secondary))[:6],
        "local": [f"{sector_clean} {city.lower()}", f"mejor {sector_clean} santo domingo"],
    }


# ─── Payment Methods ──────────────────────────────────────────────────────────

def extract_payment_methods(html: str) -> list:
    if not html:
        return []
    methods = []
    kw_map = {
        "Tarjeta de crédito": ["visa", "mastercard", "amex", "american express", "credit card"],
        "Efectivo": ["efectivo", "cash"],
        "Transferencia": ["transferencia", "transfer", "banco"],
        "PayPal": ["paypal"],
        "Pagos en línea": ["pago en línea", "pago online", "stripe", "paymentez"],
        "Cheque": ["cheque"],
    }
    html_lower = html.lower()
    for method, keywords in kw_map.items():
        if any(k in html_lower for k in keywords):
            methods.append(method)
    return methods


# ─── Appointment / Booking ────────────────────────────────────────────────────

def extract_booking_info(soup, html: str) -> dict:
    if not html:
        return {}
    html_lower = html.lower()
    has_booking = any(k in html_lower for k in [
        "reserva", "agendar", "cita", "appointment", "booking", "calendly",
        "cal.com", "acuity", "book now", "schedule", "agenda tu"
    ])
    booking_url = ""
    for pat in [r"calendly\.com/[\w\-/]+", r"cal\.com/[\w\-/]+", r"acuityscheduling\.com/[\w\-/]+"]:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            booking_url = "https://" + m.group(0) if not m.group(0).startswith("http") else m.group(0)
            break

    # Appointment types from text
    appt_types = []
    text = soup.get_text(" ", strip=True) if soup else ""
    for label in ["consulta", "evaluación", "asesoría", "visita", "demo", "llamada"]:
        if label in text.lower():
            appt_types.append(label.title())

    return {
        "has_booking": has_booking,
        "booking_url": booking_url,
        "appointment_types": appt_types[:5],
    }


# ─── Full deep extraction ─────────────────────────────────────────────────────

def deep_extract(soup, html: str, company: dict) -> dict:
    """
    Run all extractors and return a unified deep_data dict.
    company dict must have: nombre, sector, municipio, direccion.
    """
    nombre   = company.get("nombre", "")
    sector   = company.get("sector", "")
    municipio = company.get("municipio", "")
    direccion = company.get("direccion", "")

    services_detailed = extract_services_detailed(soup, html)
    services_simple   = [s.get("name", "") for s in services_detailed if s.get("name")]

    return {
        "hours":          extract_hours(soup, html),
        "mission_vision": extract_mission_vision(soup, html),
        "team":           extract_team(soup),
        "faq":            extract_faq(soup, html),
        "services":       services_detailed,
        "pricing":        extract_pricing(soup, html),
        "tiktok":         extract_tiktok(html),
        "gmaps_link":     extract_gmaps_link(soup, html, nombre, direccion, municipio),
        "certifications": extract_certifications(soup, html),
        "about":          extract_about(soup),
        "payment_methods": extract_payment_methods(html),
        "booking":        extract_booking_info(soup, html),
        "seo_keywords":   extract_seo_keywords(
                              nombre, sector, municipio,
                              services_detailed,
                              company.get("titulo_web", ""),
                              company.get("descripcion", "")
                          ),
    }
