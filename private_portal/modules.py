"""Team modules: encrypted records, explicit role allowlists, no demo data."""
import io,csv,datetime,time
from decimal import Decimal,InvalidOperation
from flask import g,request,jsonify,abort,send_file,Response
from sqlalchemy import select
from openpyxl import Workbook
from bank_reconciliation import bank_lock, bank_fingerprint, validate_bank_link

# field types: string, int, money (integer cents stored), list of IDs.
SPECS={
 'staff':dict(name='s',function='s',city='s',phone='s',notes='s',user='s'),
 'vehicle':dict(name='s',plate='s',seats='i',driver='s',notes='s'),
 'travel':dict(event='event',manager='s',hotel='s',hotelAddress='s',hotelPhone='s',booking='s',departureBilbao='s',departureZaragoza='s',meeting='s',plan='s',staff='staff[]',vehicles='vehicle[]',rooming='s',registrationDeadline='s',registrationStatus='s',registrationReference='s',routeUrl='url',scheduleUrl='url'),
 'result':dict(event='event',rider='runner',place='i',days='i',discipline='s',notes='s'),
 'days':dict(event='event',person='person',days='i',function='s',notes='s'),
 'entry':dict(date='date',event='event?',direction='direction',category='s',budget='budget?',concept='s',counterparty='s',reference='s',taxId='s',baseAmount='money',taxAmount='money',amount='money',status='s',notes='s'),
 'budget':dict(category='s',amount='money',notes='s'),
 'bank':dict(date='date',concept='s',reference='s',amount='money',direction='direction',matched='s'),
 'charge':dict(event='event?',rider='runner',concept='s',amount='money',status='s',notes='s'),
 'post':dict(event='event',type='posttype',riders='runner[]',template='i',format='format',title='s',subtitle='s',status='poststatus'),
 'license':dict(rider='runner',number='s',status='s',expiration='s',notes='s'),
 'sport':dict(rider='runner',bike='s',bikeSize='s',helmet='s',pedals='s',saddleHeight='i',saddleToBar='i',coach='s',club='s',notes='s'),
}
TECH={'staff','vehicle','travel','result','days','sport'}
MONEY={'entry','budget','bank','charge'}
LICENSE_SIDES={'licencia':'Anverso','licencia_reverso':'Reverso'}

def register_modules(app,Record,User,Document,seal,unseal,audit,require,body):
 def rows(kind):return list(g.db.scalars(select(Record).where(Record.kind=='module:'+kind)))
 def license_documents(rider_id):
  documents=g.db.scalars(select(Document).where(Document.owner_id==rider_id,Document.kind.in_(list(LICENSE_SIDES)))
                         .order_by(Document.created.desc(),Document.id.desc()))
  latest={}
  for document in documents:latest.setdefault(document.kind,document)
  return {kind:latest[kind] for kind in LICENSE_SIDES if kind in latest}
 def allowed(kind,write=False):
  if kind not in SPECS:abort(404)
  role=g.user.role
  if role=='director':return
  if role=='communication' and kind=='post':return
  if write:abort(403)
  if role=='technician' and kind in TECH:return
  if role=='runner' and kind in {'travel','result','days','charge','license','sport','post'}:return
  abort(403)
 def visible(kind,data):
  if g.user.role!='runner':return True
  if kind in ('result','charge','license','sport'):return data.get('rider')==g.user.id
  if kind=='days':return data.get('person')==g.user.id
  if kind=='post':return data.get('status')=='Aprobada' and g.user.id in data.get('riders',[])
  if kind=='travel':
   event=g.db.get(Record,data.get('event',''))
   return bool(event and g.user.id in unseal(event.data).get('called',[]))
  return False
 def output(row,kind):
  data=unseal(row.data)
  if kind=='travel' and g.user.role=='runner':data={k:v for k,v in data.items() if k not in {'rooming','booking','registrationReference','staff','vehicles'}}
  if kind=='entry':
   part=g.db.get(Record,data['budget']) if data.get('budget') else None
   data['budgetName']=unseal(part.data).get('category','') if part and part.kind in ('module:budget','archived:budget') else ''
   data['splitRecorded']=bool(g.db.get(Record,'trip-share:'+row.id))
   data['attachments']=[]
   for document in g.db.scalars(select(Document).where(Document.kind=='invoice:'+row.id)):
    meta=g.db.get(Record,'invoice-meta-'+document.id);info=unseal(meta.data) if meta else {}
    data['attachments'].append(dict(id=document.id,name=info.get('filename','factura'),size=document.size))
  return dict(data,id=row.id)
 def validate(kind,d,previous=None):
  spec=SPECS[kind];out={}
  if not isinstance(d,dict) or set(d)-set(spec):abort(400,'Campos no válidos')
  for key,typ in spec.items():
   v=d.get(key,[] if typ.endswith('[]') else 0 if typ in ('i','money') else '')
   if typ in ('s','url','date','direction','posttype','format','poststatus'):
    if not isinstance(v,str) or len(v)>2500:abort(400,'Revisa '+key)
    v=v.strip()
    if typ=='url' and v and not v.startswith('https://'):abort(400,'Los enlaces deben comenzar por https://')
    if typ=='date' and v:
     try:datetime.date.fromisoformat(v)
     except ValueError:abort(400,'Fecha no válida')
    if typ=='direction' and v not in ['Ingreso','Gasto']:abort(400)
    if typ=='posttype' and v not in ['Colectiva','Individual']:abort(400)
    if typ=='format' and v not in ['Cuadrado','Vertical','Story']:abort(400)
    if typ=='poststatus' and v not in ['Borrador','Aprobada']:abort(400)
   elif typ=='i':
    if type(v)!=int or v<0 or v>100000:abort(400,'Número no válido: '+key)
   elif typ=='money':
    # All money is integer cents, never accept floats from clients.
    if type(v)!=int or v<0 or v>100000000:abort(400,'Importe no válido')
   elif typ=='budget?':
    if not isinstance(v,str):abort(400,'Partida no válida')
    if v:
     part=g.db.get(Record,v)
     if not part or (part.kind!='module:budget' and not(part.kind=='archived:budget' and (previous or {}).get(key)==v)):
      abort(400,'Selecciona una partida presupuestaria activa')
   elif typ in ('event','event?'):
    if typ=='event?' and not v:out[key]='';continue
    if not isinstance(v,str):abort(400)
    r=g.db.get(Record,v)
    if not r or r.kind!='event':abort(400,'Actividad no encontrada')
   elif typ in ('runner','person'):
    u=g.db.get(User,v) if isinstance(v,str) else None
    if not u or not u.active or (typ=='runner' and u.role!='runner'):abort(400,'Persona no encontrada')
   elif typ.endswith('[]'):
    if not isinstance(v,list) or len(v)>100 or any(not isinstance(x,str) for x in v):abort(400)
    v=list(dict.fromkeys(v));ref=typ[:-2]
    for rid in v:
     if ref=='runner':
      u=g.db.get(User,rid)
      if not u or not u.active or u.role!='runner':abort(400,'Corredor no válido')
     else:
      r=g.db.get(Record,rid)
      if not r or r.kind!='module:'+ref:abort(400,'Recurso no válido')
   out[key]=v
  if kind=='entry' and out['direction']!='Gasto':out['budget']=''
  if kind in ('staff','vehicle') and not out['name']:abort(400,'Indica el nombre')
  if kind in ('result','days') and out['days']<1:abort(400,'Indica al menos un día')
  if kind=='post':
   ev=g.db.get(Record,out['event']);event_data=unseal(ev.data)
   if event_data.get('callStatus')!='Publicada':abort(400,'La convocatoria debe estar publicada')
   called=event_data.get('called',[])
   if not out['riders'] or any(x not in called for x in out['riders']):abort(400,'Selecciona corredores de la convocatoria')
   if out['type']=='Individual' and len(out['riders'])!=1:abort(400,'Selecciona un solo corredor')
   if out['template'] not in range(1,6):abort(400)
   for rid in out['riders']:
    if not unseal(g.db.get(User,rid).profile).get('photoConsent'):abort(400,'Falta autorización de imágenes de algún corredor')
  return out
 def lock_travel():
  if g.db.get_bind().dialect.name=='postgresql':
   from sqlalchemy import text
   g.db.execute(text('SELECT pg_advisory_xact_lock(20273001)'))

 def travel_range(event):
  start=event.get('date','')
  return start,max(start,event.get('endDate') or start)

 def check_vehicle_reservations(data,event,skip=None):
  from resources import availability_key
  for resource_id in data.get('staff',[])+data.get('vehicles',[]):
   status=g.db.get(Record,availability_key(data['event'],resource_id))
   if status and unseal(status.data)['status']=='No disponible':
    abort(409,'Uno de los recursos está marcado como no disponible para esta actividad')
   resource=g.db.get(Record,resource_id)
   if resource and resource.kind=='module:staff':
    person=unseal(resource.data).get('user')
    if person and not status:
     import hashlib
     response=g.db.get(Record,hashlib.sha256((data['event']+':'+person).encode()).hexdigest())
     if response and unseal(response.data).get('status')=='No disponible':
      abort(409,'Un técnico ha indicado que no está disponible')
  if not data.get('vehicles'):return
  start,end=travel_range(event)
  if not start:abort(400,'Indica la fecha de inicio de la actividad antes de reservar vehículos')
  for row in rows('travel'):
   if row.id==skip:continue
   other=unseal(row.data)
   if not set(data['vehicles']).intersection(other.get('vehicles',[])):continue
   record=g.db.get(Record,other['event'])
   if not record or record.kind!='event':continue
   activity=unseal(record.data)
   other_start,other_end=travel_range(activity)
   if other_start and start<=other_end and other_start<=end:
    abort(409,'Ya hay un vehículo reservado para '+activity['name']+' en esas fechas')

 def hotel_people(event_id):
  if not g.user.documents:abort(403)
  record=g.db.get(Record,event_id)
  if not record or record.kind!='event':abort(404)
  event=unseal(record.data)
  people=[]
  for rider_id in dict.fromkeys(event.get('called',[])):
   rider=g.db.get(User,rider_id)
   if rider and rider.role=='runner':
    people.append(dict(id=rider.id,name=rider.name,role='Corredor',dni=unseal(rider.profile).get('dni','')))
  planning=next((data for row in rows('travel') if (data:=unseal(row.data)).get('event')==event_id),{})
  for staff_id in dict.fromkeys(planning.get('staff',[])):
   staff=g.db.get(Record,staff_id)
   if not staff or staff.kind!='module:staff':continue
   identity=g.db.get(Record,'hotel-id:'+staff_id)
   people.append(dict(id=staff.id,name=unseal(staff.data)['name'],role='Técnico',dni=unseal(identity.data).get('dni','') if identity else ''))
  return event,people

 from hotel_documents import register_hotel_documents
 identity_documents=register_hotel_documents(app,Record,Document,hotel_people,audit,require)

 @app.get('/api/events/<event_id>/hotel/guests')
 @require('director')
 def hotel_guests(event_id):
  _,people=hotel_people(event_id)
  return jsonify(guests=[dict(id=p['id'],name=p['name'],role=p['role'],hasDni=bool(p['dni']),photos=len(identity_documents(p))) for p in people])

 @app.post('/api/events/<event_id>/hotel/staff/<staff_id>')
 @require('director')
 def hotel_staff_identity(event_id,staff_id):
  import re
  _,people=hotel_people(event_id)
  if not any(p['role']=='Técnico' and p['id']==staff_id for p in people):abort(404)
  dni=body().get('dni')
  if not isinstance(dni,str):abort(400,'Número de documento no válido')
  dni=dni.strip().upper()
  if dni and not re.fullmatch(r'[A-Z0-9-]{4,20}',dni):abort(400,'Número de documento no válido')
  g.db.get(Record,staff_id,with_for_update=True)
  identity=g.db.get(Record,'hotel-id:'+staff_id)
  if dni:
   if identity:identity.data=seal({'dni':dni})
   else:g.db.add(Record(id='hotel-id:'+staff_id,kind='system:hotel-id',owner_id=staff_id,data=seal({'dni':dni})))
  elif identity:g.db.delete(identity)
  audit('hotel_staff_identity_updated',staff_id)
  return jsonify(ok=True)

 @app.get('/api/events/<event_id>/hotel')
 @require('director')
 def hotel_export(event_id):
  event,people=hotel_people(event_id)
  if event.get('callStatus')!='Publicada' or not people:
   abort(400,'Publica la convocatoria antes de descargar el listado del hotel')
  wb=Workbook();sheet=wb.active;sheet.title='Huéspedes'
  sheet.append(['Nombre y apellidos','DNI'])
  for guest in people:
   sheet.append([guest['name'],guest['dni'] or 'Pendiente'])
   for cell in sheet[sheet.max_row]:cell.data_type='s'
  sheet.column_dimensions['A'].width=42
  sheet.column_dimensions['B'].width=22
  file=io.BytesIO();wb.save(file);file.seek(0)
  audit('hotel_guest_list_exported',event_id)
  return send_file(file,as_attachment=True,download_name='Listado_hotel.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

 @app.get('/api/modules/<kind>')
 @require()
 def list_records(kind):
  allowed(kind)
  event_id=request.args.get('event') if kind=='entry' else None
  records=[]
  for row in rows(kind):
   data=unseal(row.data)
   if event_id and (data.get('event')!=event_id or data.get('direction')!='Gasto'):continue
   if visible(kind,data):records.append(output(row,kind))
  if kind=='license' and g.user.role=='director':
   by_rider={item['rider']:item for item in records}
   for rider in g.db.scalars(select(User).where(User.role=='runner',User.active==True)):
    item=by_rider.get(rider.id)
    if item is None:
     item=dict(rider=rider.id,status='No aportada')
     records.append(item)
    if g.user.documents:
     item['photos']={kind:document.id for kind,document in license_documents(rider.id).items()}
  if kind=='budget':
   spent={}
   for row in rows('entry'):
    entry=unseal(row.data)
    part=entry.get('budget')
    if part and entry.get('direction')=='Gasto' and entry.get('status')!='Anulado':
     spent[part]=spent.get(part,0)+entry['amount']
   for item in records:item['spent']=spent.get(item['id'],0)
  return jsonify(records=records)

 @app.get('/api/licenses/<rider_id>/pdf')
 @require('director')
 def license_pdf(rider_id):
  from PIL import Image
  from pypdf import PdfReader, PdfWriter
  from pypdf.errors import PdfReadError
  from werkzeug.utils import secure_filename
  from invoice_exports import scan_page

  if not g.user.documents:abort(403)
  rider=g.db.get(User,rider_id)
  if not rider or rider.role!='runner':abort(404)
  documents=license_documents(rider_id)
  if not documents:abort(404,'Este corredor aún no tiene una licencia subida')
  cipher=app.extensions['cipher']
  writer=PdfWriter()
  for kind,document in documents.items():
   side=LICENSE_SIDES[kind]
   raw=io.BytesIO(cipher.decrypt(document.content))
   try:
    if document.mime=='application/pdf':
     reader=PdfReader(raw)
     if reader.is_encrypted or not reader.pages:raise PdfReadError('PDF unavailable')
    else:
     with Image.open(raw) as image:
      reader=scan_page(f'Licencia · {side} · {rider.name}',image)
    writer.append(reader,outline_item=side,import_outline=False,excluded_fields=['/Annots','/AA'])
   except (PdfReadError,OSError,ValueError,TypeError):
    abort(422,f'No se pudo abrir el archivo de la licencia ({side.lower()})')
  output=io.BytesIO()
  writer.write(output)
  output.seek(0)
  filename='Licencia_'+(secure_filename(rider.name) or rider.id)+'.pdf'
  audit('license_pdf_exported',rider.id)
  return Response(iter(lambda:output.read(64*1024),b''),mimetype='application/pdf',
                  headers={'Content-Disposition':f'attachment; filename="{filename}"'})
 @app.post('/api/modules/<kind>')
 @require()
 def create_record(kind):
  allowed(kind,True);data=validate(kind,body())
  if kind=='bank':
   bank_lock()
   validate_bank_link(Record,unseal,data)
  if kind=='travel':
   lock_travel()
   if any(unseal(r.data)['event']==data['event'] for r in rows(kind)):abort(409,'Ya hay planning para esta actividad; edítalo')
   check_vehicle_reservations(data,unseal(g.db.get(Record,data['event']).data))
  if kind in ('license','sport') and any(unseal(r.data)['rider']==data['rider'] for r in rows(kind)):abort(409,'Ya hay una ficha; edítala')
  r=Record(kind='module:'+kind,owner_id=g.user.id,data=seal(data));g.db.add(r);g.db.flush();audit('module_created:'+kind,r.id);return jsonify(id=r.id)
 @app.post('/api/modules/<kind>/<record_id>')
 @require()
 def edit_record(kind,record_id):
  allowed(kind,True)
  if kind=='bank':bank_lock()
  r=g.db.get(Record,record_id)
  if not r or r.kind!='module:'+kind:abort(404)
  payload=body()
  previous=unseal(r.data) if kind=='entry' else None
  if previous and 'budget' not in payload:payload['budget']=previous.get('budget','')
  data=validate(kind,payload,previous)
  if kind=='bank':validate_bank_link(Record,unseal,data,record_id)
  if kind=='travel':
   lock_travel()
   if any(x.id!=r.id and unseal(x.data)['event']==data['event'] for x in rows(kind)):abort(409,'Ya hay planning para esta actividad; edítalo')
   check_vehicle_reservations(data,unseal(g.db.get(Record,data['event']).data),r.id)
  r.data=seal(data);audit('module_updated:'+kind,r.id);return jsonify(ok=True)
 @app.post('/api/modules/<kind>/<record_id>/archive')
 @require('director')
 def archive_record(kind,record_id):
  allowed(kind,True)
  if kind=='bank':bank_lock()
  r=g.db.get(Record,record_id)
  if not r or r.kind!='module:'+kind:abort(404)
  r.kind='archived:'+kind;audit('module_archived:'+kind,r.id);return jsonify(ok=True)
 @app.post('/api/bank/import')
 @require('director')
 def bank_import():
  batch=body().get('rows')
  if not isinstance(batch,list) or not 1<=len(batch)<=2000:abort(400,'Archivo vacío o más de 2000 movimientos')
  validated=[validate('bank',r) for r in batch]
  bank_lock()
  existing={bank_fingerprint(unseal(r.data)) for r in g.db.scalars(
   select(Record).where(Record.kind.in_(['module:bank','archived:bank'])))}
  inserted=0
  for data in validated:
   data['matched']=''
   fingerprint=bank_fingerprint(data)
   if fingerprint in existing:continue
   existing.add(fingerprint)
   g.db.add(Record(kind='module:bank',owner_id=g.user.id,data=seal(data)));inserted+=1
  audit('bank_imported',str(inserted));return jsonify(imported=inserted,duplicates=len(batch)-inserted)
 @app.get('/api/people')
 @require('director','technician')
 def people():return jsonify(people=[dict(id=u.id,name=u.name,role=u.role) for u in g.db.scalars(select(User).where(User.active==True))])
 @app.get('/api/archive')
 @require('director')
 def archive():return jsonify(records=[dict(unseal(r.data),id=r.id,kind=r.kind.split(':',1)[1]) for r in g.db.scalars(select(Record).where(Record.kind.like('archived:%')))])
 @app.post('/api/archive/<record_id>/restore')
 @require('director')
 def restore(record_id):
  r=g.db.get(Record,record_id)
  if not r or not r.kind.startswith('archived:'):abort(404)
  if r.kind=='archived:bank':
   bank_lock()
   validate_bank_link(Record,unseal,unseal(r.data),r.id)
  if r.kind=='archived:travel':
   lock_travel()
   data=unseal(r.data)
   if any(unseal(row.data)['event']==data['event'] for row in rows('travel')):abort(409,'Ya hay planning para esta actividad')
   event=g.db.get(Record,data['event'])
   if not event or event.kind!='event':abort(400,'Actividad no encontrada')
   check_vehicle_reservations(data,unseal(event.data))
  r.kind='module:'+r.kind.split(':',1)[1];audit('module_restored',r.id);return jsonify(ok=True)
 @app.get('/api/modules/<kind>/export')
 @require()
 def export_module(kind):
  allowed(kind);wb=Workbook();ws=wb.active;ws.title=kind[:31];keys=list(SPECS[kind]);ws.append(keys)
  for r in rows(kind):
   d=unseal(r.data)
   if not visible(kind,d):continue
   d=output(r,kind);line=[]
   for k in keys:
    v=d.get('budgetName','') if k=='budget' else d.get(k,'')
    if isinstance(v,list):v=', '.join(v)
    if SPECS[kind][k]=='money':v=v/100
    if isinstance(v,str) and v.startswith(('=','+','-','@')):v="'"+v
    line.append(v)
   ws.append(line)
  ws.freeze_panes='A2'
  for col in ws.columns:ws.column_dimensions[col[0].column_letter].width=24
  f=io.BytesIO();wb.save(f);f.seek(0);audit('module_exported:'+kind)
  return send_file(f,as_attachment=True,download_name=kind+'.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
 @app.get('/api/summary')
 @require('director')
 def summary():
  def amounts(kind,direction=None):return sum(unseal(r.data).get('amount',0) for r in rows(kind) if not direction or unseal(r.data).get('direction')==direction)
  return jsonify(riders=g.db.scalar(select(__import__('sqlalchemy').func.count()).select_from(User).where(User.role=='runner',User.active==True)),events=g.db.scalar(select(__import__('sqlalchemy').func.count()).select_from(Record).where(Record.kind=='event')),income=amounts('entry','Ingreso'),expenses=amounts('entry','Gasto'),budget=amounts('budget'),charges=amounts('charge'),staff=len(rows('staff')),vehicles=len(rows('vehicle')))
 @app.post('/api/events/<event_id>/details')
 @require('director')
 def event_details(event_id):
  d=body()
  if {'date','endDate'}.intersection(d):lock_travel()
  r=g.db.get(Record,event_id,with_for_update=True)
  if not r or r.kind!='event':abort(404)
  out=unseal(r.data);previous_dates=travel_range(out)
  for k,v in d.items():
   if k not in ('name','date','endDate','place','category','type','status','owner','notes','callStatus') or not isinstance(v,str) or len(v)>2000:abort(400)
   if k in ('date','endDate') and v:
    try:datetime.date.fromisoformat(v)
    except ValueError:abort(400)
   if k=='callStatus' and v not in ['Borrador','Publicada']:abort(400)
   out[k]=v
  if not out.get('name'):abort(400)
  if d.get('callStatus')=='Publicada':
   if not out.get('called'):abort(400,'Selecciona corredores antes de publicar')
   for rid in out['called']:
    a=g.db.get(Record,__import__('hashlib').sha256((event_id+':'+rid).encode()).hexdigest())
    if not a or unseal(a.data).get('status')!='Disponible':abort(400,'Revisa la disponibilidad de los convocados')
  if travel_range(out)!=previous_dates:
   for travel in rows('travel'):
    data=unseal(travel.data)
    if data['event']==event_id:check_vehicle_reservations(data,out,travel.id)
  r.data=seal(out);audit('event_updated',r.id);return jsonify(ok=True)
 @app.get('/api/events/<event_id>/package')
 @require('director')
 def event_package(event_id):
  ev=g.db.get(Record,event_id)
  if not ev or ev.kind!='event':abort(404)
  e=unseal(ev.data);wb=Workbook();ws=wb.active;ws.title='Convocatoria'
  def safe(v):return "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v
  ws.append(['Actividad',safe(e['name'])]);ws.append(['Fecha',e.get('date','')]);ws.append(['Estado',e.get('callStatus','Borrador')]);ws.append([]);ws.append(['Corredor','Número licencia','Estado licencia'])
  licenses={unseal(r.data)['rider']:unseal(r.data) for r in rows('license')}
  for rid in e.get('called',[]):
   u=g.db.get(User,rid)
   if u:ws.append([safe(u.name),safe(licenses.get(rid,{}).get('number','')),licenses.get(rid,{}).get('status','No aportada')])
  hotel=wb.create_sheet('Listado hotel');hotel.append(['Huésped','Actividad'])
  for rid in e.get('called',[]):
   u=g.db.get(User,rid)
   if u:hotel.append([safe(u.name),safe(e['name'])])
  ws=wb.create_sheet('Planning')
  planning=next((unseal(r.data) for r in rows('travel') if unseal(r.data).get('event')==event_id),{})
  labels={'manager':'Responsable','hotel':'Hotel','hotelAddress':'Dirección hotel','hotelPhone':'Teléfono hotel','booking':'Reserva','departureBilbao':'Salida Bilbao','departureZaragoza':'Salida Zaragoza','meeting':'Encuentro','plan':'Planning','rooming':'Habitaciones','registrationStatus':'Inscripción'}
  for key,label in labels.items():ws.append([label,safe(planning.get(key,''))])
  for sheet in wb:
   for col in sheet.columns:sheet.column_dimensions[col[0].column_letter].width=32
  f=io.BytesIO();wb.save(f);f.seek(0);audit('event_package_exported',event_id)
  return send_file(f,as_attachment=True,download_name='Convocatoria_y_hotel.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
 @app.post('/api/fines/<fine_id>/status')
 @require('director')
 def fine_status(fine_id):
  r=g.db.get(Record,fine_id)
  if not r or r.kind!='fine':abort(404)
  d=unseal(r.data);status=body().get('status')
  if status not in ['Pendiente','Pagada','Anulada','Pendiente de decisión','Resuelta']:abort(400)
  d['status']=status;r.data=seal(d);audit('fine_status_updated',r.id);return jsonify(ok=True)
 @app.post('/api/users/<target>/restore')
 @require('director')
 def restore_user(target):
  if not g.user.owner:abort(403)
  u=g.db.get(User,target)
  if not u:abort(404)
  u.active=True;audit('user_restored',target);return jsonify(ok=True)
 @app.get('/api/media/roster')
 @require('director','communication','runner')
 def media_roster():
  result=[]
  for u in g.db.scalars(select(User).where(User.role=='runner',User.active==True)):
   if g.user.role=='runner' and u.id!=g.user.id:continue
   if not unseal(u.profile).get('photoConsent'):continue
   photos=[dict(id=d.id,kind=d.kind) for d in g.db.scalars(select(Document).where(Document.owner_id==u.id,Document.kind.in_(['portrait','action'])))]
   result.append(dict(id=u.id,name=u.name,photos=photos))
  return jsonify(riders=result)
