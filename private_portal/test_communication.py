import io
import json

from PIL import Image

from server import Record, User
from test_security import env


def test_communication_invitation_and_editable_calendar(env):
    app, _, login, _ = env
    director, headers = login('director')
    invitation = director.post('/api/communication/invite', headers=headers, json={
        'email': 'editor@example.invalid', 'name': 'Editora', 'role': 'director', 'documents': True,
    })
    assert invitation.status_code == 200
    token = invitation.json['token']
    editor = app.test_client()
    assert editor.post('/api/activate/start', json={'token': token}).json['role'] == 'communication'
    password = 'individual-editor-password'
    assert editor.post('/api/activate/finish', json={'token': token, 'password': password}).status_code == 200
    assert editor.post('/api/login', json={'email': 'editor@example.invalid', 'password': password}).status_code == 200
    session = editor.get('/api/me').json
    assert session['user']['role'] == 'communication' and not session['user']['documents']
    csrf = {'X-CSRF-Token': session['csrf']}
    for path in ('gestion', 'summary', 'users', 'roster', 'modules/bank'):
        assert editor.get('/api/'+path).status_code == 403
    assert editor.post('/api/team', json={'team': 'surne'}, headers=csrf).status_code == 403
    assert editor.post('/api/events', json={'name': 'Race'}, headers=csrf).status_code == 403
    assert editor.post('/api/communication/invite', json={}, headers=csrf).status_code == 403

    with app.extensions['db_sessions'].begin() as db:
        cipher = app.extensions['cipher']
        activity = {'name': 'Vuelta de prueba', 'date': '2027-05-07', 'endDate': '2027-05-09',
                    'called': ['private'], 'notes': 'private notes'}
        db.add(Record(id='surne-race', team='surne', kind='event', data=cipher.encrypt(json.dumps(activity).encode())))
    result = editor.get('/api/communication/calendar').json
    event = next(row for row in result['events'] if row['id'] == 'surne-race')
    assert event['team'] == 'surne' and 'called' not in event and 'notes' not in event

    path = '/api/communication/plans'
    plan = {'team': 'surne', 'date': '2027-05-07', 'time': '13:30', 'title': 'Previo',
            'status': 'Programada', 'channel': 'Instagram', 'event': 'surne-race', 'notes': 'Texto'}
    assert editor.post(path, json=dict(plan, team='occident'), headers=csrf).status_code == 400
    created = editor.post(path, json=plan, headers=csrf)
    assert created.status_code == 200, created.json
    target = path+'/'+created.json['id']
    assert editor.put(target, json=dict(plan, title='Previo editado'), headers=csrf).status_code == 200
    listed = editor.get('/api/communication/calendar').json['plans']
    assert listed[0]['team'] == 'surne' and listed[0]['title'] == 'Previo editado'
    assert editor.delete(target, headers=csrf).status_code == 200
    assert editor.get('/api/communication/calendar').json['plans'] == []


def test_communication_logos_and_photo_consent(env):
    app, _, login, _ = env
    editor, headers = login('communication')
    limited, _ = login('director_limited')
    runner, _ = login('runner')
    with app.extensions['db_sessions'].begin() as db:
        cipher = app.extensions['cipher']
        db.add(User(id='occident-photo', team='occident', name='Foto Occident', role='runner',
                    profile=cipher.encrypt(b'{"photoConsent":true}')))
    original = io.BytesIO()
    Image.new('RGB', (8, 8), 'white').save(original, format='PNG')
    raw = original.getvalue()
    logo_path = '/api/communication/logos/occident'
    upload = editor.post(logo_path, data={'name': 'Sponsor', 'file': (io.BytesIO(raw), 'logo.png')}, headers=headers)
    assert upload.status_code == 201, upload.json
    logo = '/api/communication/logo/'+upload.json['id']
    assert editor.get(logo).data == raw
    assert limited.get(logo).status_code == 404
    assert runner.get(logo).status_code == 403
    assert editor.delete(logo, headers=headers).status_code == 200
    assert editor.get(logo_path).json['logos'] == []

    picture = editor.post('/api/documents/occident-photo', data={
        'kind': 'portrait', 'file': (io.BytesIO(raw), 'portrait.png'),
    }, headers=headers)
    assert picture.status_code == 200, picture.json
    photos = editor.get('/api/communication/photos/occident').json['riders'][0]['photos']
    assert photos[0]['id'] == picture.json['id']
    photo = '/api/communication/photo/'+photos[0]['id']
    assert editor.get(photo).status_code == 200
    with app.extensions['db_sessions'].begin() as db:
        db.info['team'] = 'occident'
        db.get(User, 'occident-photo').profile = cipher.encrypt(b'{}')
    assert editor.get(photo).status_code == 404
