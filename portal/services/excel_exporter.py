"""
Genera reporte Excel de empresas investigadas.
"""
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def export_companies_excel(companies: List[Dict], output_path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Empresas Investigadas"

    # Styles
    header_fill = PatternFill("solid", fgColor="1E3A5F")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    alt_fill = PatternFill("solid", fgColor="F0F4F8")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # Headers
    headers = [
        ("Empresa", 35), ("Sector", 20), ("Ciudad", 18),
        ("Web", 30), ("Calidad Web", 14), ("Score", 8),
        ("Chat IA", 9), ("WhatsApp", 10), ("Maps Rating", 12),
        ("Reseñas Maps", 12), ("Teléfonos", 20), ("Emails", 25),
        ("Facebook", 25), ("Instagram", 25), ("LinkedIn", 25),
        ("Es Target", 10), ("Propuesta de Valor", 45),
    ]

    for col, (header, width) in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        ws.column_dimensions[get_column_letter(col)].width = width

    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"

    # Data rows
    for row_idx, co in enumerate(companies, 2):
        fill = alt_fill if row_idx % 2 == 0 else None
        values = [
            co.get("nombre", ""),
            co.get("sector", ""),
            co.get("municipio", ""),
            co.get("url", ""),
            co.get("calidad_web", ""),
            co.get("score_web", ""),
            co.get("chat_ia", ""),
            co.get("whatsapp", ""),
            co.get("gmaps_rating", ""),
            co.get("gmaps_reviews", ""),
            co.get("telefonos", ""),
            co.get("emails", ""),
            co.get("facebook", ""),
            co.get("instagram", ""),
            co.get("linkedin", ""),
            co.get("es_target", ""),
            co.get("propuesta", ""),
        ]
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            if fill:
                cell.fill = fill
            cell.alignment = left
            # Color Es Target
            if col == 16 and value == "SI":
                cell.font = Font(color="27AE60", bold=True)
            elif col == 16 and value == "NO":
                cell.font = Font(color="E74C3C", bold=True)
            # Color Calidad Web
            if col == 5:
                color_map = {"PROFESIONAL": "27AE60", "INTERMEDIA": "F39C12", "BASICA": "E74C3C"}
                c = color_map.get(value)
                if c:
                    cell.font = Font(color=c, bold=True)
        ws.row_dimensions[row_idx].height = 20

    # Auto-filter
    ws.auto_filter.ref = ws.dimensions

    # Summary sheet
    ws2 = wb.create_sheet("Resumen")
    total = len(companies)
    targets = sum(1 for c in companies if c.get("es_target") == "SI")
    con_web = sum(1 for c in companies if c.get("url"))
    profesional = sum(1 for c in companies if c.get("calidad_web") == "PROFESIONAL")
    intermedia = sum(1 for c in companies if c.get("calidad_web") == "INTERMEDIA")
    basica = sum(1 for c in companies if c.get("calidad_web") == "BASICA")

    summary = [
        ("REPORTE WEB FACTORY", ""),
        (f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ""),
        ("", ""),
        ("Total empresas investigadas", total),
        ("Prospectos TARGET (SI)", targets),
        ("Con sitio web detectado", con_web),
        ("Web PROFESIONAL", profesional),
        ("Web INTERMEDIA", intermedia),
        ("Web BASICA", basica),
        ("Sin web", total - con_web),
    ]
    for r, (label, value) in enumerate(summary, 1):
        ws2.cell(row=r, column=1, value=label).font = Font(bold=(r <= 2))
        ws2.cell(row=r, column=2, value=value)
    ws2.column_dimensions["A"].width = 35
    ws2.column_dimensions["B"].width = 15

    wb.save(str(output_path))
    return output_path
