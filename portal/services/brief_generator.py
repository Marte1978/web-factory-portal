"""
Generates the complete Website Brief Package for a company.
Output files per company:
  brief.md        — AI handoff document (all sections)
  content.json    — full structured data
  colors.json     — brand palette
  seo.json        — SEO keywords and meta tags
  chatbot.json    — FAQ + chatbot training data
"""
import json
import re
from pathlib import Path
from datetime import datetime
from portal.config import PACKAGES_DIR


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _tone_from_sector(sector: str) -> str:
    s = sector.lower()
    if any(k in s for k in ["hotel", "turismo", "vacac"]):  return "Calido, acogedor, aspiracional"
    if any(k in s for k in ["salud", "medic", "clinic"]):   return "Profesional, confiable, humano"
    if any(k in s for k in ["educac", "colegio", "escuel"]): return "Inspirador, accesible, moderno"
    if any(k in s for k in ["inmob", "construc"]):           return "Solido, confiable, aspiracional"
    if any(k in s for k in ["financ", "seguro", "banco"]):   return "Profesional, seguro, serio"
    if any(k in s for k in ["restaur", "comida", "gastro"]): return "Apetitoso, cercano, invitador"
    if any(k in s for k in ["belleza", "spa", "estetica"]):  return "Elegante, relajante, cuidado"
    return "Profesional, claro, moderno"


def _color_mood(primary: str) -> str:
    if not primary or len(primary) < 4:
        return "Paleta neutra profesional"
    try:
        r = int(primary[1:3], 16)
        g = int(primary[3:5], 16)
        b = int(primary[5:7], 16)
        if b > r and b > g:    return "Azul corporativo — confianza y profesionalismo"
        if g > r and g > b:    return "Verde — crecimiento, salud o sostenibilidad"
        if r > g and r > b:    return "Rojo/naranja — energia, accion, urgencia"
        if r > 200 and g > 200: return "Amarillo/dorado — premium, calidez"
        return "Paleta equilibrada — versatil y profesional"
    except Exception:
        return "Paleta extraida del logo"


def _slug(nombre: str) -> str:
    return re.sub(r"[^\w]", "_", nombre.lower())[:35]


def _wa_number(telefonos: str) -> str:
    if not telefonos:
        return ""
    first = telefonos.split("|")[0].strip()
    digits = re.sub(r"\D", "", first)
    if len(digits) == 10 and digits.startswith("8"):
        return "1" + digits
    if len(digits) == 7:
        return "1809" + digits
    return digits


# ─── Generate package ─────────────────────────────────────────────────────────

def generate_package(
    company: dict,
    soup,
    html: str,
    photos: list,
    colors: dict,
    logo_saved: bool,
    maps_data: dict = None,
    deep: dict = None,
) -> Path:
    """Creates the full package folder with all files and returns its path."""
    maps_data = maps_data or {}
    deep      = deep or {}

    slug    = _slug(company["nombre"])
    pkg_dir = PACKAGES_DIR / slug
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "images").mkdir(exist_ok=True)

    # ── Build content.json ────────────────────────────────────────────────────
    telefonos   = company.get("telefonos", company.get("telefono", ""))
    wa_number   = _wa_number(telefonos)
    phones_list = [t for t in telefonos.split(" | ") if t] if telefonos else []
    emails_list = [e for e in company.get("emails", "").split(" | ") if e]

    services_detailed = deep.get("services", [])
    services_simple   = company.get("servicios", "")
    # If deep extraction got detailed services, prefer those
    if not services_detailed and services_simple:
        services_detailed = [
            {"name": s.strip()} for s in services_simple.split("|") if s.strip()
        ]

    mission_vision = deep.get("mission_vision", {})
    about_deep     = deep.get("about", {})
    hours_data     = deep.get("hours", {})
    team           = deep.get("team", [])
    faq            = deep.get("faq", [])
    booking        = deep.get("booking", {})
    certifications = deep.get("certifications", [])
    payment_methods = deep.get("payment_methods", [])
    seo_keywords   = deep.get("seo_keywords", {})
    pricing        = deep.get("pricing", [])
    gmaps_link     = deep.get("gmaps_link", maps_data.get("maps_url", ""))

    primary_color   = colors.get("dominant", "#2B5EA7")
    palette         = colors.get("palette", [])

    content = {
        # ── Identity ──
        "company_name":  company.get("nombre", ""),
        "sector":        company.get("sector", ""),
        "municipio":     company.get("municipio", ""),
        "city":          company.get("municipio", "").replace("DISTRITO NACIONAL", "Santo Domingo").title(),
        "country":       "República Dominicana",
        "employees":     company.get("empleados", 0),
        "rnc":           company.get("rnc", ""),
        "business_type": company.get("tipo", ""),
        "founded_year":  about_deep.get("founded_year", ""),
        "years_experience": about_deep.get("years_experience", ""),

        # ── Web presence ──
        "website_url":   company.get("url", ""),
        "web_quality":   company.get("calidad_web", ""),
        "web_score":     company.get("score_web", 0),
        "web_title":     company.get("titulo_web", ""),
        "is_target":     company.get("es_target", "SI") == "SI",
        "has_chat_ia":   company.get("chat_ia", "NO") == "SI",
        "has_whatsapp":  company.get("whatsapp", "NO") == "SI",
        "has_booking":   booking.get("has_booking", False),
        "booking_url":   booking.get("booking_url", ""),

        # ── Contact ──
        "contact": {
            "phones":       phones_list,
            "whatsapp_number": wa_number,
            "whatsapp_link": f"https://wa.me/{wa_number}" if wa_number else "",
            "emails":       emails_list,
            "address":      company.get("direccion", ""),
            "gmaps_url":    gmaps_link,
            "gmaps_embed":  f"{gmaps_link}&output=embed" if "maps.google" in gmaps_link else "",
        },

        # ── Social media ──
        "social_media": {
            "facebook":   company.get("facebook", ""),
            "instagram":  company.get("instagram", ""),
            "linkedin":   company.get("linkedin", ""),
            "twitter":    company.get("twitter", ""),
            "youtube":    company.get("youtube", ""),
            "tiktok":     company.get("tiktok", ""),
            "whatsapp":   company.get("whatsapp_link", ""),
        },

        # ── Google Maps ──
        "google_maps": {
            "url":          gmaps_link,
            "rating":       maps_data.get("rating") or company.get("gmaps_rating"),
            "review_count": maps_data.get("review_count") or company.get("gmaps_reviews"),
            "hours_text":   maps_data.get("hours_text", "") or company.get("gmaps_hours", ""),
            "category":     maps_data.get("category", ""),
            "found":        maps_data.get("found", False),
        },

        # ── About ──
        "about": {
            "meta_description": company.get("descripcion", ""),
            "about_text":    about_deep.get("about_text", ""),
            "mission":       mission_vision.get("mission", ""),
            "vision":        mission_vision.get("vision", ""),
            "values":        mission_vision.get("values", ""),
            "history":       mission_vision.get("about", ""),
        },

        # ── Services ──
        "services":           services_detailed,
        "services_count":     len(services_detailed),
        "appointment_types":  booking.get("appointment_types", []),
        "pricing_detected":   pricing,
        "payment_methods":    payment_methods,

        # ── Team ──
        "team": team,

        # ── Hours ──
        "hours": {
            "structured":  hours_data.get("structured", []),
            "raw_text":    hours_data.get("raw_text", ""),
            "has_weekend": hours_data.get("has_weekend", False),
            "open_24h":    hours_data.get("open_24h", False),
            "inferred":    hours_data.get("inferred", ""),
        },

        # ── Certifications ──
        "certifications": certifications,

        # ── Assets ──
        "assets": {
            "logo_available": logo_saved,
            "logo_file":      "logo.png" if logo_saved else "",
            "photos":         photos,
            "photo_count":    len(photos),
            "primary_color":  primary_color,
            "palette":        palette,
            "background_suggestion": colors.get("background_suggestion", "#F8F9FA"),
            "text_suggestion":       colors.get("text_suggestion", "#1A1A1A"),
            "accent_suggestion":     colors.get("accent_suggestion", primary_color),
        },

        # ── Sales ──
        "sales": {
            "proposal":        company.get("propuesta", ""),
            "priority":        company.get("prioridad", ""),
            "missing_features": _missing_features(company),
            "best_channel":    "WhatsApp" if wa_number else ("Email" if emails_list else "Teléfono"),
        },

        # ── Research meta ──
        "research_date": datetime.now().isoformat(),
        "research_confidence": "ALTA" if company.get("url") else "MEDIA",
        "colors":        colors,
    }

    (pkg_dir / "content.json").write_text(
        json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Build seo.json ────────────────────────────────────────────────────────
    seo = {
        "title_tag":        _seo_title(company),
        "meta_description": _seo_description(company, services_detailed),
        "h1_suggestion":    _h1_suggestion(company),
        "keywords":         seo_keywords,
        "local_schema": {
            "@context":   "https://schema.org",
            "@type":      "LocalBusiness",
            "name":       company.get("nombre", ""),
            "telephone":  phones_list[0] if phones_list else "",
            "email":      emails_list[0] if emails_list else "",
            "address": {
                "@type":           "PostalAddress",
                "streetAddress":   company.get("direccion", ""),
                "addressLocality": content["city"],
                "addressCountry":  "DO",
            },
            "url":           company.get("url", ""),
            "sameAs":        [v for v in [
                company.get("facebook", ""),
                company.get("instagram", ""),
                company.get("linkedin", ""),
            ] if v],
            "aggregateRating": {
                "@type":       "AggregateRating",
                "ratingValue": str(maps_data.get("rating", "")),
                "reviewCount": str(maps_data.get("review_count", "")),
            } if maps_data.get("rating") else None,
        },
        "open_graph": {
            "og:title":       company.get("titulo_web") or company.get("nombre", ""),
            "og:description": company.get("descripcion", "")[:160],
            "og:image":       f"images/{photos[0]}" if photos else "logo.png",
            "og:type":        "website",
            "og:url":         company.get("url", ""),
        },
    }
    (pkg_dir / "seo.json").write_text(
        json.dumps(seo, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Build chatbot.json ────────────────────────────────────────────────────
    chatbot = _build_chatbot(company, content, faq, services_detailed, booking, payment_methods)
    (pkg_dir / "chatbot.json").write_text(
        json.dumps(chatbot, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── colors.json ───────────────────────────────────────────────────────────
    colors_path = pkg_dir / "colors.json"
    if not colors_path.exists():
        colors_path.write_text(json.dumps(colors, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── brief.md ──────────────────────────────────────────────────────────────
    brief = _build_brief(company, content, seo, chatbot, photos, logo_saved, colors, maps_data, deep)
    (pkg_dir / "brief.md").write_text(brief, encoding="utf-8")

    return pkg_dir


# ─── SEO helpers ──────────────────────────────────────────────────────────────

def _seo_title(company: dict) -> str:
    nombre = re.sub(r"\b(S\.?A\.?S?|SRL|EIRL|LTD|INC|CORP)\b", "",
                    company.get("nombre", ""), flags=re.IGNORECASE).strip()
    sector = company.get("sector", "").split("/")[0].strip()
    city   = company.get("municipio", "").replace("DISTRITO NACIONAL", "Santo Domingo").title()
    return f"{nombre} | {sector} en {city}"[:60]


def _seo_description(company: dict, services: list) -> str:
    nombre = company.get("nombre", "")
    sector = company.get("sector", "").lower()
    city   = company.get("municipio", "").replace("DISTRITO NACIONAL", "Santo Domingo").title()
    svc_names = [s.get("name", "") if isinstance(s, dict) else str(s) for s in services[:3]]
    svc_str = ", ".join(svc_names) if svc_names else sector
    return f"{nombre} ofrece {svc_str} en {city}. Contactanos hoy."[:160]


def _h1_suggestion(company: dict) -> str:
    nombre = re.sub(r"\b(S\.?A\.?S?|SRL|EIRL|LTD|INC|CORP)\b", "",
                    company.get("nombre", ""), flags=re.IGNORECASE).strip()
    sector = company.get("sector", "").split("/")[0].strip()
    city   = company.get("municipio", "").replace("DISTRITO NACIONAL", "Santo Domingo").title()
    return f"Somos {nombre} — {sector} profesional en {city}"


def _missing_features(company: dict) -> list:
    missing = []
    if company.get("calidad_web") in ("SIN WEB", "CAIDA", "BASICA"):
        missing.append("sitio web profesional")
    if company.get("chat_ia") == "NO":
        missing.append("chat IA / chatbot")
    if company.get("whatsapp") == "NO":
        missing.append("botón WhatsApp")
    if not company.get("instagram"):
        missing.append("presencia en Instagram")
    return missing or ["actualización general"]


# ─── Chatbot builder ──────────────────────────────────────────────────────────

def _build_chatbot(company: dict, content: dict, faq: list,
                   services: list, booking: dict, payment_methods: list) -> dict:
    nombre   = company.get("nombre", "")
    city     = content.get("city", "Santo Domingo")
    phones   = content["contact"]["phones"]
    wa_link  = content["contact"]["whatsapp_link"]
    emails   = content["contact"]["emails"]
    address  = content["contact"]["address"]
    gmaps    = content["contact"]["gmaps_url"]
    hours    = content["hours"].get("raw_text") or "Lunes a Viernes 8am–6pm (confirmar)"

    svc_names = [s.get("name", "") if isinstance(s, dict) else str(s) for s in services[:6]]
    svc_str   = ", ".join(svc_names) if svc_names else "nuestros servicios"

    # Base Q&A
    base_qa = [
        {
            "question": f"¿Qué servicios ofrece {nombre}?",
            "answer": f"Ofrecemos {svc_str}. Para más información contáctenos.",
            "category": "servicios"
        },
        {
            "question": "¿Cuánto cuesta?",
            "answer": f"Los precios varían según el servicio. Contáctanos por WhatsApp o teléfono para obtener una cotización personalizada.",
            "category": "precios"
        },
        {
            "question": "¿Dónde están ubicados?",
            "answer": f"Estamos ubicados en {address or city}, República Dominicana. {f'Ver en mapa: {gmaps}' if gmaps else ''}",
            "category": "ubicacion"
        },
        {
            "question": "¿Cuál es el horario de atención?",
            "answer": hours,
            "category": "horario"
        },
        {
            "question": "¿Cómo puedo contactarlos?",
            "answer": (
                f"Puedes contactarnos por:"
                f"{f' WhatsApp: {wa_link}' if wa_link else ''}"
                f"{f' | Teléfono: {phones[0]}' if phones else ''}"
                f"{f' | Email: {emails[0]}' if emails else ''}"
            ),
            "category": "contacto"
        },
    ]

    if booking.get("has_booking"):
        base_qa.append({
            "question": "¿Cómo puedo agendar una cita?",
            "answer": f"Puedes agendar tu cita {f'en línea: {booking[\"booking_url\"]}' if booking.get('booking_url') else 'contactándonos directamente por WhatsApp o teléfono'}.",
            "category": "citas"
        })

    if payment_methods:
        base_qa.append({
            "question": "¿Qué métodos de pago aceptan?",
            "answer": f"Aceptamos: {', '.join(payment_methods)}.",
            "category": "pagos"
        })

    # Merge with extracted FAQ
    all_qa = base_qa + [
        {**q, "category": "faq_extraido"}
        for q in faq
        if q.get("question") and q.get("answer")
    ]

    return {
        "business_name": nombre,
        "bot_name":      f"Asistente de {nombre.split()[0]}",
        "welcome_message": f"¡Hola! Soy el asistente virtual de {nombre}. ¿En qué puedo ayudarte hoy?",
        "qa_pairs":      all_qa,
        "quick_replies": [
            "📋 Ver servicios",
            "💰 Solicitar cotización",
            "📍 ¿Dónde están?",
            "🕐 Horario de atención",
            f"💬 Hablar por WhatsApp",
        ],
        "escalation_message": f"Para atención personalizada contáctanos por WhatsApp: {wa_link or phones[0] if phones else nombre}",
        "language": "es",
        "context": {
            "sector":   company.get("sector", ""),
            "city":     city,
            "services": svc_names,
        }
    }


# ─── Brief builder ────────────────────────────────────────────────────────────

def _build_brief(company: dict, content: dict, seo: dict, chatbot: dict,
                 photos: list, logo_saved: bool, colors: dict,
                 maps_data: dict, deep: dict) -> str:

    nombre  = company.get("nombre", "")
    sector  = company.get("sector", "")
    city    = content.get("city", "Santo Domingo")
    today   = datetime.now().strftime("%d/%m/%Y %H:%M")

    primary       = colors.get("dominant", "#2B5EA7")
    palette       = colors.get("palette", [])
    tone          = _tone_from_sector(sector)
    color_mood    = _color_mood(primary)
    about         = content.get("about", {})
    contact       = content.get("contact", {})
    social        = content.get("social_media", {})
    gmaps         = content.get("google_maps", {})
    hours         = content.get("hours", {})
    services      = content.get("services", [])
    team          = content.get("team", [])
    certs         = content.get("certifications", [])
    booking       = content.get("has_booking", False)
    payment       = content.get("payment_methods", [])
    seo_kw        = content.get("seo_keywords") or deep.get("seo_keywords", {})
    missing       = content.get("sales", {}).get("missing_features", [])
    wa_link       = contact.get("whatsapp_link", "")
    wa_number     = contact.get("whatsapp_number", "")

    def yn(val):
        return "SI" if val else "NO"

    def fmt_services(svcs):
        if not svcs:
            return "- (Investigar directamente con el cliente)"
        lines = []
        for s in svcs[:10]:
            if isinstance(s, dict):
                line = f"- **{s.get('name', '')}**"
                if s.get("description"):
                    line += f": {s['description'][:120]}"
                if s.get("price"):
                    line += f" *(Precio: {s['price']})*"
            else:
                line = f"- {s}"
            lines.append(line)
        return "\n".join(lines)

    def fmt_team(members):
        if not members:
            return "*(Equipo no detectado — completar con información del cliente)*"
        return "\n".join(
            f"- **{m.get('name','')}** — {m.get('role','')}" for m in members[:6]
        )

    def fmt_faq(pairs):
        if not pairs:
            return "*(Sin FAQ detectado)*"
        lines = []
        for p in pairs[:8]:
            q = p.get("question", "")
            a = p.get("answer", "")
            lines.append(f"**P: {q}**\nR: {a}\n")
        return "\n".join(lines)

    def fmt_hours(h):
        if h.get("raw_text"):
            return h["raw_text"]
        if h.get("structured"):
            return " | ".join(f"{x['day']}: {x['open']}–{x['close']}" for x in h["structured"])
        if h.get("open_24h"):
            return "Abierto 24 horas / 7 días"
        return h.get("inferred") or "*(Confirmar horario con el cliente)*"

    def fmt_socials(s):
        lines = []
        for net, url in s.items():
            if url:
                lines.append(f"- {net}: {url}")
        return "\n".join(lines) if lines else "- *(Sin redes detectadas)*"

    def fmt_images(photos_list):
        if not photos_list:
            return "- *(No se encontraron fotos en el sitio)*"
        lines = []
        if logo_saved:
            lines.append("- `logo.png` — Logo principal")
        for p in photos_list[:12]:
            lines.append(f"- `images/{p}`")
        return "\n".join(lines)

    gmaps_rating_str = (
        f"{gmaps.get('rating')}/5 ({gmaps.get('review_count', 0)} reseñas)"
        if gmaps.get("rating") else "No encontrado"
    )

    brief = f"""# Website Brief: {nombre}
> Generado por Web Factory Portal | {today}
> Listo para construccion con IA — NO compartir con el cliente

---

## 1. RESUMEN EJECUTIVO

| Campo | Valor |
|-------|-------|
| Empresa | **{nombre}** |
| Sector | {sector} |
| Ciudad | {city}, República Dominicana |
| Empleados | {company.get("empleados", "?")} |
| Calidad Web Actual | **{company.get("calidad_web", "?")}** |
| Score Web | {company.get("score_web", 0)}/8 |
| Tiene Chat IA | {company.get("chat_ia", "NO")} |
| Tiene WhatsApp | {company.get("whatsapp", "NO")} |
| Sistema de Citas | {yn(booking)} |
| Es Prospecto Target | **{company.get("es_target", "SI")}** |
| Prioridad | {company.get("prioridad", "?")} |
| Investigado | {today} |

**Lo que le falta:** {", ".join(missing)}

---

## 2. IDENTIDAD DEL NEGOCIO

### Descripcion
{about.get("meta_description") or company.get("descripcion") or "*(Sin descripción detectada — completar)*"}

### Historia / Sobre Nosotros
{about.get("about_text") or "*(No detectada — completar con información del cliente)*"}

### Mision
{about.get("mission") or "*(No detectada — definir con el cliente)*"}

### Vision
{about.get("vision") or "*(No detectada — definir con el cliente)*"}

### Valores
{about.get("values") or "*(No detectados)*"}

### Fundacion
- Año de fundación: {content.get("founded_year") or "*(No detectado)*"}
- Años de experiencia: {content.get("years_experience") or "*(No detectado)*"}
- Certificaciones: {", ".join(certs) if certs else "*(No detectadas)*"}

---

## 3. CONTACTO

| Canal | Dato |
|-------|------|
| Teléfonos | {" | ".join(contact.get("phones", [])) or "*(No encontrado)*"} |
| WhatsApp | {f"[Abrir chat]({wa_link})" if wa_link else "*(No detectado)*"} |
| Emails | {" | ".join(contact.get("emails", [])) or "*(No encontrado)*"} |
| Dirección | {contact.get("address") or "*(No encontrada)*"} |
| Google Maps | {f"[Ver mapa]({contact.get('gmaps_url', '')})" if contact.get("gmaps_url") else "*(No encontrado)*"} |

---

## 4. PRESENCIA DIGITAL

### Sitio Web
- URL: {company.get("url") or "*(Sin sitio web)*"}
- Calidad: {company.get("calidad_web", "?")}
- Título: {company.get("titulo_web") or "*(No detectado)*"}

### Google Maps
- Calificación: {gmaps_rating_str}
- Horario (Maps): {gmaps.get("hours_text") or "*(No detectado)*"}
- Enlace: {gmaps.get("url") or "*(No encontrado)*"}

### Redes Sociales
{fmt_socials(social)}

---

## 5. SERVICIOS Y PRODUCTOS

{fmt_services(services)}

### Tipos de Citas / Agendamiento
- Sistema de citas: {yn(booking)}
- Tipos: {", ".join(content.get("appointment_types", [])) or "*(No detectado)*"}
- Link: {content.get("booking_url") or "*(No configurado)*"}

### Precios Detectados
{", ".join(content.get("pricing_detected", [])) or "*(Precios no publicados — cotizacion directa)*"}

### Metodos de Pago
{", ".join(payment) if payment else "*(No detectados)*"}

---

## 6. EQUIPO

{fmt_team(team)}

---

## 7. HORARIO DE ATENCION

{fmt_hours(hours)}
- Atiende fines de semana: {yn(hours.get("has_weekend"))}
- Abierto 24h: {yn(hours.get("open_24h"))}

---

## 8. ASSETS DE MARCA

### Logo
- Disponible: {yn(logo_saved)}
- Archivo: `logo.png`

### Paleta de Colores
| Tipo | Color |
|------|-------|
| Primario | {primary} |
| Secundario | {palette[1] if len(palette) > 1 else "#FFFFFF"} |
| Acento | {colors.get("accent_suggestion", primary)} |
| Fondo sugerido | {colors.get("background_suggestion", "#F8F9FA")} |
| Texto sugerido | {colors.get("text_suggestion", "#1A1A1A")} |

Mood: *{color_mood}*

### Imágenes
{fmt_images(photos)}

---

## 9. INSTRUCCIONES PARA CONSTRUCCION DE LA WEB

### Objetivo
Construir un sitio web profesional para **{nombre}** ({sector}, {city}) que:
- Use los colores de marca de `colors.json`
- Incluya el logo de `logo.png`
- Muestre claramente los {len(services)} servicios detectados
- Tenga botón WhatsApp prominente → `{wa_link or f"https://wa.me/{wa_number}"}`
- Sea 100% responsive (mobile-first)
- Tenga CTA claro para contacto/cotizacion

### Secciones Obligatorias
- [ ] **Hero**: `{_h1_suggestion(company)}` + CTA botón
- [ ] **Servicios**: {len(services)} servicios con descripción y CTA por servicio
- [ ] **Sobre Nosotros**: historia + equipo + años de experiencia
- [ ] **Reseñas Google**: embed o widget con {gmaps_rating_str}
- [ ] **Contacto**: teléfono, email, dirección, mapa embed, botón WhatsApp
- [ ] **Footer**: redes sociales + datos legales

### Secciones Opcionales (si hay data)
- [ ] **Galería**: {len(photos)} fotos disponibles en `images/`
- [ ] **Blog/Noticias**: si el sector lo amerita
- [ ] **Precios/Planes**: datos en `content.json > pricing_detected`
- [ ] **Agenda Online**: {f"integrar {content.get('booking_url')}" if booking else "Cal.com o Calendly"}
- [ ] **Chat IA**: configurar con `chatbot.json`

### Tono y Estilo
- Sector: {sector}
- Tono: *{tone}*
- Paleta: *{color_mood}*
- Stack sugerido: HTML + Tailwind CSS (un solo archivo, sin build step)
- WhatsApp button: `wa.me/{wa_number}` (flotante en mobile)
- Formulario: Formspree (sin backend)

---

## 10. SEO

- **Title tag**: `{seo.get("title_tag", "")}`
- **Meta description**: `{seo.get("meta_description", "")}`
- **H1 sugerido**: `{seo.get("h1_suggestion", "")}`

### Palabras Clave Primarias
{chr(10).join(f"- {k}" for k in (seo_kw.get("primary", []) if isinstance(seo_kw, dict) else []))}

### Palabras Clave Secundarias
{chr(10).join(f"- {k}" for k in (seo_kw.get("secondary", []) if isinstance(seo_kw, dict) else []))}

### Schema.org Local Business
Incluido en `seo.json` — copiar en `<head>` como JSON-LD.

---

## 11. CHATBOT IA

Archivo completo en `chatbot.json`. Incluye:
- {len(chatbot.get("qa_pairs", []))} pares de preguntas y respuestas
- Mensaje de bienvenida personalizado
- Quick replies configurados
- Categorías: servicios, precios, ubicación, horario, contacto, citas, pagos

### FAQ Extraido del Sitio
{fmt_faq(deep.get("faq", []))}

---

## 12. PROPUESTA DE VENTA

### Por Que Necesitan Una Nueva Web
{company.get("propuesta", "")}

### Canal Recomendado para Contacto
{content.get("sales", {}).get("best_channel", "WhatsApp")} → {wa_link or " | ".join(contact.get("phones", [])) or "contacto directo"}

---

## ARCHIVOS DEL PAQUETE

| Archivo | Contenido |
|---------|-----------|
| `brief.md` | Este documento — handoff completo para el dev IA |
| `content.json` | Todos los datos estructurados de la empresa |
| `seo.json` | Keywords, meta tags, Schema.org |
| `chatbot.json` | FAQ y entrenamiento del chatbot |
| `colors.json` | Paleta de colores extraida del logo |
| `logo.png` | Logo de la empresa |
| `images/` | {len(photos)} fotos del sitio web actual |

**Confianza del dato:** {"ALTA" if company.get("url") else "MEDIA"}
**Generado:** {today}
"""

    return brief


def _h1_suggestion(company: dict) -> str:
    nombre = re.sub(r"\b(S\.?A\.?S?|SRL|EIRL|LTD|INC|CORP)\b", "",
                    company.get("nombre", ""), flags=re.IGNORECASE).strip()
    sector = company.get("sector", "").split("/")[0].strip()
    city   = company.get("municipio", "").replace("DISTRITO NACIONAL", "Santo Domingo").title()
    return f"Somos {nombre} — {sector} profesional en {city}"
