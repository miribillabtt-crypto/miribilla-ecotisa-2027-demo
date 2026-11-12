from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import laboral_kutxa
from test_security import env


def test_laboral_kutxa_read_only_link_and_sync(env, monkeypatch):
    _, _, login, _ = env
    director, headers = login('director')
    runner, _ = login('runner')
    base = '/api/bank/laboral-kutxa'
    assert runner.get(base).status_code == 403
    assert director.get(base).json['configured'] is False
    assert director.post(base+'/start', json={}, headers=headers).status_code == 503

    monkeypatch.setenv('PUBLIC_ORIGIN', 'https://portal.example')
    monkeypatch.setenv('ENABLE_BANKING_APP_ID', 'fixture')
    monkeypatch.setenv('ENABLE_BANKING_PRIVATE_KEY', 'fixture')
    expires = (datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    captured = {}

    def fake_provider(method, path, payload=None, query=None):
        if (method, path) == ('GET', '/aspsps'):
            assert query == {'country': 'ES'}
            return {'aspsps': [{'name': 'Laboral Kutxa'}]}
        if (method, path) == ('POST', '/auth'):
            assert payload['psu_type'] == 'business'
            assert payload['redirect_url'] == 'https://portal.example/banco/laboral-kutxa/retorno'
            captured.update(payload)
            return {'url': 'https://auth.enablebanking.com/ais/start'}
        if (method, path) == ('POST', '/sessions'):
            assert payload == {'code': 'fixture'}
            return {'session_id': 'session', 'access': {'valid_until': expires}, 'accounts': [
                {'uid': 'account', 'identification_hash': 'stable-identity', 'currency': 'EUR',
                 'account_id': {'iban': 'ES00000000000000001234'}}]}
        if (method, path) == ('GET', '/accounts/account/transactions'):
            transaction = {'entry_reference': 'ABC', 'transaction_amount': {'amount': '10.00', 'currency': 'EUR'},
                           'credit_debit_indicator': 'DBIT', 'booking_date': query.get('date_to', '2027-01-01'),
                           'status': 'BOOK', 'remittance_information': ['Compra de material']}
            if 'continuation_key' in query:
                return {'transactions': [{**transaction, 'entry_reference': None}]}
            return {'transactions': [transaction], 'continuation_key': 'next'}
        if (method, path) == ('GET', '/accounts/account/balances'):
            return {'balances': [{'balance_type': 'ITBD', 'balance_amount': {'amount': '-20.25', 'currency': 'EUR'}}]}
        if (method, path) == ('DELETE', '/sessions/session'):
            return {}
        raise AssertionError((method, path))

    monkeypatch.setattr(laboral_kutxa, 'banking_api', fake_provider)
    assert director.post(base+'/start', json={}, headers=headers).status_code == 200
    callback = director.get('/banco/laboral-kutxa/retorno', query_string={'state': captured['state'], 'code': 'fixture'})
    assert callback.status_code == 303
    assert parse_qs(urlsplit(callback.location).fragment)['code'] == ['fixture']
    assert director.post(base+'/finish', json={'state': 'wrong', 'code': 'fixture'}, headers=headers).status_code == 400
    proof = {'state': captured['state'], 'code': 'fixture'}
    assert director.post(base+'/finish', json=proof, headers=headers).status_code == 200
    assert director.post(base+'/finish', json=proof, headers=headers).status_code == 400
    assert director.get(base).json['accounts'] == [{'id': 'account', 'label': '•••• 1234'}]
    assert director.post(base+'/select', json={'account': 'account'}, headers=headers).status_code == 200
    assert director.post(base+'/sync', json={}, headers=headers).json == {'imported': 1, 'skipped': 1}
    row = director.get('/api/modules/bank').json['records'][0]
    edit = {key: row[key] for key in ('date', 'concept', 'reference', 'amount', 'direction', 'matched')}
    edit['concept'] = 'Editado'
    assert director.post('/api/modules/bank/'+row['id'], json=edit, headers=headers).status_code == 200
    assert director.post(base+'/sync', json={}, headers=headers).json['imported'] == 0
    assert director.get(base).json['balance'] == -2025
    assert director.post(base+'/disconnect', json={}, headers=headers).status_code == 200
    assert not director.get(base).json['connected']
    assert len(director.get('/api/modules/bank').json['records']) == 1


def test_treasury_uses_due_dates_and_excludes_settled_entries(env):
    _, _, login, _ = env
    director, headers = login('director')
    runner, _ = login('runner')
    path = '/api/bank/treasury'
    assert runner.get(path).status_code == 403
    before = director.get(path).json
    assert len(before['weeks']) == 13
    data = {'direction': 'Ingreso', 'status': 'Pendiente', 'amount': 5500,
            'dueDate': before['weeks'][1]['start']}
    assert director.post('/api/modules/entry', json=data, headers=headers).status_code == 200
    assert director.post('/api/modules/entry', json={**data, 'status': 'Cobrado'}, headers=headers).status_code == 200
    assert director.post('/api/modules/entry', json={**data, 'dueDate': '', 'direction': 'Gasto'}, headers=headers).status_code == 200
    forecast = director.get(path).json
    assert forecast['weeks'][1]['income'] == 5500
    assert forecast['undated'] == 1
