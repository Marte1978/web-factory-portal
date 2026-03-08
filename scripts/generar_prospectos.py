import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment

wb_in = openpyxl.load_workbook(r'C:\Users\Willy\Downloads\empresas_2.xlsx', read_only=True, data_only=True)
ws_in = wb_in.active

sectores_alto = {8, 11, 12, 14, 15, 16, 18}
sectores_medio = {3, 5, 6, 7, 9, 10, 33, 41}
sectores_excluir = {13, 17, 25, 26, 34, 36, 4}

sectores_nombre = {
    3: 'Manufactura', 5: 'Construccion', 6: 'Comercio Mayor',
    7: 'Comercio Minorista', 8: 'Hoteles/Turismo', 9: 'Transporte/Logistica',
    10: 'Finanzas/Bancos', 11: 'Inmobiliaria', 12: 'Servicios Empresariales',
    14: 'Educacion', 15: 'Salud/Medicina',
    16: 'Servicios Sociales', 18: 'Otros Servicios',
    33: 'Manufactura Avanzada', 41: 'Construccion Especializada',
}

municipios_sd = {'DISTRITO NACIONAL', 'SANTO DOMINGO ESTE', 'SANTO DOMINGO OESTE', 'SANTO DOMINGO NORTE'}

empresas = []

for row in ws_in.iter_rows(min_row=2, values_only=True):
    rnc, nombre, calle, num, edif, piso, apto, sector_barrio, muni_cod, muni_nom, tipo, tel1, ext1, empleados, salarios, sector_eco = row

    if str(muni_nom).upper() not in municipios_sd:
        continue
    if not isinstance(empleados, (int, float)) or empleados < 10 or empleados > 500:
        continue

    sec = int(sector_eco) if isinstance(sector_eco, (int, float)) else 0
    if sec in sectores_excluir:
        continue

    sec_nombre = sectores_nombre.get(sec, 'Otro')

    if sec in sectores_alto:
        prioridad = 'ALTA'
        prioridad_num = 3
    elif sec in sectores_medio:
        prioridad = 'MEDIA'
        prioridad_num = 2
    else:
        prioridad = 'BAJA'
        prioridad_num = 1

    sal = salarios if isinstance(salarios, (int, float)) else 0
    score = (empleados * prioridad_num) + (sal / 2000)

    dir_parts = [str(calle or ''), str(num or ''), str(sector_barrio or '')]
    direccion = ', '.join(p for p in dir_parts if p and p not in ('None', ''))

    tel_str = ''
    if isinstance(tel1, (int, float)):
        t = str(int(tel1))
        tel_str = t if len(t) >= 7 else ''
    elif tel1:
        tel_str = str(tel1).strip()

    empresas.append({
        'rnc': rnc,
        'nombre': str(nombre or '').strip(),
        'empleados': int(empleados),
        'salarios_mensual': sal,
        'municipio': str(muni_nom or ''),
        'sector': sec_nombre,
        'prioridad': prioridad,
        'score': score,
        'telefono': tel_str,
        'direccion': direccion,
    })

def sort_key(e):
    p = {'ALTA': 3, 'MEDIA': 2, 'BAJA': 1}[e['prioridad']]
    return (p, e['score'])

empresas.sort(key=sort_key, reverse=True)

alta = [e for e in empresas if e['prioridad'] == 'ALTA']
media = [e for e in empresas if e['prioridad'] == 'MEDIA']
baja = [e for e in empresas if e['prioridad'] == 'BAJA']

print(f"TOTAL: {len(empresas):,} | ALTA: {len(alta):,} | MEDIA: {len(media):,} | BAJA: {len(baja):,}")

# Crear Excel
wb_out = openpyxl.Workbook()
wb_out.remove(wb_out.active)

HEADERS = ['#', 'RNC', 'EMPRESA', 'EMPLEADOS', 'SECTOR', 'MUNICIPIO',
           'TELEFONO', 'DIRECCION', 'SALARIO MASA', 'ESTADO WEB', 'CONTACTO', 'NOTAS']

WIDTHS = [5, 13, 42, 11, 22, 20, 14, 35, 14, 18, 20, 25]

COLORS = {
    'ALTA': ('1B5E20', 'E8F5E9'),
    'MEDIA': ('E65100', 'FFF3E0'),
    'BAJA': ('37474F', 'FAFAFA'),
}

def make_tab(wb, tab_name, datos, header_hex, row_hex):
    ws = wb.create_sheet(title=tab_name)
    hfill = PatternFill('solid', fgColor=header_hex)

    for col, h in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = hfill
        cell.font = Font(color='FFFFFF', bold=True, size=10)
        cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 28

    alt_fill = PatternFill('solid', fgColor=row_hex)
    white_fill = PatternFill('solid', fgColor='FFFFFF')

    for i, e in enumerate(datos, 1):
        r = i + 1
        row_data = [
            i, e['rnc'], e['nombre'], e['empleados'], e['sector'],
            e['municipio'], e['telefono'], e['direccion'],
            e['salarios_mensual'], '', '', ''
        ]
        fill = alt_fill if i % 2 == 0 else white_fill
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=r, column=col, value=val)
            cell.fill = fill
            cell.font = Font(bold=(col == 3), size=9)
            cell.alignment = Alignment(vertical='center', wrap_text=(col in (3, 8)))

    for col, w in enumerate(WIDTHS, 1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = w

    ws.freeze_panes = 'C2'
    return ws

make_tab(wb_out, 'ALTA (' + str(len(alta)) + ')', alta, '1B5E20', 'E8F5E9')
make_tab(wb_out, 'MEDIA (' + str(len(media)) + ')', media, 'E65100', 'FFF3E0')
make_tab(wb_out, 'BAJA (' + str(len(baja)) + ')', baja, '37474F', 'F5F5F5')

# Hoja resumen
ws_r = wb_out.create_sheet(title='RESUMEN', index=0)
ws_r['A1'] = 'PIPELINE DE PROSPECCION - SANTO DOMINGO'
ws_r['A1'].font = Font(bold=True, size=14, color='1B5E20')

data_resumen = [
    ('Categoria', 'Cantidad', 'Sectores principales', 'Accion'),
    ('ALTA prioridad', len(alta), 'Turismo, Salud, Inmobiliaria, Educacion, Consultoria', 'Contactar primero - mayor disposicion a pagar'),
    ('MEDIA prioridad', len(media), 'Construccion, Comercio, Manufactura, Transporte', 'Segunda oleada de contacto'),
    ('BAJA prioridad', len(baja), 'Otros sectores', 'Solo si hay capacidad disponible'),
    ('TOTAL', len(empresas), '', ''),
]

hfill = PatternFill('solid', fgColor='1B5E20')
for col, h in enumerate(data_resumen[0], 1):
    cell = ws_r.cell(row=3, column=col, value=h)
    cell.fill = hfill
    cell.font = Font(color='FFFFFF', bold=True)

fills_r = [PatternFill('solid', fgColor='E8F5E9'), PatternFill('solid', fgColor='FFF3E0'),
           PatternFill('solid', fgColor='F5F5F5'), PatternFill('solid', fgColor='E3F2FD')]
for ri, row in enumerate(data_resumen[1:], 4):
    for ci, val in enumerate(row, 1):
        cell = ws_r.cell(row=ri, column=ci, value=val)
        cell.fill = fills_r[ri - 4]
        if ci == 2:
            cell.font = Font(bold=True, size=12)

ws_r['A9'] = 'INSTRUCCIONES DE USO:'
ws_r['A9'].font = Font(bold=True)
ws_r['A10'] = '1. Abre la pestana ALTA y empieza a investigar cada empresa'
ws_r['A11'] = '2. Busca su sitio web en Google y anota en columna ESTADO WEB:'
ws_r['A12'] = '   - Sin web | Web basica | Web desactualizada | Web OK sin IA'
ws_r['A13'] = '3. Si no tienen web profesional con IA/WhatsApp -> son tu target'
ws_r['A14'] = '4. Usa /proposal en Claude Code con los datos para generar la propuesta'
ws_r['A15'] = '5. Llama al telefono y usa el script de ventas generado'

ws_r['A17'] = 'Generado: 2026-03-08 | Fuente: empresas_2.xlsx | Total analizado: 69,313'
ws_r['A17'].font = Font(italic=True, color='9E9E9E', size=9)

ws_r.column_dimensions['A'].width = 60
ws_r.column_dimensions['B'].width = 12
ws_r.column_dimensions['C'].width = 50
ws_r.column_dimensions['D'].width = 45

output = r'C:\Users\Willy\sistema de egocios\research\prospecto_santo_domingo.xlsx'
wb_out.save(output)
print(f"Guardado en: {output}")
