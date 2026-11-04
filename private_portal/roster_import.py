"""One-time encrypted roster import from a sensitive deployment variable.
Actual roster data must never be put in source control or public assets.
"""
import json,hashlib,unicodedata,time
from sqlalchemy import select,text

def normalize(value):
 return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',str(value)) if not unicodedata.combining(c)).upper().split())

def import_roster(Sessions,Record,User,cipher,payload):
 data=json.loads(payload)
 if not isinstance(data,list) or not 1<=len(data)<=100:raise ValueError('Invalid roster import')
 checked=[];keys=set()
 for row in data:
  if not isinstance(row,dict) or set(row)-{'firstName','surname','birthYear','dni'}:raise ValueError('Invalid roster fields')
  first=row.get('firstName','').strip();surname=row.get('surname','').strip();year=str(row.get('birthYear','')).strip();dni=row.get('dni','').strip().upper()
  if not first or not surname or len(first)>100 or len(surname)>180 or not year.isdigit() or not 2000<=int(year)<=2020 or len(dni)>20:raise ValueError('Invalid roster row')
  key=normalize(first+' '+surname)
  if key in keys:raise ValueError('Duplicate roster row')
  keys.add(key);checked.append(dict(firstName=first,surname=surname,birthYear=year,dni=dni))
 payload_hash=hashlib.sha256(payload.encode()).hexdigest();marker='roster-import:'+payload_hash
 with Sessions.begin() as db:
  if db.get_bind().dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(20271818)'))
  previous=db.get(Record,marker)
  if previous:return json.loads(cipher.decrypt(previous.data))
  existing=list(db.scalars(select(User).where(User.role=='runner')));added=0;updated=0;conflicts=0
  for row in checked:
   fullname=row['firstName']+' '+row['surname'];key=normalize(fullname)
   matches=[u for u in existing if normalize(u.name)==key]
   if len(matches)>1:raise ValueError('Ambiguous existing rider')
   if matches:
    u=matches[0];profile=json.loads(cipher.decrypt(u.profile));updated+=1
    for field,value in row.items():
     if value and not profile.get(field):profile[field]=value
     elif value and profile.get(field)!=value:conflicts+=1
    u.profile=cipher.encrypt(json.dumps(profile,ensure_ascii=False).encode())
   else:
    rider_id='rider-'+hashlib.sha256(key.encode()).hexdigest()[:26]
    if db.get(User,rider_id):raise ValueError('Rider identifier conflict')
    profile=dict(row,source='Listado de plantilla facilitado por Dirección',dniStatus='Pendiente de verificación' if row['dni'] else 'No aportado',photoConsent=False)
    u=User(id=rider_id,email=None,name=fullname,role='runner',password=None,mfa=None,active=True,documents=False,owner=False,profile=cipher.encrypt(json.dumps(profile,ensure_ascii=False).encode()))
    db.add(u);existing.append(u);added+=1
  result=dict(added=added,updated=updated,total=len(checked),conflicts=conflicts,at=int(time.time()))
  db.add(Record(id=marker,kind='system:roster-import',owner_id='direction',data=cipher.encrypt(json.dumps(result).encode())))
  return result
