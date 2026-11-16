"""Company-wide accounting overview and internal allocation of invoices."""
import csv
import hashlib
import io
import re
import secrets
import time
from datetime import date

from flask import abort, g, jsonify, request, send_file
from sqlalchemy import select, text
from werkzeug.utils import secure_filename

from team_scope import TEAMS

CENTRAL = 'gestion'
INBOX = 'gestion:invoice'
SPLIT = 'gestion:allocation'
MAIL_ACCOUNTS = ('miribillabtt@gmail.com', 'alex.alvarez@miribillacycling.com')
BUCKETS = {**TEAMS, 'common': 'Gasto común'}


def can_manage_gestion(user):
    return bool(user and user.role=='director' and (
        user.id=='shared-direction' or user.email=='alex.alvarez@miribillacycling.com'))


def register_gestion(app, Record, Document, User, cipher, seal, unseal, audit, require, body):
    def central_only():
        if not can_manage_gestion(g.user):
            abort(403, 'Acceso reservado a la dirección general')

    def all_teams(stmt):
        return stmt.execution_options(shared_resource_lookup=True)

    def lock():
        if g.db.get_bind().dialect.name == 'postgresql':
            g.db.execute(text('SELECT pg_advisory_xact_lock(20273040)'))

    def documents(entries):
        kinds = ['invoice:' + entry for entry in entries]
        docs = g.db.execute(all_teams(
            select(Document.id, Document.kind).where(Document.kind.in_(kinds))
        ))
        out = {}
        for file_id, kind in docs:
            out.setdefault(kind[8:], []).append(file_id)
        return out

    def rows():
        entries = list(g.db.execute(all_teams(select(Record.id, Record.team, Record.kind, Record.data)
                       .where(Record.kind.in_(('module:entry', INBOX, SPLIT))))))
        splits = {row.id: unseal(row.data) for row in entries if row.kind == SPLIT}
        files = documents([row.id for row in entries if row.kind != SPLIT])
        for row in entries:
            if row.kind == SPLIT:
                continue
            data = unseal(row.data)
            amount = data.get('amount', 0)
            split_id = 'gestion-allocation:' + row.id
            signed_direction = data.get('direction', 'Gasto')
            split = splits.get(split_id, {row.team: amount} if row.team in TEAMS else {})
            if sum(split.values()) != amount:
                split = {}
            yield dict(id=row.id, team=row.team, date=data.get('date',''), direction=signed_direction,
                       supplier=data.get('counterparty',''), reference=data.get('reference',''),
                       concept=data.get('concept',''), amount=amount, base=data.get('baseAmount',0),
                       tax=data.get('taxAmount',0), status=data.get('status',''),
                       allocations=split, files=files.get(row.id, []), taxId=data.get('taxId',''),
                       needsReview=row.kind==INBOX and data.get('status')!='Revisada',
                       needsOCR=bool(data.get('needsOCR')))

    @app.get('/api/gestion')
    @require('director')
    def gestion_overview():
        central_only()
        return jsonify(rows=list(rows()), buckets=BUCKETS, mailAccounts=MAIL_ACCOUNTS)

    @app.get('/api/gestion/export')
    @require('director')
    def gestion_export():
        central_only()
        output=io.StringIO()
        writer=csv.writer(output, delimiter=';')
        writer.writerow(['Fecha','Movimiento','Equipo de origen','Proveedor','Número','Concepto',
                         'Base','IVA','Total',*BUCKETS.values(),'Sin asignar'])
        def safe(value):
            value=str(value)
            return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
        def money(cents):
            return f'{cents//100},{cents%100:02d}'
        month=request.args.get('month','')
        if month and not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])',month):
            abort(400,'Mes no válido')
        for row in sorted(rows(),key=lambda row:(row['date'],row['id'])):
            if row['needsReview']:
                continue
            if month and not row['date'].startswith(month):
                continue
            writer.writerow([*(safe(value) for value in (
                row['date'],row['direction'],TEAMS.get(row['team'],'Buzón de facturas'),
                row['supplier'],row['reference'],row['concept'])),
                *(money(row[key]) for key in ('base','tax','amount')),
                *(money(row['allocations'].get(bucket,0)) for bucket in BUCKETS),
                money(row['amount']-sum(row['allocations'].values()))])
        audit('gestion_exported',month)
        return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')),mimetype='text/csv',
                         as_attachment=True,download_name='gestion-miribilla'+('-'+month if month else '')+'.csv')

    @app.get('/api/gestion/team')
    @require('director')
    def gestion_team_overview():
        allocated = []
        for row in rows():
            if row['needsReview']:
                continue
            amount = row['allocations'].get(g.team,0)
            if (row['team']==g.team and amount!=row['amount']) or (row['team']!=g.team and amount):
                allocated.append({k: row[k] for k in ('id','date','supplier','reference','concept','direction','team')}
                                 | dict(amount=amount, originalAmount=row['amount']))
        return jsonify(rows=allocated)

    @app.post('/api/gestion/<entry_id>/allocation')
    @require('director')
    def gestion_allocate(entry_id):
        central_only()
        amounts = body().get('amounts')
        if not isinstance(amounts,dict) or set(amounts)-set(BUCKETS) or any(
            type(amount)!=int or amount<0 for amount in amounts.values()
        ):
            abort(400,'Revisa el reparto')
        lock()
        entry = g.db.execute(all_teams(select(Record.id,Record.data).where(
            Record.id==entry_id, Record.kind.in_(('module:entry',INBOX))).with_for_update())).first()
        if not entry:
            abort(404,'Apunte no encontrado')
        if sum(amounts.values()) != unseal(entry.data).get('amount',0):
            abort(400,'El reparto debe sumar el importe íntegro de la factura')
        split_id = 'gestion-allocation:' + entry.id
        split = g.db.execute(all_teams(select(Record).where(Record.id==split_id))).scalar_one_or_none()
        encoded = seal({key:amount for key,amount in amounts.items() if amount})
        if split:
            split.data = encoded
        else:
            g.db.add(Record(id=split_id,kind=SPLIT,team=CENTRAL,owner_id=entry.id,data=encoded))
        audit('gestion_allocation_updated',entry.id)
        return jsonify(ok=True)

    def invoice_field(name, maximum):
        value = request.form.get(name,'').strip()
        if len(value)>maximum:
            abort(400,'Revisa el campo '+name)
        return value

    def cents(name):
        value = request.form.get(name,'0') or '0'
        if not re.fullmatch(r'[0-9]{1,9}',value):
            abort(400,'Indica importes válidos en céntimos')
        return int(value)

    def invoice_matches(data, supplier, reference, tax_id):
        def normalize(value):
            return ''.join(character for character in value.casefold() if character.isalnum())
        if not reference or not data.get('reference'):
            return False
        same_supplier = (normalize(data['taxId'])==normalize(tax_id) if data.get('taxId') and tax_id
                         else normalize(data.get('counterparty',''))==normalize(supplier))
        return same_supplier and normalize(data['reference'])==normalize(reference)

    def store_invoice(owner, mail_account=None):
        file = request.files.get('file')
        raw = file.read(4*1024*1024+1) if file else b''
        if not raw.startswith(b'%PDF-') or b'%%EOF' not in raw[-65536:] or len(raw)>4*1024*1024:
            abort(400,'Adjunta el PDF original, de hasta 4 MB')
        supplier = invoice_field('supplier',180)
        reference = invoice_field('reference',120)
        tax_id = invoice_field('taxId',40)
        issue_date = invoice_field('date',10)
        amount, base, tax = (cents(name) for name in ('amount','base','tax'))
        if mail_account:
            supplier=reference=tax_id=issue_date=''
            amount=base=tax=0
        else:
            check_invoice_fields(issue_date,supplier,reference,amount,base,tax)
        sha = hashlib.sha256(raw).hexdigest()
        lock()
        for row in g.db.execute(all_teams(select(Record.id,Record.kind,Record.data).where(
            Record.kind.in_(('invoice-metadata',INBOX,'module:entry'))))):
            data=unseal(row.data)
            if data.get('sha256')==sha or invoice_matches(data,supplier,reference,tax_id):
                return jsonify(duplicate=True)
        entry = Record(kind=INBOX,team=CENTRAL,owner_id=owner,data=seal(dict(
            date=issue_date, counterparty=supplier, reference=reference, taxId=tax_id,
            direction='Gasto', amount=amount, baseAmount=base,taxAmount=tax,
            concept=invoice_field('concept',250), status='Pendiente de revisar',
            needsOCR=bool(mail_account), mailAccount=mail_account or '')))
        g.db.add(entry)
        g.db.flush()
        doc = Document(kind='invoice:'+entry.id,team=CENTRAL,owner_id=owner,
                       size=len(raw),mime='application/pdf',created=int(time.time()),content=cipher.encrypt(raw))
        g.db.add(doc)
        g.db.flush()
        name=secure_filename(file.filename or '')[:140] or 'factura.pdf'
        if not name.lower().endswith('.pdf'):
            name += '.pdf'
        g.db.add(Record(id='invoice-meta-'+doc.id,kind='invoice-metadata',team=CENTRAL,
                        owner_id=entry.id,data=seal(dict(filename=name,sha256=sha))))
        audit('gestion_invoice_received',entry.id)
        return jsonify(id=entry.id),201

    @app.post('/api/gestion/invoices')
    @require('director')
    def gestion_upload():
        central_only()
        return store_invoice(g.user.id)

    def check_invoice_fields(issue_date,supplier,reference,amount,base,tax):
        try:
            if date.fromisoformat(issue_date).isoformat()!=issue_date:
                raise ValueError()
        except ValueError:
            abort(400,'Indica la fecha de la factura')
        if not supplier or not reference or amount<=0 or ((base or tax) and base+tax!=amount):
            abort(400,'Revisa proveedor, número, base, IVA y total')

    @app.post('/api/gestion/mail-key')
    @require('director')
    def gestion_mail_key():
        central_only()
        account=body().get('account')
        if account not in MAIL_ACCOUNTS:
            abort(400)
        lock()
        key=secrets.token_urlsafe(40)
        record_id='gestion-mail-key:'+account
        row=g.db.execute(all_teams(select(Record).where(Record.id==record_id))).scalar_one_or_none()
        data=seal({'hash':hashlib.sha256(key.encode()).hexdigest()})
        if row:
            row.data=data
        else:
            g.db.add(Record(id=record_id,kind='gestion:mail-key',team=CENTRAL,owner_id=g.user.id,data=data))
        audit('gestion_mail_key_rotated',account)
        return jsonify(key=key)

    @app.post('/api/gestion/mail-intake')
    def gestion_mail_intake():
        supplied=request.headers.get('Authorization','')
        account=request.headers.get('X-Gestion-Mailbox','')
        if not supplied.startswith('Bearer ') or len(supplied)>150 or account not in MAIL_ACCOUNTS:
            abort(401)
        row=g.db.execute(all_teams(select(Record.data).where(
            Record.id=='gestion-mail-key:'+account,Record.kind=='gestion:mail-key'))).scalar_one_or_none()
        digest=hashlib.sha256(supplied[7:].encode()).hexdigest()
        if not row or not secrets.compare_digest(unseal(row)['hash'],digest):
            abort(401)
        owner=g.db.execute(all_teams(select(User.id).where(User.id=='shared-direction',User.active.is_(True)))).scalar_one_or_none()
        if not owner:
            abort(503)
        return store_invoice(owner,account)

    @app.post('/api/gestion/<entry_id>/review')
    @require('director')
    def gestion_review(entry_id):
        central_only()
        incoming=body()
        approved=incoming.get('approved') is True
        lock()
        row=g.db.execute(all_teams(select(Record).where(
            Record.id==entry_id,Record.kind==INBOX).with_for_update())).scalar_one_or_none()
        if not row:
            abort(404)
        current=unseal(row.data)
        if current.get('status')=='Revisada' or (not approved and not current.get('needsOCR')):
            abort(409,'La factura ya se ha revisado o preparado')
        fields={}
        for key,limit in (('date',10),('counterparty',180),('reference',120),('concept',250),('taxId',40)):
            value=incoming.get(key,'')
            if not isinstance(value,str) or len(value)>limit:
                abort(400,'Revisa los datos de la factura')
            fields[key]=value.strip()
        for key in ('amount','baseAmount','taxAmount'):
            value=incoming.get(key,0)
            if type(value)!=int or not 0<=value<=999999999:
                abort(400,'Revisa los importes de la factura')
            fields[key]=value
        if approved:
            check_invoice_fields(fields['date'],fields['counterparty'],fields['reference'],
                                 fields['amount'],fields['baseAmount'],fields['taxAmount'])
            existing=g.db.execute(all_teams(select(Record.kind,Record.data).where(
                Record.id!=entry_id,Record.kind.in_(('module:entry',INBOX)))))
            for kind,encrypted in existing:
                item=unseal(encrypted)
                if kind==INBOX and item.get('status')!='Revisada':
                    continue
                if invoice_matches(item,fields['counterparty'],fields['reference'],fields['taxId']):
                    abort(409,'Ya hay un asiento con ese proveedor y número de factura')
        current.update(fields,needsOCR=False,status='Revisada' if approved else 'Pendiente de revisar')
        row.data=seal(current)
        audit('gestion_invoice_reviewed' if approved else 'gestion_invoice_ocr_prepared',entry_id)
        return jsonify(ok=True)

    @app.get('/api/gestion/file/<file_id>')
    @require('director')
    def gestion_download(file_id):
        central_only()
        doc=g.db.execute(all_teams(select(Document.id,Document.kind,Document.content,Document.mime)
                         .where(Document.id==file_id))).first()
        if not doc or not doc.kind.startswith('invoice:'):
            abort(404)
        meta=g.db.execute(all_teams(select(Record.data).where(Record.id=='invoice-meta-'+file_id,
                            Record.kind=='invoice-metadata'))).scalar_one_or_none()
        audit('gestion_invoice_downloaded',file_id)
        return send_file(io.BytesIO(cipher.decrypt(doc.content)),mimetype=doc.mime,
                         as_attachment=True,download_name=(unseal(meta).get('filename') if meta else 'factura.pdf'))
