"""Generates the complete Website Brief Package for a company."""
import json
from pathlib import Path
from datetime import datetime
from portal.config import PACKAGES_DIR


BRIEF_TEMPLATE = """\
# Website Brief: {nombre}
> Generado por Web Factory Portal | {date}
> Listo para construccion con IA

---

## RESUMEN DEL CLIENTE

| Campo | Valor |
|-------|-------|
| Empresa | {nombre} |
| Sector | {sector} |
| Ubicacion | {municipio}, Republica Dominicana |
| Empleados | {empleados} |
| Calidad Web Actual | {calidad_web} |
| Tiene Chat IA | {chat_ia} |
| Es Prospecto Target | {es_target} |

---

## IDENTIDAD DEL NEGOCIO

### Que Hacen
{descripcion}

### Servicios Detectados
{servicios_list}

### Presencia Digital Actual
- Sitio web: {url}
- Facebook: {facebook}
- Instagram: {instagram}
- LinkedIn: {linkedin}
- WhatsApp: {whatsapp_link}

---

## ASSETS DE MARCA

### Logo
- Archivo: `logo.png` (disponible en este paquete)
- Fuente: {logo_source}

### Paleta de Colores
- Color primario: {color_primary}
- Color secundario: {color_secondary}
- Acento: {color_accent}
- Fondo sugerido: {color_bg}
- Texto sugerido: {color_text}
- Paleta completa en: `colors.json`

### Imagenes Disponibles
{images_list}

---

## INSTRUCCIONES PARA CONSTRUCCION DE LA WEB

### Objetivo
Construir un sitio web profesional para **{nombre}** que:
1. Refleje el estilo visual del sector {sector}
2. Use los colores de marca de `colors.json`
3. Incluya el logo de `logo.png`
4. Muestre claramente los servicios de la empresa
5. Tenga boton de WhatsApp prominente para contacto
6. Sea 100% responsive (mobile-first)
7. Tenga CTA claro para que el cliente contacte o solicite cotizacion

### Secciones Obligatorias
- [ ] Hero: nombre de la empresa + propuesta de valor en 1 linea
- [ ] Servicios: listado visual de {num_servicios} servicios/productos
- [ ] Nosotros: breve historia o descripcion del negocio
- [ ] Contacto: telefono, email, direccion, boton WhatsApp
- [ ] Footer: redes sociales + datos legales

### Stack Sugerido
- HTML + Tailwind CSS (archivo unico, sin build step) — recomendado para velocidad
- WhatsApp button: enlace a wa.me/{whatsapp_number}
- Formulario: Formspree (sin backend)

### Tono y Estilo
- Industria: {sector}
- Tono sugerido: {tone}
- Paleta de colores: {color_mood}

---

## CONTEXTO DE VENTAS

### Por Que Necesitan Una Nueva Web
- Calidad actual: **{calidad_web}**
- Le falta: {missing_features}
- Oportunidad: {propuesta}

### Contacto para Negociacion
- Telefono: {telefonos}
- Email: {emails}
- Canal recomendado: {best_channel}

---

## DATOS TECNICOS
> Todos los datos estructurados en `content.json`
> Todos los colores en `colors.json`
> Imagenes en carpeta `images/`

**Paquete generado:** {date}
**Confianza del dato:** {confidence}
"""


def _tone_from_sector(sector: str) -> str:
    sector = sector.lower()
    if any(k in sector for k in ["hotel", "turismo", "vacac"]):
        return "Calido, acogedor, aspiracional"
    if any(k in sector for k in ["salud", "medic", "clinic"]):
        return "Profesional, confiable, humano"
    if any(k in sector for k in ["educac", "colegio", "escuel"]):
        return "Inspirador, accesible, moderno"
    if any(k in sector for k in ["inmob", "construc"]):
        return "Solido, confiable, aspiracional"
    if any(k in sector for k in ["financ", "seguro", "banco"]):
        return "Profesional, seguro, serio"
    return "Profesional, claro, moderno"


def _color_mood(primary: str) -> str:
    if not primary or len(primary) < 4:
        return "Paleta neutra profesional"
    try:
        r = int(primary[1:3], 16)
        g = int(primary[3:5], 16)
        b = int(primary[5:7], 16)
        if b > r and b > g:   return "Azul corporativo — transmite confianza y profesionalismo"
        if g > r and g > b:   return "Verde — transmite crecimiento, salud o sostenibilidad"
        if r > g and r > b:   return "Rojo/naranja — energia, accion, llamada a la atencion"
        return "Paleta equilibrada — versatil y profesional"
    except Exception:
        return "Paleta de marca extraida del logo"


def generate_package(company: dict, soup, html: str, photos: list[str],
                     colors: dict, logo_saved: bool) -> Path:
    """Creates the full package folder and returns its path."""
    import re
    slug = re.sub(r"[^\w]", "_", company["nombre"].lower())[:35]
    pkg_dir = PACKAGES_DIR / slug
    pkg_dir.mkdir(parents=True, exist_ok=True)
    images_dir = pkg_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # content.json
    content = {
        "company_name":    company.get("nombre", ""),
        "sector":          company.get("sector", ""),
        "municipio":       company.get("municipio", ""),
        "empleados":       company.get("empleados", 0),
        "website_url":     company.get("url", ""),
        "web_quality":     company.get("calidad_web", ""),
        "is_target":       company.get("es_target", "SI") == "SI",
        "has_chat_ia":     company.get("chat_ia", "NO") == "SI",
        "has_whatsapp":    company.get("whatsapp", "NO") == "SI",
        "contact": {
            "phones":  [t for t in company.get("telefonos", "").split(" | ") if t],
            "emails":  [e for e in company.get("emails", "").split(" | ") if e],
            "address": company.get("direccion", ""),
        },
        "social_media": {
            "facebook":  company.get("facebook", ""),
            "instagram": company.get("instagram", ""),
            "linkedin":  company.get("linkedin", ""),
            "whatsapp":  company.get("whatsapp_link", ""),
        },
        "about": {
            "meta_description": company.get("descripcion", ""),
            "services_text":    company.get("servicios", ""),
            "title_tag":        company.get("titulo_web", ""),
        },
        "sales_proposal": company.get("propuesta", ""),
        "research_date":  datetime.now().isoformat(),
        "images":         photos,
        "logo_available": logo_saved,
        "colors":         colors,
    }
    (pkg_dir / "content.json").write_text(
        json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # colors.json (already generated, just copy reference)
    colors_path = pkg_dir / "colors.json"
    if not colors_path.exists():
        colors_path.write_text(json.dumps(colors, ensure_ascii=False, indent=2), encoding="utf-8")

    # Build services list for brief
    servicios = company.get("servicios", "")
    if servicios:
        servicios_list = "\n".join(
            f"- {s.strip()}" for s in servicios.split("|") if s.strip()
        )
    else:
        servicios_list = "- (Investigar directamente en el sitio web)"

    images_list = "\n".join(f"- `images/{p}`" for p in photos) if photos else "- (No se encontraron fotos en el sitio)"
    if logo_saved:
        images_list = "- `logo.png` (logo principal)\n" + images_list

    telefonos = company.get("telefonos", company.get("telefono", ""))
    wa_number = re.sub(r"\D", "", telefonos.split("|")[0] if telefonos else "")
    missing = []
    if company.get("calidad_web") in ("SIN WEB", "CAIDA", "BASICA"):
        missing.append("sitio web profesional")
    if company.get("chat_ia") == "NO":
        missing.append("chat IA / chatbot")
    if company.get("whatsapp") == "NO":
        missing.append("boton WhatsApp")
    missing_str = ", ".join(missing) if missing else "actualizacion general"

    phones_list = content["contact"]["phones"]
    emails_list = content["contact"]["emails"]
    best_channel = "WhatsApp" if wa_number else ("Email" if emails_list else "Telefono")

    primary = colors.get("dominant", "#2B5EA7")
    palette = colors.get("palette", [])

    brief = BRIEF_TEMPLATE.format(
        nombre=company.get("nombre", ""),
        date=datetime.now().strftime("%d/%m/%Y %H:%M"),
        sector=company.get("sector", ""),
        municipio=company.get("municipio", ""),
        empleados=company.get("empleados", 0),
        calidad_web=company.get("calidad_web", ""),
        chat_ia=company.get("chat_ia", "NO"),
        es_target=company.get("es_target", "SI"),
        descripcion=company.get("descripcion", "(Sin descripcion disponible)"),
        servicios_list=servicios_list,
        url=company.get("url", "No encontrado"),
        facebook=company.get("facebook", "No encontrado"),
        instagram=company.get("instagram", "No encontrado"),
        linkedin=company.get("linkedin", "No encontrado"),
        whatsapp_link=company.get("whatsapp_link", "No encontrado"),
        logo_source="Descargado del sitio web" if logo_saved else "No disponible",
        color_primary=primary,
        color_secondary=palette[1] if len(palette) > 1 else "#FFFFFF",
        color_accent=colors.get("accent_suggestion", primary),
        color_bg=colors.get("background_suggestion", "#F8F9FA"),
        color_text=colors.get("text_suggestion", "#1A1A1A"),
        images_list=images_list,
        num_servicios=len([s for s in servicios.split("|") if s.strip()]) if servicios else 3,
        whatsapp_number=wa_number,
        tone=_tone_from_sector(company.get("sector", "")),
        color_mood=_color_mood(primary),
        propuesta=company.get("propuesta", ""),
        missing_features=missing_str,
        telefonos=telefonos,
        emails=", ".join(emails_list) if emails_list else "No encontrado",
        best_channel=best_channel,
        confidence="ALTA" if company.get("url") else "MEDIA",
    )

    (pkg_dir / "brief.md").write_text(brief, encoding="utf-8")
    return pkg_dir
