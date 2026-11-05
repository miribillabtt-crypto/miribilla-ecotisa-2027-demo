"""Provision the shared direction account once, using a deployment password hash."""
import json
from sqlalchemy import select, text


def seed_direction_account(Sessions, User, Record, cipher, password_hash):
    if not password_hash or not password_hash.startswith('scrypt:'):
        raise ValueError('A supported password hash is required')
    marker = 'system-shared-direction-created'
    with Sessions.begin() as db:
        if db.get_bind().dialect.name == 'postgresql':
            db.execute(text('SELECT pg_advisory_xact_lock(20273002)'))
        if db.get(Record, marker):
            return
        existing = db.scalar(select(User).where(User.email == 'direccion'))
        if existing:
            raise ValueError('The shared username already exists')
        db.add(User(id='shared-direction', email='direccion', name='Dirección',
                    role='director', password=password_hash, mfa=None, active=True,
                    documents=True, owner=False, profile=cipher.encrypt(b'{}')))
        db.add(Record(id=marker, kind='system', owner_id='shared-direction',
                      data=cipher.encrypt(json.dumps({'created': True}).encode())))
