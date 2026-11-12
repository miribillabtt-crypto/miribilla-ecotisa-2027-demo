"""Bank statement preview and confirmed one-to-one invoice reconciliation."""
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re
import unicodedata
from zipfile import ZipFile, BadZipFile
from xml.etree.ElementTree import ParseError

from flask import abort, g, jsonify, request
from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel
from sqlalchemy import select, text


def bank_lock():
    if g.db.get_bind().dialect.name == 'postgresql':
        g.db.execute(text('SELECT pg_advisory_xact_lock(20273004)'))


def bank_fingerprint(row):
    return tuple(row.get(key, '') for key in ('date', 'concept', 'reference', 'amount', 'direction'))


def bank_rows(Record, unseal, kind):
    return [(row, unseal(row.data)) for row in g.db.scalars(
        select(Record).where(Record.kind == 'module:'+kind))]


def validate_bank_link(Record, unseal, movement, skip=None):
    target = movement.get('matched')
    if not target:
        return
    entry = g.db.get(Record, target)
    if not entry or entry.kind != 'module:entry':
        abort(400, 'Apunte CONTA no encontrado')
    expense = unseal(entry.data)
    if expense.get('status') == 'Anulado' or (expense.get('amount'),expense.get('direction')) != (movement['amount'],movement['direction']):
        abort(400, 'El importe y el sentido del movimiento deben coincidir con el apunte')
    if any(row.id != skip and data.get('matched') == target for row,data in bank_rows(Record,unseal,'bank')):
        abort(409, 'El apunte ya está conciliado con otro movimiento')


HEADERS = {
    'date': {'fecha', 'fecha operacion', 'fecha de operacion', 'f operacion', 'fecha movimiento', 'fecha de movimiento', 'fecha contable', 'fecha valor', 'fecha de valor', 'date', 'booking date'},
    'concept': {'concepto', 'descripcion', 'movimiento', 'detalle', 'description', 'beneficiario'},
    'amount': {'importe', 'importe eur', 'importe euros', 'importe movimiento', 'importe del movimiento', 'cantidad', 'amount', 'amount eur'},
    'debit': {'debe', 'cargo', 'cargos', 'debito', 'debit', 'importe cargo'},
    'credit': {'haber', 'abono', 'abonos', 'credito', 'credit', 'importe abono'},
    'reference': {'referencia', 'reference', 'id movimiento', 'identificador', 'numero operacion'},
    'direction': {'tipo', 'sentido', 'tipo movimiento', 'tipo de movimiento', 'direccion', 'debit credit'},
}


def normalized(value):
    value = unicodedata.normalize('NFD', str(value or '').lower())
    return ' '.join(re.sub(r'[^a-z0-9 ]',' ',''.join(c for c in value if not unicodedata.combining(c))).split())


def statement_amount(value):
    if value is None or value == '':
        return 0
    if isinstance(value, str):
        value = re.sub(r'(?i)eur|€|\s', '', value).replace('−','-')
        if value.startswith('(') and value.endswith(')'):
            value = '-'+value[1:-1]
        if value.endswith('-'):
            value = '-'+value[:-1]
        if ',' in value:
            value = value.replace('.','').replace(',','.') if value.rfind(',') > value.rfind('.') else value.replace(',','')
        elif re.fullmatch(r'-?\d{1,3}(?:\.\d{3})+',value):
            value = value.replace('.','')
    amount = Decimal(str(value))
    if not amount.is_finite() or amount*100 != (amount*100).to_integral_value() or abs(amount)>1_000_000:
        raise ValueError('Importe no válido')
    return int(amount*100)


def statement_date(value, epoch):
    if isinstance(value, (int,float)) and not isinstance(value,bool):
        value = from_excel(value, epoch)
    if isinstance(value, date):
        return value.strftime('%Y-%m-%d')
    raw = str(value or '').strip()
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        for fmt in ('%d/%m/%Y','%d-%m-%Y','%d.%m.%Y','%d/%m/%y','%d-%m-%y'):
            try:
                return datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                continue
    raise ValueError('Fecha no válida')


def parse_statement(raw):
    with ZipFile(BytesIO(raw)) as container:
        if sum(item.file_size for item in container.infolist()) > 30*1024*1024:
            raise ValueError('El Excel descomprimido es demasiado grande')
    book = load_workbook(BytesIO(raw), read_only=True, data_only=True, keep_links=False)
    try:
        for sheet in book.worksheets:
            rows = sheet.iter_rows(values_only=True, max_col=100)
            for line, values in enumerate(rows, 1):
                if line > 30:
                    break
                names = [normalized(value) for value in values]
                columns = {key: next((index for index,name in enumerate(names) if name in aliases), None)
                           for key,aliases in HEADERS.items()}
                if columns['date'] is not None and any(columns[key] is not None for key in ('amount','debit','credit')):
                    break
            else:
                continue
            if line > 30 or columns['date'] is None or all(columns[key] is None for key in ('amount','debit','credit')):
                continue
            result = []
            for line, values in enumerate(rows, line+1):
                def value(key):
                    index = columns[key]
                    return values[index] if index is not None else None
                if all(value(key) in (None,'') for key in ('date','concept','amount','debit','credit')):
                    continue
                if not value('date') and normalized(value('concept')).startswith(('total','saldo')):
                    continue
                try:
                    day = statement_date(value('date'), book.epoch)
                    if columns['amount'] is not None:
                        amount = statement_amount(value('amount'))
                        direction = normalized(value('direction'))
                        if direction in ('cargo','c','d','debe','debito','gasto','debit'):
                            amount = -abs(amount)
                        elif direction in ('abono','a','h','haber','credito','ingreso','credit'):
                            amount = abs(amount)
                    else:
                        debit,credit = abs(statement_amount(value('debit'))),abs(statement_amount(value('credit')))
                        if debit and credit:
                            raise ValueError('Debe y Haber tienen importe en la misma fila')
                        amount = credit-debit
                except (ValueError,InvalidOperation,OverflowError):
                    raise ValueError(f'Revisa la fecha y el importe de la fila {line}') from None
                if not amount:
                    continue
                result.append(dict(date=day,concept=str(value('concept') or '').strip()[:2500],
                                   reference=str(value('reference') or '').strip()[:2500],
                                   amount=abs(amount),direction='Gasto' if amount<0 else 'Ingreso',matched=''))
                if len(result)>2000:
                    raise ValueError('Máximo 2000 movimientos por importación')
            if not result:
                raise ValueError('No hay movimientos con importe en esa hoja')
            return result
    finally:
        book.close()
    raise ValueError('Faltan las columnas Fecha e Importe, o Fecha y Debe/Haber')


def register_bank_reconciliation(app, Record, Document, seal, unseal, audit, require, body):
    @app.post('/api/bank/preview')
    @require('director')
    def bank_preview():
        file = request.files.get('file')
        if not file:
            abort(400, 'Selecciona un Excel')
        raw = file.read(4*1024*1024+1)
        if len(raw)>4*1024*1024:
            abort(400, 'Máximo 4 MB por Excel')
        try:
            rows = parse_statement(raw)
        except ValueError as error:
            abort(400, str(error))
        except (BadZipFile, KeyError, OSError, TypeError, ParseError):
            abort(400, 'Selecciona un Excel .xlsx válido')
        return jsonify(rows=rows)

    @app.get('/api/bank/reconciliation')
    @require('director')
    def reconciliation():
        movements = bank_rows(Record, unseal, 'bank')
        entries = {row.id: data for row, data in bank_rows(Record, unseal, 'entry')
                   if data.get('status') != 'Anulado'}
        documents = defaultdict(list)
        for document_id, kind in g.db.execute(
            select(Document.id, Document.kind).where(Document.kind.startswith('invoice:'))
        ):
            documents[kind.removeprefix('invoice:')].append(document_id)
        links = Counter(data['matched'] for _, data in movements if data.get('matched'))

        def match_key(data):
            return data.get('direction'), data.get('amount')

        def invoice(entry_id):
            entry = entries[entry_id]
            return dict(id=entry_id, date=entry.get('date', ''), concept=entry.get('concept', ''),
                        supplier=entry.get('counterparty', ''), reference=entry.get('reference', ''),
                        amount=entry['amount'], direction=entry.get('direction', ''),
                        files=documents[entry_id])

        pending = [invoice(entry_id) for entry_id in entries
                   if documents[entry_id] and not links[entry_id]]
        pending.sort(key=lambda row: (row['date'], row['id']), reverse=True)
        candidates_by_amount = defaultdict(list)
        for item in pending:
            candidates_by_amount[match_key(item)].append(item)

        unmatched = Counter(match_key(data) for _, data in movements if not data.get('matched'))
        result = []
        for row, data in movements:
            target = data.get('matched')
            key = match_key(data)
            candidates = candidates_by_amount[key] if not target else []
            if target:
                same = target in entries and match_key(entries[target]) == key and links[target] == 1
                state = ('Conciliado' if documents[target] else 'Sin factura') if same else 'Revisar enlace'
            elif candidates:
                state = 'Coincidencia única' if len(candidates) == unmatched[key] == 1 else 'Revisar coincidencias'
            else:
                state = 'Sin factura'
            result.append(dict(data, id=row.id, state=state,
                               invoice=invoice(target) if target in entries else None,
                               candidates=candidates))
        result.sort(key=lambda row: (row.get('date', ''), row['id']), reverse=True)
        return jsonify(movements=result, pendingInvoices=pending)

    @app.post('/api/bank/reconciliation/<movement_id>')
    @require('director')
    def reconcile(movement_id):
        target=body().get('invoice')
        if not isinstance(target,str):
            abort(400, 'Selecciona una factura')
        bank_lock()
        movement=g.db.get(Record,movement_id)
        if not movement or movement.kind!='module:bank':
            abort(404)
        data=unseal(movement.data)
        data['matched']=target
        if target:
            validate_bank_link(Record,unseal,data,movement_id)
            if not g.db.scalar(select(Document.id).where(Document.kind=='invoice:'+target).limit(1)):
                abort(400, 'Adjunta primero la factura al gasto')
        movement.data=seal(data)
        audit('bank_reconciled' if target else 'bank_unlinked',movement_id)
        return jsonify(ok=True)
