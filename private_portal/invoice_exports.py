"""Private expense reports for CONTA and individual activities."""
from datetime import date
from io import BytesIO

from flask import Response, abort, g, request, send_file
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from sqlalchemy import select


def scan_page(title, image=None, note=''):
    with Image.new('RGB', (1240, 1754), 'white') as page:
        draw = ImageDraw.Draw(page)
        font = ImageFont.load_default(size=25)
        draw.text((45, 40), title[:86], fill='#173047', font=font)
        if image is not None:
            scan = ImageOps.exif_transpose(image).convert('RGB')
            try:
                with ImageOps.contain(scan, (1150, 1600), Image.Resampling.LANCZOS) as fitted:
                    page.paste(fitted, ((1240 - fitted.width) // 2, 100))
            finally:
                scan.close()
        else:
            draw.text((45, 110), note, fill='#842f2b', font=font)
        output = BytesIO()
        page.save(output, format='PDF', resolution=150, quality=82)
    output.seek(0)
    return PdfReader(output)


def register_invoice_exports(app, Record, Document, cipher, unseal, audit, require):
    def report_entries():
        event_id = request.args.get('event', '')
        start, end = request.args.get('from', ''), request.args.get('to', '')
        try:
            start = date.fromisoformat(start).isoformat() if start else ''
            end = date.fromisoformat(end).isoformat() if end else ''
        except ValueError:
            abort(400, 'Introduce fechas válidas')
        if start and end and start > end:
            abort(400, 'La fecha inicial debe ser anterior o igual a la final')
        if event_id:
            event = g.db.get(Record, event_id)
            if not event or event.kind != 'event':
                abort(404, 'Actividad no encontrada')
        entries = []
        for row in g.db.scalars(select(Record).where(Record.kind == 'module:entry')):
            data = unseal(row.data)
            if data.get('direction') != 'Gasto' or data.get('status') == 'Anulado':
                continue
            if event_id and data.get('event') != event_id:
                continue
            day = data.get('date') or ''
            if (start or end) and (not day or (start and day < start) or (end and day > end)):
                continue
            entries.append((row.id, data))
        return sorted(entries, key=lambda item: (not item[1].get('date'), item[1].get('date') or '', item[0]))

    @app.get('/api/invoices/report.xlsx')
    @require('director')
    def invoice_report():
        entries = report_entries()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Relación de gastos'
        sheet.append(['Justificante', 'Fecha', 'Proveedor', 'NIF / CIF', 'N.º de factura',
                      'Concepto', 'Categoría', 'Actividad', 'Partida', 'Base (€)', 'IVA (€)',
                      'Importe (€)', 'Estado', 'Archivos adjuntos', 'Club que paga', 'Quién paga', 'Fecha de pago', 'Criterio de reparto', '% Miribilla personalizado'])
        for entry_id, data in entries:
            event = g.db.get(Record, data['event']) if data.get('event') else None
            budget = g.db.get(Record, data['budget']) if data.get('budget') else None
            count = len(g.db.scalars(select(Document.id).where(Document.kind == 'invoice:' + entry_id)).all())
            sheet.append([
                'G-'+entry_id[:12].upper(), data.get('date', ''), data.get('counterparty', ''),
                data.get('taxId', ''), data.get('reference', ''), data.get('concept', ''),
                data.get('category', ''), unseal(event.data).get('name', '') if event else '',
                unseal(budget.data).get('category', '') if budget else '',
                data.get('baseAmount', 0) / 100, data.get('taxAmount', 0) / 100,
                data.get('amount', 0) / 100, data.get('status', ''), count or 'Sin adjuntar', data.get('payerClub') or 'Sin asignar', data.get('paidBy',''), data.get('paymentDate',''), data.get('allocationRule',''), data.get('miribillaPercent',''),
            ])
            for cell in sheet[sheet.max_row]:
                if isinstance(cell.value, str):
                    cell.data_type = 's'
            for cell in sheet[sheet.max_row][9:12]:
                cell.number_format = '#,##0.00'
        sheet.auto_filter.ref = sheet.dimensions
        sheet.freeze_panes = 'C2'
        sheet.print_title_rows = '1:1'
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.orientation = 'landscape'
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='173047')
            cell.alignment = Alignment(wrap_text=True)
        for index, width in enumerate([15, 13, 29, 15, 18, 32, 17, 24, 23, 14, 13, 14, 15, 20, 20, 25, 15, 24, 20], 1):
            sheet.column_dimensions[get_column_letter(index)].width = width
        sheet.append(['TOTAL'])
        for col in ('J', 'K', 'L'):
            cell = sheet[f'{col}{sheet.max_row}']
            cell.value = f'=SUM({col}2:{col}{sheet.max_row-1})' if entries else 0
            cell.number_format = '#,##0.00'
            cell.font = Font(bold=True)
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        audit('invoice_report_exported', str(len(entries)))
        return send_file(output, as_attachment=True, download_name='Relacion_de_gastos.xlsx',
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    @app.get('/api/invoices/report.pdf')
    @require('director')
    def invoice_pack():
        writer = PdfWriter()
        count = 0
        for entry_id, data in report_entries():
            documents = g.db.scalars(select(Document).where(Document.kind == 'invoice:' + entry_id)
                                     .order_by(Document.created, Document.id))
            for number, document in enumerate(documents, 1):
                title = f'G-{entry_id[:12].upper()} · {number} · ' + (data.get('counterparty') or data.get('concept') or 'Justificante')
                raw = BytesIO(cipher.decrypt(document.content))
                try:
                    if document.mime == 'application/pdf':
                        reader = PdfReader(raw)
                        if reader.is_encrypted or not reader.pages:
                            raise PdfReadError('PDF unavailable')
                    else:
                        with Image.open(raw) as image:
                            reader = scan_page(title, image)
                    writer.append(reader, outline_item=title[:120], import_outline=False,
                                  excluded_fields=['/Annots', '/AA'])
                except (PdfReadError, OSError, ValueError, TypeError):
                    writer.append(scan_page(title, note='Archivo pendiente de revisión. Descárgalo desde CONTA.'),
                                  outline_item=title[:120], import_outline=False)
                count += 1
        if not count:
            abort(400, 'No hay facturas adjuntas en el periodo seleccionado')
        output = BytesIO()
        writer.write(output)
        output.seek(0)
        audit('invoice_pack_exported', str(count))
        return Response(iter(lambda: output.read(64 * 1024), b''), mimetype='application/pdf',
                        headers={'Content-Disposition': 'attachment; filename="Facturas_escaneadas.pdf"'})
