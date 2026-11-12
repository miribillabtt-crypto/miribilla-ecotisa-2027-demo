"""Read-only Open Banking and short-term treasury for the portal."""
import base64
import hashlib
import json
import os
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from flask import abort, g, jsonify, redirect, request
from sqlalchemy import select

from bank_reconciliation import bank_fingerprint, bank_lock, bank_rows, normalized
from team_scope import NETKOM, team_record_key


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def banking_api(method, path, payload=None, query=None):
    def encode(value):
        return base64.urlsafe_b64encode(value).rstrip(b'=')

    try:
        key = serialization.load_pem_private_key(
            os.environ['ENABLE_BANKING_PRIVATE_KEY'].replace(r'\n', '\n').encode(), password=None)
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
            raise ValueError('invalid RSA key')
        now = int(time.time())
        header = {'alg': 'RS256', 'typ': 'JWT', 'kid': os.environ['ENABLE_BANKING_APP_ID']}
        claims = {'iss': 'enablebanking.com', 'aud': 'api.enablebanking.com', 'iat': now, 'exp': now+300}
        unsigned = b'.'.join(encode(json.dumps(item).encode()) for item in (header, claims))
        token = unsigned+b'.'+encode(key.sign(unsigned, padding.PKCS1v15(), hashes.SHA256()))
    except (KeyError, TypeError, ValueError):
        abort(503, 'Revisa las credenciales de Enable Banking en el servidor.')
    url = 'https://api.enablebanking.com'+path
    if query:
        url += '?'+urlencode(query)
    headers = {'Authorization': 'Bearer '+token.decode(), 'Accept': 'application/json'}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers['Content-Type'] = 'application/json'
    try:
        with build_opener(NoRedirect()).open(Request(url, data=data, headers=headers, method=method), timeout=8) as response:
            raw = response.read(8_000_001)
            if len(raw) > 8_000_000:
                raise ValueError('response too large')
            return json.loads(raw) if raw else {}
    except HTTPError as error:
        if method == 'DELETE' and error.code == 404:
            return {}
        if error.code in (401, 403, 404, 422):
            abort(502, 'El proveedor no ha autorizado esta operación. Revisa la conexión y el consentimiento.')
        if error.code == 429:
            abort(429, 'Se ha alcanzado el límite de consultas. Inténtalo más tarde.')
        abort(502, 'Laboral Kutxa no ha podido completar la consulta.')
    except (URLError, OSError, ValueError):
        abort(502, 'No se pudo consultar Laboral Kutxa. Inténtalo más tarde.')


def iso_time(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed if parsed.tzinfo else None
    except (AttributeError, TypeError, ValueError):
        return None


def euros_in_cents(amount):
    if amount.get('currency') != 'EUR' or amount.get('amount') in (None, ''):
        raise ValueError('missing euro amount')
    value = Decimal(str(amount['amount']))
    if not value.is_finite() or abs(value)>1_000_000 or value*100 != (value*100).to_integral_value():
        raise ValueError('invalid euro amount')
    return int(value*100)


def bank_transaction(item):
    if item.get('status') != 'BOOK' or item.get('credit_debit_indicator') not in ('CRDT', 'DBIT'):
        return None
    reference = item.get('entry_reference')
    if not reference:
        return None
    try:
        amount = abs(euros_in_cents(item.get('transaction_amount') or {}))
        day = date.fromisoformat(item.get('booking_date') or item.get('value_date') or '').isoformat()
    except (ValueError, ArithmeticError):
        return None
    if not amount:
        return None
    incoming = item['credit_debit_indicator'] == 'CRDT'
    party = (item.get('debtor' if incoming else 'creditor') or {}).get('name') or ''
    concept = ' · '.join(dict.fromkeys(filter(None, [party, *(item.get('remittance_information') or [])])))
    return dict(date=day, concept=concept[:2500], reference=str(item.get('reference_number') or reference)[:2500],
                amount=amount, direction='Ingreso' if incoming else 'Gasto', matched='',
                bankReference=str(reference))


def treasury_weeks(entries, moves, today):
    settled = {(row.get('matched'), row.get('direction'), row.get('amount')) for row in moves}
    weeks = [dict(start=(today+timedelta(weeks=i)).isoformat(),
                  end=(today+timedelta(days=7*i+6)).isoformat(), income=0, expenses=0)
             for i in range(13)]
    undated = overdue = 0
    for entry_id, data in entries:
        amount, direction = data.get('amount', 0), data.get('direction')
        if (not amount or direction not in ('Ingreso', 'Gasto')
                or data.get('status') in ('Pagado', 'Cobrado', 'Anulado')
                or (entry_id, direction, amount) in settled):
            continue
        try:
            due = date.fromisoformat(data.get('dueDate') or '')
        except ValueError:
            undated += 1
            continue
        days = (due-today).days
        if days < 0:
            overdue += 1
        week = max(0, days)//7
        if week < len(weeks):
            weeks[week]['income' if direction == 'Ingreso' else 'expenses'] += amount
    return dict(weeks=weeks, undated=undated, overdue=overdue, today=today.isoformat())


def register_laboral_kutxa(app, Record, seal, unseal, audit, require, body):
    def active_team():
        return os.environ.get('LABORAL_KUTXA_TEAM', NETKOM)

    def configured():
        origin = urlsplit(os.environ.get('PUBLIC_ORIGIN', ''))
        return bool(origin.scheme == 'https' and origin.hostname and not origin.path
                    and os.environ.get('ENABLE_BANKING_APP_ID') and os.environ.get('ENABLE_BANKING_PRIVATE_KEY'))

    def get_record(kind, refresh=False):
        return g.db.get(Record, team_record_key(g.team, 'laboral-kutxa-'+kind), populate_existing=refresh)

    def save_record(kind, data):
        row = get_record(kind)
        if not row:
            row = Record(id=team_record_key(g.team, 'laboral-kutxa-'+kind),
                         kind='system:bank-connection', owner_id=g.user.id)
            g.db.add(row)
        row.data = seal(data)

    def read_record(kind):
        row = get_record(kind)
        return unseal(row.data) if row else {}

    def allowed():
        if not g.user.owner or g.team != active_team():
            abort(403, 'La conexión se gestiona desde la cuenta propietaria de Dirección.')
        if not configured():
            abort(503, 'Pendiente de configurar Enable Banking.')

    def still_valid(connection):
        expires = iso_time(connection.get('expires'))
        return bool(expires and expires > datetime.now(timezone.utc))

    @app.get('/api/bank/laboral-kutxa')
    @require('director')
    def status():
        can_manage = bool(g.user.owner and g.team == active_team())
        connection = read_record('connection') if g.team == active_team() else {}
        accounts = connection.get('accounts', [])
        selected = next((item for item in accounts if item['uid'] == connection.get('selected')), {})
        return jsonify(manage=can_manage, configured=configured() if can_manage else False,
                       team=g.team == active_team(), expires=connection.get('expires', ''),
                       connected=bool(selected and still_valid(connection)),
                       accounts=[dict(id=item['uid'], label=item['label']) for item in accounts]
                           if can_manage and not selected and still_valid(connection) else [],
                       label=selected.get('label', ''), balance=connection.get('balance'), balanceLabel=connection.get('balanceLabel', ''),
                       synced=connection.get('synced', ''), hasConsent=bool(connection))

    @app.post('/api/bank/laboral-kutxa/start')
    @require('director')
    def start():
        allowed()
        bank_lock()
        if still_valid(read_record('connection')):
            abort(409, 'Desconecta primero el consentimiento actual.')
        banks = banking_api('GET', '/aspsps', query={'country': 'ES'}).get('aspsps', [])
        bank = next((item for item in banks if 'laboral kutxa' in normalized(item.get('name'))), None)
        if not bank:
            abort(503, 'Laboral Kutxa no está disponible para esta aplicación de Enable Banking.')
        validity = min(int(bank.get('maximum_consent_validity') or 90*86400), 90*86400)
        state = secrets.token_urlsafe(32)
        callback = os.environ['PUBLIC_ORIGIN']+'/banco/laboral-kutxa/retorno'
        expires = (datetime.now(timezone.utc)+timedelta(seconds=validity)).isoformat()
        answer = banking_api('POST', '/auth', dict(
            access={'valid_until': expires}, aspsp={'name': bank['name'], 'country': 'ES'},
            state=state, redirect_url=callback, psu_type='business', language='es',
        ))
        url = answer.get('url', '')
        parts = urlsplit(url)
        if parts.scheme != 'https' or parts.netloc != 'auth.enablebanking.com':
            abort(502, 'El proveedor no devolvió un enlace de autorización válido.')
        save_record('pending', dict(state=state, login=g.login.id, until=int(time.time())+900, expires=expires))
        return jsonify(url=url)

    @app.get('/banco/laboral-kutxa/retorno')
    def callback():
        # A fresh same-origin page can use the existing Strict login cookie.
        values = {key: request.args.get(key, '')[:2048] for key in ('code', 'state')}
        return redirect('/#'+urlencode({'lk': '1', **values}), 303)

    @app.post('/api/bank/laboral-kutxa/finish')
    @require('director')
    def finish():
        allowed()
        payload = body()
        state, code = payload.get('state'), payload.get('code')
        if not isinstance(state, str) or not isinstance(code, str) or len(state)>128 or not 0<len(code)<=2048:
            abort(400, 'La autorización bancaria no se completó.')
        bank_lock()
        pending = read_record('pending')
        if (pending.get('login') != g.login.id or pending.get('until', 0) < time.time()
                or not secrets.compare_digest(pending.get('state', '').encode(), state.encode())):
            abort(400, 'La autorización ha caducado. Vuelve a conectar desde Contabilidad.')
        result = banking_api('POST', '/sessions', {'code': code})
        session_id = result.get('session_id')
        accounts = []
        for item in result.get('accounts', []):
            uid, identity = item.get('uid'), item.get('identification_hash')
            iban = (item.get('account_id') or {}).get('iban', '')
            if uid and identity and item.get('currency') in (None, '', 'EUR'):
                accounts.append(dict(uid=uid, identity=identity, label='•••• '+iban[-4:] if iban else
                                     (item.get('name') or f'Cuenta {len(accounts)+1}')))
        if not session_id or not accounts:
            if session_id:
                banking_api('DELETE', '/sessions/'+quote(session_id, safe=''))
            abort(422, 'Laboral Kutxa no devolvió una cuenta en euros seleccionable.')
        expires = (result.get('access') or {}).get('valid_until') or pending['expires']
        save_record('connection', dict(session=session_id, accounts=accounts, expires=expires))
        g.db.delete(get_record('pending'))
        audit('laboral_kutxa_authorized')
        return jsonify(ok=True)

    @app.post('/api/bank/laboral-kutxa/select')
    @require('director')
    def select_account():
        allowed()
        bank_lock()
        connection = read_record('connection')
        account_id = body().get('account')
        if (not still_valid(connection) or connection.get('selected')
                or not any(item['uid'] == account_id for item in connection.get('accounts', []))):
            abort(400, 'Selecciona una cuenta del consentimiento vigente.')
        connection['selected'] = account_id
        connection['accounts'] = [item for item in connection['accounts'] if item['uid'] == account_id]
        save_record('connection', connection)
        audit('laboral_kutxa_account_selected')
        return jsonify(ok=True)

    @app.post('/api/bank/laboral-kutxa/sync')
    @require('director')
    def sync():
        allowed()
        connection = read_record('connection')
        if not connection.get('selected') or not still_valid(connection):
            abort(409, 'Autoriza y selecciona primero la cuenta de Laboral Kutxa.')
        account = connection['accounts'][0]
        prefix = '/accounts/'+quote(account['uid'], safe='')
        today = datetime.now(ZoneInfo('Europe/Madrid')).date()
        params = dict(date_from=(today-timedelta(days=30)).isoformat(), date_to=today.isoformat(),
                      transaction_status='BOOK')
        imported, skipped = [], 0
        for _ in range(10):
            page = banking_api('GET', prefix+'/transactions', query=params)
            for item in page.get('transactions', []):
                row = bank_transaction(item)
                if row:
                    imported.append(row)
                else:
                    skipped += 1
            key = page.get('continuation_key')
            if not key:
                break
            params = {'continuation_key': key}
        else:
            abort(502, 'El extracto supera el límite de páginas. No se han guardado movimientos.')
        balances = banking_api('GET', prefix+'/balances').get('balances', [])
        balance = None
        balance_label = ''
        for balance_type in ('ITBD', 'CLBD', 'ITAV', 'CLAV'):
            candidate = next((b for b in balances if b.get('balance_type') == balance_type
                              and (b.get('balance_amount') or {}).get('currency') == 'EUR'), None)
            if candidate:
                try:
                    balance = euros_in_cents(candidate['balance_amount'])
                    balance_label = 'contable' if balance_type in ('ITBD', 'CLBD') else 'disponible'
                    break
                except (ValueError, ArithmeticError):
                    continue

        bank_lock()
        current_record = get_record('connection', refresh=True)
        current = unseal(current_record.data) if current_record else {}
        if (current.get('session'), current.get('selected')) != (connection['session'], account['uid']):
            abort(409, 'La cuenta cambió durante la consulta. Vuelve a sincronizar.')
        existing = {}
        seen = set()
        for record in g.db.scalars(select(Record).where(Record.kind.in_(('module:bank', 'archived:bank')))):
            data = unseal(record.data)
            if data.get('bankImportId'):
                seen.add(data['bankImportId'])
            else:
                existing.setdefault(bank_fingerprint(data), []).append((record, data))
        count = 0
        for row in imported:
            reference = row.pop('bankReference')
            import_id = hashlib.sha256(json.dumps([account['identity'], reference]).encode()).hexdigest()
            if import_id in seen:
                continue
            seen.add(import_id)
            duplicates = existing.get(bank_fingerprint(row))
            if duplicates:
                record, previous = duplicates.pop()
                record.data = seal(dict(previous, bankImportId=import_id))
            else:
                g.db.add(Record(kind='module:bank', owner_id=g.user.id,
                                data=seal(dict(row, bankImportId=import_id))))
                count += 1
        current.update(balance=balance, balanceLabel=balance_label, synced=today.isoformat())
        save_record('connection', current)
        audit('laboral_kutxa_synced', str(count))
        return jsonify(imported=count, skipped=skipped)

    @app.post('/api/bank/laboral-kutxa/disconnect')
    @require('director')
    def disconnect():
        allowed()
        bank_lock()
        connection = get_record('connection')
        if connection:
            session_id = unseal(connection.data)['session']
            banking_api('DELETE', '/sessions/'+quote(session_id, safe=''))
            g.db.delete(connection)
        pending = get_record('pending')
        if pending:
            g.db.delete(pending)
        audit('laboral_kutxa_disconnected')
        return jsonify(ok=True)

    @app.get('/api/bank/treasury')
    @require('director')
    def treasury():
        entries = [(row.id, data) for row, data in bank_rows(Record, unseal, 'entry')]
        moves = [data for _, data in bank_rows(Record, unseal, 'bank')]
        today = datetime.now(ZoneInfo('Europe/Madrid')).date()
        return jsonify(treasury_weeks(entries, moves, today))
