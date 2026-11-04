"""Only the user's previously supplied planned races; no invented dates or people."""
import json,hashlib
from sqlalchemy import select,text
RACES=[('Circuito del Guadiana','Febrero','Copa de España',''),('Albi','Marzo','UCI',''),('La Canonja','Abril','UCI','Alfonso'),('El Baruco','Abril','Carrera','Alfonso'),('Chele Campos','Abril','Carrera','Alfonso'),('Vuelta Montaña Central','Sin fecha','Vuelta',''),('Vuelta a Besaya','Sin fecha','Vuelta',''),('Vuelta Gipuzkoa','Sin fecha','Vuelta',''),('Vuelta Bizkaia','Sin fecha','Vuelta',''),('Vuelta a Pamplona','Sin fecha','Vuelta','Alfonso'),('Vuelta Ribera del Duero','Sin fecha','UCI',''),('Vuelta a Cantabria','Sin fecha','Vuelta','Alfonso')]
def seed_calendar(Sessions,Record,cipher):
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
