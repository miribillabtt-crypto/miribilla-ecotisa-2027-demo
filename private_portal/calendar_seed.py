"""Restore the planned races and apply the supplied NETKOM calendar once."""
import json,hashlib
import os
import re
import unicodedata
from datetime import date
from sqlalchemy import select,text
RACES=[('Circuito del Guadiana','Febrero','Copa de España',''),('Albi','Marzo','UCI',''),('La Canonja','Abril','UCI','Alfonso'),('El Baruco','Abril','Carrera','Alfonso'),('Chele Campos','Abril','Carrera','Alfonso'),('Vuelta Montaña Central','Sin fecha','Vuelta',''),('Vuelta a Besaya','Sin fecha','Vuelta',''),('Vuelta Gipuzkoa','Sin fecha','Vuelta',''),('Vuelta Bizkaia','Sin fecha','Vuelta',''),('Vuelta a Pamplona','Sin fecha','Vuelta','Alfonso'),('Vuelta Ribera del Duero','Sin fecha','UCI',''),('Vuelta a Cantabria','Sin fecha','Vuelta','Alfonso')]
def restore_calendar(Sessions,Record,cipher):
 with Sessions.begin() as db:
  if db.get_bind().dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(20272027)'))
  marker='system-calendar-2027-restored'
  recovery='system-calendar-guadiana-checked'
  if db.get(Record,recovery):return
  seeded=db.get(Record,marker)
  names={json.loads(cipher.decrypt(r.data)).get('name','').casefold() for r in db.scalars(select(Record).where(Record.kind=='event'))}
  for name,month,typ,owner in (RACES[:1] if seeded else RACES):
   rid='race2027-'+hashlib.sha256(name.encode()).hexdigest()[:24]
   if db.get(Record,rid) or name.casefold() in names:continue
   if name==RACES[0][0] and any('guadiana' in existing for existing in names):continue
   data=dict(name=name,month=month,category='Carrera',type=typ,owner=owner,date='',endDate='',place='',status='Prevista · por confirmar',notes='Calendario previsto facilitado por Dirección; fecha y participación por confirmar.',called=[],callStatus='Borrador')
   db.add(Record(id=rid,kind='event',owner_id='direction',data=cipher.encrypt(json.dumps(data,ensure_ascii=False).encode())))
  if not seeded:db.add(Record(id=marker,kind='system',owner_id='direction',data=cipher.encrypt(b'{"version":1}')))
  db.add(Record(id=recovery,kind='system',owner_id='direction',data=cipher.encrypt(b'{"version":1}')))


def race_key(name):
    name = re.sub(r'\s*\((?:UCI|COPA(?: DE)? ESPAÑA)\)\s*$', '', name, flags=re.I)
    name = unicodedata.normalize('NFKD', name.casefold())
    return ' '.join(re.findall(r'[a-z0-9]+', name.encode('ascii', 'ignore').decode()))


RACE_ALIASES = {
    'el baruco': 'baruco',
    'chele campos': 'chele del campo',
    'vuelta montana central': 'montana central de asturias',
    'vuelta a besaya': 'vuelta besaya',
    'vuelta gipuzkoa': 'gipuzkoa klasikoa',
    'vuelta bizkaia': 'bizkaia itzulia',
}
LEGACY_NOTES = 'Calendario previsto facilitado por Dirección; fecha y participación por confirmar.'


def import_netkom_calendar(Sessions, Record, cipher, payload):
    marker = 'system-netkom-calendar-2027'
    with Sessions.begin() as db:
        if db.get_bind().dialect.name == 'postgresql':
            db.execute(text('SELECT pg_advisory_xact_lock(20272027)'))
        imported = db.get(Record, marker)
        if imported:
            return json.loads(cipher.decrypt(imported.data))

        rows = json.loads(payload)
        keys = set()
        for start, end, name, confirmed, requested in rows:
            if date.fromisoformat(start).year != 2027 or (end and (
                date.fromisoformat(end).year != 2027 or end < start
            )):
                raise ValueError('Fecha fuera del calendario NETKOM 2027')
            key = (race_key(name), start)
            if not key[0] or key in keys or any(
                status not in {'SI', 'NO', 'NO HACE FALTA'} for status in (confirmed, requested)
            ):
                raise ValueError('Fila inválida en el calendario NETKOM 2027')
            keys.add(key)

        existing = {}
        for record in db.scalars(select(Record).where(Record.kind == 'event').order_by(Record.id)):
            data = json.loads(cipher.decrypt(record.data))
            event_date = data.get('date') or ''
            if data.get('category', 'Carrera') != 'Carrera' or (event_date and not event_date.startswith('2027-')):
                continue
            key = race_key(data.get('name', ''))
            existing.setdefault(RACE_ALIASES.get(key, key), []).append((record, data))

        created = updated = 0
        for start, end, name, confirmed, requested in rows:
            key = race_key(name)
            candidates = existing.get(key, [])
            match = next((pair for pair in candidates if pair[1].get('date') == start), None)
            if match is None and len(candidates) == 1:
                match = candidates[0]
            if match is None:
                record = Record(
                    id='netkom2027-' + hashlib.sha256(f'{key}|{start}'.encode()).hexdigest()[:24],
                    kind='event', owner_id='direction',
                )
                data = {'category': 'Carrera', 'place': '', 'called': [], 'callStatus': 'Borrador'}
                db.add(record)
                created += 1
            else:
                record, data = match
                candidates.remove(match)
                updated += 1

            race_type = 'Otras'
            if '(COPA ESPAÑA)' in name.upper():
                race_type = 'Copa de España'
            elif end or name.casefold().startswith('vuelta'):
                race_type = 'Vueltas'
            if race_type == 'Otras' and data.get('type') == 'Euskaldun':
                race_type = 'Euskaldun'

            invitation = f'Invitación solicitada: {requested} · Invitación confirmada: {confirmed}'
            previous_notes = data.get('notes') or ''
            if previous_notes == LEGACY_NOTES:
                previous_notes = ''
            notes = '\n'.join(filter(None, (previous_notes, invitation)))
            data.update(name=name, date=start, endDate=end, type=race_type, notes=notes)
            record.data = cipher.encrypt(json.dumps(data, ensure_ascii=False).encode())

        receipt = {'created': created, 'updated': updated}
        db.add(Record(
            id=marker, kind='system', owner_id='direction',
            data=cipher.encrypt(json.dumps(receipt).encode()),
        ))
    return receipt


def seed_calendar(Sessions, Record, cipher):
    restore_calendar(Sessions, Record, cipher)
    payload = os.environ.get('NETKOM_CALENDAR_2027')
    if payload:
        return import_netkom_calendar(Sessions, Record, cipher, payload)
