"""Monthly, printable activity lists without private roster data."""
from collections import defaultdict
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

MONTHS = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


def calendar_pdf(events, personal=False, runner_id=None):
    groups = defaultdict(list)
    for event in events:
        if personal and runner_id not in event.get('called', []):
            continue
        try:
            start = date.fromisoformat(event.get('date') or '')
            end = max(start, date.fromisoformat(event.get('endDate') or start.isoformat()))
        except (ValueError, TypeError):
            start = end = None
        keys = []
        if start:
            year, month = start.year, start.month
            while (year, month) <= (end.year, end.month):
                keys.append((year, month))
                year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        else:
            month = event.get('month', '')
            keys = [(2027, MONTHS.index(month) + 1)] if month in MONTHS else [(9999, 0)]
        for key in keys:
            groups[key].append((start, end, event))
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=(210*mm, 297*mm), rightMargin=16*mm, leftMargin=16*mm, topMargin=18*mm, bottomMargin=18*mm, title='Calendario por meses · Netkom Miribilla Ecotisa')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Cell', fontName='Helvetica', fontSize=9, leading=13, spaceAfter=0))
    styles['Heading1'].textColor = colors.HexColor('#073bd9')
    styles['Heading2'].textColor = colors.HexColor('#073bd9')
    def p(text):
        return Paragraph(escape(str(text or '')).replace('\n', '<br/>'), styles['Cell'])
    title = 'Mi calendario por meses' if personal else 'Calendario del equipo por meses'
    story = [Paragraph(title, styles['Heading1']), Paragraph('NETKOM · MIRIBILLA × ECOTISA', styles['Normal']), Spacer(1, 5*mm), p('Listado de carreras, competiciones, entrenamientos y concentraciones. Las pruebas de varios días aparecen en cada mes que abarcan.'), Spacer(1, 5*mm)]
    if not groups:
        story.append(p('No hay actividades para este calendario.'))
    for (year, month), rows in sorted(groups.items()):
        heading = f'{MONTHS[month-1]} {year}' if month else 'Fecha por confirmar'
        data = [[p('Días / fechas'), p('Actividad y lugar'), p('Tipo / competición' + (' · convocatoria' if runner_id else ''))]]
        for start, end, event in sorted(rows, key=lambda row: (row[0] is None, row[0] or date.max, row[2].get('name', ''))):
            dates = start.strftime('%d/%m/%Y') if start else 'Día por confirmar'
            if start and end != start:
                dates += ' – ' + end.strftime('%d/%m/%Y')
            details = event.get('category') or 'Actividad'
            if event.get('type'):
                details += ' · ' + event['type']
            if runner_id:
                selected = runner_id in event.get('called', [])
                details += '\n' + (('Convocado' if event.get('callStatus') == 'Publicada' else 'Preconvocado') if selected else 'No convocado')
            data.append([p(dates), p(event.get('name', 'Actividad') + ('\n' + event['place'] if event.get('place') else '')), p(details)])
        table = Table(data, colWidths=[39*mm, 85*mm, 54*mm], repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e7edff')), ('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),7), ('RIGHTPADDING',(0,0),(-1,-1),7), ('TOPPADDING',(0,0),(-1,-1),8), ('BOTTOMPADDING',(0,0),(-1,-1),8), ('LINEBELOW',(0,0),(-1,-1),0.4,colors.HexColor('#d6dfed'))]))
        story += [Paragraph(heading, styles['Heading2']), table, Spacer(1, 6*mm)]
    def footer(canvas, document):
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#526174'))
        canvas.drawString(16*mm, 10*mm, 'Copia del calendario actual · Netkom Miribilla Ecotisa')
        canvas.drawRightString(194*mm, 10*mm, str(document.page))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
