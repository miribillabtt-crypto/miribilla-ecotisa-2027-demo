"""Create rider username aliases from a sensitive, one-time deployment payload."""
import json
import hashlib
from sqlalchemy import select, text, update, delete
from werkzeug.security import generate_password_hash
from roster_import import normalize


MARKER = 'system-rider-accounts-v1'


def alias_key(username):
    return 'login-alias:'+hashlib.sha256(username.lower().encode()).hexdigest()


def provision_rider_accounts(Sessions, User, Record, Invite, LoginSession, cipher, payload):
    items = json.loads(payload)
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise ValueError('Invalid account payload')
    with Sessions.begin() as db:
        if db.get_bind().dialect.name == 'postgresql':
            db.execute(text('SELECT pg_advisory_xact_lock(20273003)'))
        previous = db.get(Record, MARKER)
        if previous:
            return json.loads(cipher.decrypt(previous.data))
        riders = list(db.scalars(select(User).where(User.role == 'runner')))
        seen = set()
        existing_accounts = 0
        for item in items:
            username = item['username'].lower()
            if username in seen or not username.replace('.', '').isalnum() or len(item['password']) < 6:
                raise ValueError('Invalid account credentials')
            seen.add(username)
            matches = [r for r in riders if normalize(r.name) == normalize(item['name'])]
            if len(matches) != 1 or not matches[0].active:
                raise ValueError('Rider match is missing or ambiguous')
            rider = matches[0]
            if rider.documents or rider.owner:
                raise ValueError('Unexpected rider permissions')
            collision = db.scalar(select(User).where(User.email == username, User.id != rider.id))
            alias = db.get(Record, alias_key(username))
            if collision or (alias and alias.owner_id != rider.id):
                raise ValueError('Username already exists')
            existing_accounts += int(bool(rider.password))
            rider.password = generate_password_hash(item['password'], method='scrypt:32768:8:1')
            db.execute(delete(LoginSession).where(LoginSession.user_id == rider.id))
            db.execute(update(Invite).where(Invite.reset_user == rider.id, Invite.used == False).values(used=True))
            if not alias:
                db.add(Record(id=alias_key(username), kind='system:login-alias', owner_id=rider.id,
                              data=cipher.encrypt(json.dumps({'username': username}).encode())))
        receipt = dict(created=len(items), existingAccounts=existing_accounts, verified=0)
        db.add(Record(id=MARKER, kind='system', owner_id='direction',
                      data=cipher.encrypt(json.dumps(receipt).encode())))
        return receipt


def verify_rider_accounts(app, Sessions, User, Record, cipher, payload, origin):
    with Sessions() as db:
        receipt = db.get(Record, MARKER)
        result = json.loads(cipher.decrypt(receipt.data))
        if result['verified'] == result['created']:
            return result
    verified = 0
    for index,item in enumerate(json.loads(payload),start=1):
        client = app.test_client()
        options = dict(base_url=origin, headers={'Origin': origin},
                       environ_overrides={'REMOTE_ADDR': '192.0.2.'+str(index)})
        response = client.post('/api/login', json={'email': item['username'], 'password': item['password']}, **options)
        if response.status_code != 200:
            raise RuntimeError('Rider login verification failed')
        me = client.get('/api/me', base_url=origin).json
        user = me['user']
        try:
            if user['role'] != 'runner' or user['owner'] or user['documents']:
                raise RuntimeError('Unexpected account permissions')
            if client.get('/api/profile/'+user['id'], base_url=origin).status_code != 200:
                raise RuntimeError('Rider profile verification failed')
            if client.get('/api/users', base_url=origin).status_code != 403:
                raise RuntimeError('Rider isolation verification failed')
            verified += 1
        finally:
            options['headers']['X-CSRF-Token'] = me['csrf']
            client.post('/api/logout', json={}, **options)
    result['verified'] = verified
    with Sessions.begin() as db:
        receipt = db.get(Record, MARKER)
        receipt.data = cipher.encrypt(json.dumps(result).encode())
    return result
