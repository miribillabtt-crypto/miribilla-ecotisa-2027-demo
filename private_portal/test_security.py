import io,json,time,secrets
import pytest,pyotp
from cryptography.fernet import Fernet
from sqlalchemy import select
from werkzeug.security import generate_password_hash
from PIL import Image
from server import create_app,User,Record,Document,Audit,Invite

@pytest.fixture
def env(tmp_path):
 app=create_app({'TESTING':True,'DATABASE_URL':'sqlite:///'+str(tmp_path/'test.db'),'ENCRYPTION_KEY':Fernet.generate_key()})
 cipher=app.extensions['cipher'];db=app.extensions['db_sessions']();secrets_by={};ids={}
 for role in ['director','technician','runner','runner2','communication','director_limited']:
  secret=pyotp.random_base32();secrets_by[role]=secret
  user=User(email=role+'@test.invalid',name=role,role='runner' if role=='runner2' else 'director' if role=='director_limited' else role,password=generate_password_hash('un-password-seguro-de-prueba'),mfa=cipher.encrypt(json.dumps(secret).encode()),profile=cipher.encrypt(json.dumps({}).encode()),documents=role=='director',owner=role=='director')
  db.add(user);db.flush();ids[role]=user.id
 db.commit();db.close()
 def login(role):
  client=app.test_client();resp=client.post('/api/login',json={'email':role+'@test.invalid','password':'un-password-seguro-de-prueba','code':pyotp.TOTP(secrets_by[role]).now()})
  assert resp.status_code==200,resp.json
  csrf=client.get('/api/me').json['csrf'];return client,{'X-CSRF-Token':csrf}
 return app,ids,login,secrets_by

def test_unauthenticated_denied(env):
 app,ids,_,_=env;c=app.test_client()
 for path in ['/api/users','/api/events','/api/clothes','/api/profile/'+ids['runner'],'/api/documents/'+ids['runner'],'/api/audit']:
  assert c.get(path).status_code==401

def test_direction_creates_events_with_optional_end_date(env):
 _,_,login,_=env
 director,h=login('director')
 runner,rh=login('runner')
 path='/api/events'
 event={'name':'Vuelta de prueba','date':'2027-02-27','endDate':'2027-03-01'}
 assert runner.post(path,json=event,headers=rh).status_code==403
 assert director.post(path,json={**event,'date':''},headers=h).status_code==400
 assert director.post(path,json={**event,'endDate':'2027-02-26'},headers=h).status_code==400
 assert director.post(path,json={**event,'endDate':'2027-02-29'},headers=h).status_code==400
 assert director.post(path,json=event,headers=h).status_code==200
 assert director.post(path,json={'name':'Prueba de un día','date':'2027-03-05'},headers=h).status_code==200
 events={row['name']:row for row in director.get(path).json['events']}
 assert events[event['name']]['date']==event['date']
 assert events[event['name']]['endDate']==event['endDate']
 assert events['Prueba de un día']['endDate']==''

def test_direction_provisions_linked_technician_accounts(env):
 app,_,login,_=env
 director,h=login('director_limited')
 technician,th=login('technician')
 path='/api/staff/accounts'
 assert technician.post(path,json={'name':'Otro Técnico'},headers=th).status_code==403
 assert director.post(path,json={'name':' '},headers=h).status_code==400
 existing=director.post('/api/modules/staff',json={'name':'Técnica Existente','function':'Mecánica'},headers=h).json['id']
 new=director.post(path,json={'name':'Álvaro de Prueba'},headers=h)
 assert new.status_code==200,new.json
 account=new.json['accounts'][0]
 assert account['username']=='alvaro.de.prueba'
 assert director.post(path,json={'name':'alvaro de prueba'},headers=h).status_code==409
 pending=director.post(path,json={},headers=h).json
 assert [a['username'] for a in pending['accounts']]==['tecnica.existente']
 assert director.post(path,json={},headers=h).json['accounts']==[]
 staff={row['name']:row for row in director.get('/api/modules/staff').json['records']}
 assert staff['Técnica Existente']['id']==existing and staff['Técnica Existente']['function']=='Mecánica'
 for access in [account,*pending['accounts']]:
  client=app.test_client()
  assert client.post('/api/login',json={'email':access['username'],'password':access['password']}).status_code==200
  user=client.get('/api/me').json['user']
  assert user['id']==staff[access['name']]['user']
  assert user['role']=='technician' and not user['owner'] and not user['documents']
  assert client.get('/api/users').status_code==403

def test_technician_password_from_existing_staff_row(env):
 app,ids,login,_=env
 director,h=login('director')
 limited,lh=login('director_limited')
 technician,th=login('technician')
 staff_path='/api/modules/staff'
 path='/api/staff/accounts'
 staff=director.post(staff_path,json={'name':'Eva Núñez'},headers=h).json['id']
 assert technician.post(path,json={'staffId':staff},headers=th).status_code==403
 account=limited.post(path,json={'staffId':staff},headers=lh).json['accounts'][0]
 assert account['username']=='eva.nunez' and account['password'].startswith('Nunez-')
 assert limited.post(path,json={'staffId':staff,'replace':True},headers=lh).status_code==403
 assert director.post(path,json={'staffId':staff},headers=h).status_code==409
 client=app.test_client()
 assert client.post('/api/login',json={'email':account['username'],'password':account['password']}).status_code==200
 renewed=director.post(path,json={'staffId':staff,'replace':True},headers=h).json['accounts'][0]
 assert renewed['username']==account['username'] and renewed['password']!=account['password']
 assert client.get('/api/me').json['user'] is None
 assert client.post('/api/login',json={'email':renewed['username'],'password':renewed['password']}).status_code==200
 linked=director.post(staff_path,json={'name':'Aitor Peña','user':ids['technician']},headers=h).json['id']
 access=director.post(path,json={'staffId':linked,'replace':True},headers=h).json['accounts'][0]
 assert access['username']=='aitor.pena'
 client=app.test_client()
 assert client.post('/api/login',json={'email':access['username'],'password':access['password']}).status_code==200
 assert client.get('/api/me').json['user']['id']==ids['technician']
 invalid=director.post(staff_path,json={'name':'Otra ficha','user':ids['runner']},headers=h).json['id']
 assert director.post(path,json={'staffId':invalid,'replace':True},headers=h).status_code==409

def test_runner_cannot_read_other_profile(env):
 _,ids,login,_=env;c,h=login('runner')
 assert c.get('/api/profile/'+ids['runner2']).status_code==403
 assert c.get('/api/users').status_code==403
 assert c.get('/api/clothes/export').status_code==403
 assert c.post('/api/invites',json={},headers=h).status_code==403

def test_technician_communication_denied_private(env):
 _,ids,login,_=env
 for role in ['technician','communication']:
  c,h=login(role)
  assert c.get('/api/profile/'+ids['runner']).status_code==403
  assert c.get('/api/clothes').status_code==403
  assert c.post('/api/fines',json={},headers=h).status_code==403

def test_csrf_enforced(env):
 _,ids,login,_=env;c,h=login('runner')
 assert c.post('/api/profile/'+ids['runner'],json={'phone':'123'}).status_code==403
 assert c.post('/api/profile/'+ids['runner'],json={'phone':'123'},headers=h).status_code==200

def test_document_object_permissions_and_encryption(env):
 app,ids,login,_=env;c,h=login('runner');img=io.BytesIO();Image.new('RGB',(100,100),'blue').save(img,format='PNG');raw=img.getvalue()
 r=c.post('/api/documents/'+ids['runner'],data={'kind':'dni','file':(io.BytesIO(raw),'dni.png')},headers=h)
 assert r.status_code==200,r.json
 docs=c.get('/api/documents/'+ids['runner']).json['documents'];did=docs[0]['id']
 with app.extensions['db_sessions']() as db:
  file=db.get(Document,did);assert file.content.startswith(b'gAAAA');assert not file.content.startswith(b'\xff\xd8')
 for role in ['runner2','technician','communication','director_limited']:
  other,_=login(role);assert other.get('/api/file/'+did).status_code==403
 director,_=login('director');assert director.get('/api/file/'+did).status_code==200
 assert c.get('/api/file/'+did).headers['Cache-Control']=='no-store'
 assert c.post('/api/documents/'+ids['runner'],data={'kind':'dni','file':(io.BytesIO(b'<script>bad</script>'),'x.png')},headers=h).status_code==400

def test_limited_director_cannot_read_sensitive_fields(env):
 _,ids,login,_=env;c,h=login('runner');c.post('/api/profile/'+ids['runner'],json={'iban':'PRIVATE','phone':'SECRET'},headers=h)
 limited,lh=login('director_limited');p=limited.get('/api/profile/'+ids['runner']).json['profile'];assert 'iban' not in p and 'phone' not in p
 assert limited.post('/api/profile/'+ids['runner'],json={'iban':'OTHER'},headers=lh).status_code==403
 assert limited.post('/api/invites',json={},headers=lh).status_code==403

def test_disabling_revokes_all_sessions(env):
 _,ids,login,_=env;runner,h=login('runner');director,dh=login('director')
 assert director.post('/api/users/'+ids['runner']+'/disable',json={},headers=dh).status_code==200
 assert runner.get('/api/events').status_code==401

def test_password_only_login(env):
 app,_,_,_=env;c=app.test_client()
 assert c.post('/api/login',json={'email':'runner@test.invalid','password':'un-password-seguro-de-prueba'}).status_code==200

def test_invite_single_use_and_no_role_escalation(env):
 app,_,login,_=env;c,h=login('director');r=c.post('/api/invites',json={'name':'New Runner','email':'new@test.invalid','role':'runner','documents':True},headers=h);assert r.status_code==200
 token=r.json['token'];a=app.test_client();setup=a.post('/api/activate/start',json={'token':token});assert setup.status_code==200
 params={'token':token,'password':'abcdef','role':'director'}
 assert a.post('/api/activate/finish',json=params).status_code==200
 assert a.post('/api/activate/finish',json=params).status_code==400
 with app.extensions['db_sessions']() as db:
  u=db.scalar(select(User).where(User.email=='new@test.invalid'));assert u.role=='runner' and not u.documents

def test_clothes_export_defaults_and_registered_quantities(env):
 _,ids,login,_=env;c,h=login('director')
 r=c.post('/api/profile/'+ids['runner'],json={'sizes':{'Maillot corto':'S','Culote corto':'XS'},'quantities':{'Maillot corto':2,'Camiseta':3}},headers=h)
 assert r.status_code==200
 r=c.post('/api/profile/'+ids['runner2'],json={'sizes':{'Maillot corto':'S'},'quantities':{'Maillot corto':1}},headers=h)
 assert r.status_code==200
 from openpyxl import load_workbook
 wb=load_workbook(io.BytesIO(c.get('/api/clothes/export').data))
 summary={(item,size):qty for item,size,qty in list(wb['Resumen proveedor'].values)[1:]}
 assert summary[('Camiseta','Sin indicar')]==5
 assert summary[('Maillot corto','S')]==3
 assert summary[('Chaleco','Sin indicar')]==2
 assert ('runner','Culote corto','XS',1) in list(wb['Por corredor'].values)
 totals=dict(list(wb['Total por prenda'].values)[1:])
 assert totals['Camiseta']==5 and totals['Chaleco']==2
 assert totals['TOTAL UNIDADES']==30
 api_riders={rider['id']:rider for rider in c.get('/api/clothes').json['riders']}
 assert api_riders[ids['runner2']]['quantities']['Camiseta']==2
 assert api_riders[ids['runner2']]['quantities']['Chaleco']==1
 assert c.post('/api/profile/'+ids['runner2'],json={'quantities':{'Chaleco':0}},headers=h).status_code==200
 updated=load_workbook(io.BytesIO(c.get('/api/clothes/export').data))
 assert dict(list(updated['Total por prenda'].values)[1:])['Chaleco']==1
 assert len(list(updated['Por corredor'].values))==27

def test_call_requires_available_runner(env):
 app,ids,login,_=env;c,h=login('director');assert c.post('/api/events',json={'name':'Carrera','date':'2027-02-01','place':'Bilbao'},headers=h).status_code==200
 eid=c.get('/api/events').json['events'][0]['id'];assert c.post('/api/events/'+eid+'/call',json={'users':[ids['runner']]},headers=h).status_code==400
 r,rh=login('runner');assert r.post('/api/events/'+eid+'/availability',json={'status':'Disponible'},headers=rh).status_code==200
 assert c.post('/api/events/'+eid+'/call',json={'users':[ids['runner']]},headers=h).status_code==200

def test_runner_only_reads_own_fines(env):
 _,ids,login,_=env
 director,h=login('director')
 runner,rh=login('runner')
 other,_=login('runner2')
 assert runner.get('/api/fines').json['fines']==[]
 for role in ('runner','runner2'):
  assert director.post('/api/fines',json={'user':ids[role],'type':0,'note':role},headers=h).status_code==200
 all_fines=director.get('/api/fines').json['fines']
 assert len(all_fines)==2
 for client,role in ((runner,'runner'),(other,'runner2')):
  fines=client.get('/api/fines?user='+ids['runner2']).json['fines']
  assert len(fines)==1 and fines[0]['user']==ids[role]
 foreign=next(fine for fine in all_fines if fine['user']==ids['runner2'])
 assert runner.post('/api/fines/'+foreign['id']+'/status',json={'status':'Pagada'},headers=rh).status_code==403

def test_photos_require_consent_for_communication(env):
 app,ids,login,_=env;c,h=login('runner');img=io.BytesIO();Image.new('RGB',(10,10)).save(img,format='PNG')
 c.post('/api/documents/'+ids['runner'],data={'kind':'portrait','file':(io.BytesIO(img.getvalue()),'photo.png')},headers=h)
 did=c.get('/api/documents/'+ids['runner']).json['documents'][0]['id'];comm,_=login('communication')
 assert comm.get('/api/file/'+did).status_code==403
 c.post('/api/profile/'+ids['runner'],json={'photoConsent':True},headers=h)
 assert comm.get('/api/file/'+did).status_code==200
 c.post('/api/profile/'+ids['runner'],json={'photoConsent':False},headers=h)
 assert comm.get('/api/file/'+did).status_code==403

def test_expired_invite_rejected(env):
 app,_,login,_=env;c,h=login('director');r=c.post('/api/invites',json={'name':'Expired','email':'expired@test.invalid','role':'runner'},headers=h)
 from server import digest
 with app.extensions['db_sessions']() as db:
  i=db.get(Invite,digest(r.json['token']));i.expires=0;db.commit()
 assert app.test_client().post('/api/activate/start',json={'token':r.json['token']}).status_code==400

def test_reset_invalidates_previous_links(env):
 app,ids,login,_=env;c,h=login('director')
 first=c.post('/api/users/'+ids['runner']+'/reset',json={},headers=h).json['token']
 second=c.post('/api/users/'+ids['runner']+'/reset',json={},headers=h).json['token']
 guest=app.test_client();assert guest.post('/api/activate/start',json={'token':first}).status_code==400
 assert guest.post('/api/activate/start',json={'token':second}).status_code==200

def test_headers_and_throttling(env):
 app,_,_,_=env;c=app.test_client()
 r=c.get('/');assert r.headers['X-Frame-Options']=='DENY';assert "frame-ancestors 'none'" in r.headers['Content-Security-Policy']
 for _ in range(8):assert c.post('/api/login',json={'email':'nobody@test.invalid','password':'fake','code':'123456'}).status_code==401
 assert c.post('/api/login',json={'email':'nobody@test.invalid','password':'fake','code':'123456'}).status_code==429

def test_owner_recovery_revokes_previous_password_and_sessions(env,monkeypatch):
 from server import digest
 app,ids,login,_=env;c,_=login('director');token='owner-reset-test-token'
 monkeypatch.setenv('BOOTSTRAP_TOKEN_HASH',digest(token));monkeypatch.setenv('BOOTSTRAP_EXPIRES',str(int(time.time())+3600));monkeypatch.setenv('ADMIN_EMAIL','director@test.invalid')
 guest=app.test_client();assert guest.post('/api/activate/start',json={'token':token}).status_code==200
 assert c.get('/api/users').status_code==401
 assert guest.post('/api/activate/finish',json={'token':token,'password':'newpass'}).status_code==200
 assert guest.post('/api/login',json={'email':'director@test.invalid','password':'newpass'}).status_code==200
 with app.extensions['db_sessions']() as db:assert db.get(User,ids['director']).owner

def test_remember_device_sets_30_day_cookie(env):
 app,_,_,_=env;c=app.test_client()
 r=c.post('/api/login',json={'email':'runner@test.invalid','password':'un-password-seguro-de-prueba','remember':True})
 assert r.status_code==200
 assert 'Max-Age=2592000' in r.headers['Set-Cookie']
 assert 'HttpOnly' in r.headers['Set-Cookie'] and 'Secure' in r.headers['Set-Cookie']

def test_all_module_routes_require_authentication(env):
 app,_,_,_=env;c=app.test_client()
 for kind in ['staff','vehicle','travel','result','days','entry','budget','bank','charge','license','sport','post']:
  assert c.get('/api/modules/'+kind).status_code==401
  assert c.post('/api/modules/'+kind,json={}).status_code==401

def test_modules_role_isolation(env):
 _,_,login,_=env
 for role in ['runner','technician','communication']:
  c,h=login(role)
  for kind in ['entry','budget','bank']:
   assert c.get('/api/modules/'+kind).status_code==403
   assert c.get('/api/modules/'+kind+'/export').status_code==403
  assert c.post('/api/bank/import',json={'rows':[]},headers=h).status_code==403
  if role!='runner':assert c.get('/api/modules/charge').status_code==403
 comm,_=login('director_limited')
 assert comm.get('/api/modules/entry').status_code==200

def test_shared_staff_crud_archive_and_restore(env):
 app,ids,login,_=env;c,h=login('director')
 r=c.post('/api/modules/staff',json={'name':'Mecánico','function':'Mecánico','city':'Bilbao'},headers=h);assert r.status_code==200,r.json
 rid=r.json['id'];tech,th=login('technician')
 assert tech.get('/api/modules/staff').json['records'][0]['name']=='Mecánico'
 assert tech.post('/api/modules/staff/'+rid,json={'name':'Otro'},headers=th).status_code==403
 assert c.post('/api/modules/staff/'+rid,json={'name':'Auxiliar','function':'Auxiliar'},headers=h).status_code==200
 assert c.post('/api/modules/staff/'+rid+'/archive',json={},headers=h).status_code==200
 assert c.get('/api/modules/staff').json['records']==[]
 assert c.post('/api/archive/'+rid+'/restore',json={},headers=h).status_code==200
 assert c.get('/api/modules/staff').json['records'][0]['name']=='Auxiliar'

def test_runner_receipts_only_own_and_no_money_write(env):
 app,ids,login,_=env;c,h=login('director');c.post('/api/events',json={'name':'Trip','date':'2027-03-01'},headers=h);eid=c.get('/api/events').json['events'][0]['id']
 for role in ['runner','runner2']:
  response=c.post('/api/modules/charge',json={'event':eid,'rider':ids[role],'concept':'Hotel','amount':2500,'status':'Pendiente'},headers=h);assert response.status_code==200,response.json
 r,rh=login('runner');records=r.get('/api/modules/charge').json['records'];assert len(records)==1 and records[0]['rider']==ids['runner']
 assert r.post('/api/modules/charge/'+records[0]['id'],json={},headers=rh).status_code==403
 from openpyxl import load_workbook
 wb=load_workbook(io.BytesIO(r.get('/api/modules/charge/export').data));assert len(list(wb.active.values))==2

def test_bank_import_atomic_and_duplicate_safe(env):
 _,_,login,_=env;c,h=login('director')
 row={'date':'2027-01-01','concept':'Patrocinio','reference':'A1','amount':10000,'direction':'Ingreso','matched':''}
 invalid=dict(row,amount=-1)
 assert c.post('/api/bank/import',json={'rows':[row,invalid]},headers=h).status_code==400
 assert c.get('/api/modules/bank').json['records']==[]
 assert c.post('/api/bank/import',json={'rows':[row,row]},headers=h).json['imported']==1
 assert c.post('/api/bank/import',json={'rows':[row]},headers=h).json['imported']==0

def test_runner_planning_redacts_other_guests_and_booking(env):
 app,ids,login,_=env;c,h=login('director');c.post('/api/events',json={'name':'Trip'},headers=h);eid=c.get('/api/events').json['events'][0]['id']
 with app.extensions['db_sessions']() as db:
  r=db.get(Record,eid);cipher=app.extensions['cipher'];data=json.loads(cipher.decrypt(r.data));data['called']=[ids['runner']];r.data=cipher.encrypt(json.dumps(data).encode());db.commit()
 assert c.post('/api/modules/travel',json={'event':eid,'hotel':'Hotel','booking':'PRIVATE','rooming':'OTHER GUESTS'},headers=h).status_code==200
 runner,_=login('runner');rows=runner.get('/api/modules/travel').json['records'];assert len(rows)==1 and 'rooming' not in rows[0] and 'booking' not in rows[0]
 other,_=login('runner2');assert other.get('/api/modules/travel').json['records']==[]

def test_communication_posts_require_published_call_and_consent(env):
 app,ids,login,_=env;director,h=login('director');director.post('/api/events',json={'name':'Race'},headers=h);eid=director.get('/api/events').json['events'][0]['id']
 comm,ch=login('communication');post={'event':eid,'type':'Individual','riders':[ids['runner']],'template':1,'format':'Cuadrado','title':'Race','subtitle':'','status':'Aprobada'}
 assert comm.post('/api/modules/post',json=post,headers=ch).status_code==400
 with app.extensions['db_sessions']() as db:
  cipher=app.extensions['cipher'];e=db.get(Record,eid);data=json.loads(cipher.decrypt(e.data));data.update(called=[ids['runner']],callStatus='Publicada');e.data=cipher.encrypt(json.dumps(data).encode());u=db.get(User,ids['runner']);u.profile=cipher.encrypt(json.dumps({'photoConsent':True}).encode());db.commit()
 assert comm.post('/api/modules/post',json=post,headers=ch).status_code==200
 own,_=login('runner');other,_=login('runner2');assert len(own.get('/api/modules/post').json['records'])==1;assert other.get('/api/modules/post').json['records']==[]
 assert comm.get('/api/modules/license').status_code==403

def test_bulk_invites_are_atomic_and_restricted(env):
 app,_,login,_=env;c,h=login('director')
 rows=[{'name':'New','email':'new@example.invalid','role':'runner'},{'name':'Bad','email':'bad','role':'root'}]
 assert c.post('/api/invites/import',json={'rows':rows},headers=h).status_code==400
 with app.extensions['db_sessions']() as db:assert db.scalar(select(Invite).where(Invite.email=='new@example.invalid')) is None
 response=c.post('/api/invites/import',json={'rows':rows[:1]},headers=h);assert response.status_code==200 and len(response.json['invitations'])==1
 tech,th=login('technician');assert tech.post('/api/invites/import',json={'rows':rows[:1]},headers=th).status_code==403

def test_communication_uploads_only_consent_photos(env):
 app,ids,login,_=env;c,h=login('communication');im=io.BytesIO();Image.new('RGB',(10,10)).save(im,format='PNG');raw=im.getvalue()
 assert c.post('/api/documents/'+ids['runner'],data={'kind':'portrait','file':(io.BytesIO(raw),'p.png')},headers=h).status_code==403
 with app.extensions['db_sessions']() as db:
  u=db.get(User,ids['runner']);u.profile=app.extensions['cipher'].encrypt(json.dumps({'photoConsent':True}).encode());db.commit()
 assert c.post('/api/documents/'+ids['runner'],data={'kind':'portrait','file':(io.BytesIO(raw),'p.png')},headers=h).status_code==200
 assert c.post('/api/documents/'+ids['runner'],data={'kind':'dni','file':(io.BytesIO(raw),'dni.png')},headers=h).status_code==403

def test_calendar_restore_preserves_existing_and_is_idempotent(env):
 from calendar_seed import seed_calendar,RACES
 app,_,_,_=env;S=app.extensions['db_sessions'];cipher=app.extensions['cipher']
 with S.begin() as db:db.add(Record(id='real-event',kind='event',owner_id='direction',data=cipher.encrypt(json.dumps({'name':'Albi','date':'2027-03-15','called':['test']}).encode())))
 seed_calendar(S,Record,cipher);seed_calendar(S,Record,cipher)
 with S() as db:
  records=list(db.scalars(select(Record).where(Record.kind=='event')));assert len(records)==len(RACES)
  assert json.loads(cipher.decrypt(db.get(Record,'real-event').data))['date']=='2027-03-15'

def test_event_package_has_names_but_no_identity_or_bank(env):
 app,ids,login,_=env;c,h=login('director');c.post('/api/events',json={'name':'Trip'},headers=h);eid=c.get('/api/events').json['events'][0]['id']
 with app.extensions['db_sessions']() as db:
  cipher=app.extensions['cipher'];e=db.get(Record,eid);data=json.loads(cipher.decrypt(e.data));data['called']=[ids['runner']];e.data=cipher.encrypt(json.dumps(data).encode());u=db.get(User,ids['runner']);u.profile=cipher.encrypt(json.dumps({'iban':'SENSITIVE_IBAN','dni':'SENSITIVE_DNI'}).encode());db.commit()
 from openpyxl import load_workbook
 r=c.get('/api/events/'+eid+'/package');assert r.status_code==200
 wb=load_workbook(io.BytesIO(r.data));assert set(wb.sheetnames)=={'Convocatoria','Listado hotel','Planning'}
 rendered=str([list(sheet.values) for sheet in wb]);assert 'SENSITIVE_IBAN' not in rendered and 'SENSITIVE_DNI' not in rendered
 runner,_=login('runner');assert runner.get('/api/events/'+eid+'/package').status_code==403

def test_invoice_original_exact_bytes_encrypted_and_roles(env):
 app,ids,login,_=env;c,h=login('director')
 payload={'date':'2027-01-01','direction':'Gasto','category':'Alojamiento','concept':'Factura','counterparty':'Hotel','reference':'F1','amount':12100,'baseAmount':10000,'taxAmount':2100,'taxId':'B12345678','status':'Pendiente'}
 result=c.post('/api/modules/entry',json=payload,headers=h);assert result.status_code==200,result.json;eid=result.json['id']
 im=io.BytesIO();Image.new('RGB',(100,100),'green').save(im,format='JPEG',quality=87);raw=im.getvalue()
 uploaded=c.post('/api/invoices/'+eid,data={'file':(io.BytesIO(raw),'original.jpg')},headers=h);assert uploaded.status_code==200,uploaded.json;fid=uploaded.json['id']
 assert c.get('/api/invoice-file/'+fid).data==raw
 with app.extensions['db_sessions']() as db:
  stored=db.get(Document,fid);assert stored.content!=raw;assert app.extensions['cipher'].decrypt(stored.content)==raw
 for role in ['runner','technician','communication']:
  other,oh=login(role);assert other.get('/api/invoice-file/'+fid).status_code==403
  assert other.get('/api/invoices/'+eid).status_code==403
  assert other.post('/api/invoices/'+eid,data={'file':(io.BytesIO(raw),'x.jpg')},headers=oh).status_code==403
 # Reattaching the same original does not duplicate attachments or create another charge.
 duplicate=c.post('/api/invoices/'+eid,data={'file':(io.BytesIO(raw),'original.jpg')},headers=h);assert duplicate.json['duplicate']
 entries=c.get('/api/modules/entry').json['records'];assert len(entries)==1 and len(entries[0]['attachments'])==1
 assert entries[0]['baseAmount']==10000 and entries[0]['taxId']=='B12345678'

def test_invoice_pdf_download_and_validation(env):
 app,ids,login,_=env;c,h=login('director');r=c.post('/api/modules/entry',json={'direction':'Gasto','amount':500,'concept':'PDF'},headers=h);eid=r.json['id']
 pdf=b'%PDF-1.7\n1 0 obj<</Type/Catalog>>endobj\n%%EOF'
 r=c.post('/api/invoices/'+eid,data={'file':(io.BytesIO(pdf),'factura.pdf')},headers=h);assert r.status_code==200
 response=c.get('/api/invoice-file/'+r.json['id']);assert response.data==pdf and response.mimetype=='application/pdf';assert 'attachment;' in response.headers['Content-Disposition'];assert response.headers['Cache-Control']=='no-store'
 assert c.post('/api/invoices/'+eid,data={'file':(io.BytesIO(b'<html>fake</html>'),'factura.pdf')},headers=h).status_code==400
 assert c.post('/api/invoices/'+eid,data={'file':(io.BytesIO(b'x'*(4*1024*1024+1)),'large.jpg')},headers=h).status_code==400
 assert c.post('/api/invoices/unknown',data={'file':(io.BytesIO(pdf),'file.pdf')},headers=h).status_code==404


def test_import_roster_creates_private_individual_profiles(env):
 from roster_import import import_roster
 app,_,login,_=env
 sessions=app.extensions['db_sessions']
 cipher=app.extensions['cipher']
 payload=json.dumps([
  dict(firstName='Nombre',surname='De Prueba',birthYear='2009',dni='00000000T'),
  dict(firstName='Segundo',surname='De Prueba',birthYear='2010'),
 ])
 receipt=import_roster(sessions,Record,User,cipher,payload)
 assert receipt['added']==receipt['total']==2
 assert import_roster(sessions,Record,User,cipher,payload)==receipt
 director,_=login('director')
 roster=director.get('/api/roster').json['riders']
 riders=[r for r in roster if r['name'].endswith('De Prueba')]
 assert len(riders)==2
 rider=next(r for r in riders if r['name']=='Nombre De Prueba')
 assert set(rider)=={'id','name'}
 path='/api/profile/'+rider['id']
 profile=director.get(path).json['profile']
 assert profile['birthYear']=='2009' and profile['dni']=='00000000T'
 limited,_=login('director_limited')
 assert 'dni' not in limited.get(path).json['profile']
 with sessions() as db:
  user=db.get(User,rider['id'])
  assert user.email is user.password is user.mfa is None
  assert b'00000000T' not in user.profile


def test_hotel_export_and_vehicle_reservations(env):
 from openpyxl import load_workbook
 _,ids,login,_=env
 director,h=login('director')
 runner,rh=login('runner')
 limited,_=login('director_limited')
 def create(name,start):
  assert director.post('/api/events',json={'name':name,'date':start},headers=h).status_code==200
  return next(e['id'] for e in director.get('/api/events').json['events'] if e['name']==name)
 first=create('Primer viaje','2027-03-04')
 second=create('Segundo viaje','2027-03-06')
 first_path='/api/events/'+first
 assert director.post(first_path+'/details',json={'endDate':'2027-03-06'},headers=h).status_code==200
 vehicle=director.post('/api/modules/vehicle',json={'name':'Furgoneta'},headers=h).json['id']
 staff=director.post('/api/modules/staff',json={'name':'Mecánico de prueba'},headers=h).json['id']
 assert director.post('/api/modules/travel',json={'event':first,'vehicles':[vehicle],'staff':[staff]},headers=h).status_code==200
 assert director.post(first_path+'/hotel/staff/'+staff,json={'dni':'12345678Z'},headers=h).status_code==200
 assert '12345678Z' not in director.get('/api/modules/staff').get_data(as_text=True)
 assert limited.get(first_path+'/hotel/guests').status_code==403
 assert director.get(first_path+'/hotel/guests').json['guests']==[
  dict(id=staff,name='Mecánico de prueba',role='Técnico',hasDni=True,photos=0)]
 assert director.post('/api/modules/travel',json={'event':second,'vehicles':[vehicle]},headers=h).status_code==409
 assert director.post('/api/events/'+second+'/details',json={'date':'2027-03-07'},headers=h).status_code==200
 assert director.post('/api/modules/travel',json={'event':second,'vehicles':[vehicle]},headers=h).status_code==200
 assert director.post(first_path+'/details',json={'endDate':'2027-03-07'},headers=h).status_code==409
 assert runner.post('/api/profile/'+ids['runner'],json={'dni':'00000000T','iban':'PRIVATE'},headers=rh).status_code==200
 assert runner.post(first_path+'/availability',json={'status':'Disponible'},headers=rh).status_code==200
 assert director.post(first_path+'/call',json={'users':[ids['runner']]},headers=h).status_code==200
 assert director.get(first_path+'/hotel').status_code==400
 assert director.post(first_path+'/details',json={'callStatus':'Publicada'},headers=h).status_code==200
 response=director.get(first_path+'/hotel')
 assert response.status_code==200
 assert list(load_workbook(io.BytesIO(response.data)).active.values)==[('Nombre y apellidos','DNI'),('runner','00000000T'),('Mecánico de prueba','12345678Z')]
 assert limited.get(first_path+'/hotel').status_code==403
 assert runner.get(first_path+'/hotel').status_code==403


def test_runner_can_upload_identity_and_license_with_other_private_uploads_off(env,monkeypatch):
 app,ids,login,_=env
 runner,headers=login('runner')
 director,_=login('director')
 limited,_=login('director_limited')
 other,_=login('runner2')
 monkeypatch.setenv('PUBLIC_ORIGIN','https://portal.test')
 monkeypatch.setenv('DOCUMENT_UPLOADS_ENABLED','false')
 monkeypatch.setitem(app.config,'TESTING',False)
 path='/api/documents/'+ids['runner']
 headers['Origin']='https://portal.test'
 raw=io.BytesIO()
 Image.new('RGB',(50,50),'blue').save(raw,format='PNG')
 for kind in ('dni','licencia','sepa'):
  result=runner.post(path,data={'kind':kind,'file':(io.BytesIO(raw.getvalue()),'scan.png')},headers=headers)
  assert result.status_code==(503 if kind=='sepa' else 200),result.json
 docs=runner.get(path).json['documents']
 assert {doc['kind'] for doc in docs}=={'dni','licencia'}
 for doc in docs:
  url='/api/file/'+doc['id']
  assert director.get(url).status_code==200
  assert limited.get(url).status_code==403
  assert other.get(url).status_code==403


def test_event_expenses_use_existing_conta_entries_and_permissions(env):
 _,_,login,_=env
 director,headers=login('director')
 runner,_=login('runner')
 for name in ('Carrera A','Carrera B'):
  assert director.post('/api/events',json={'name':name},headers=headers).status_code==200
 ids={event['name']:event['id'] for event in director.get('/api/events').json['events']}
 path='/api/modules/entry'
 def add(event,direction,category):
  response=director.post(path,json={'event':event,'direction':direction,'category':category,'amount':1250},headers=headers)
  assert response.status_code==200,response.json
  return response.json['id']
 expense=add(ids['Carrera A'],'Gasto','Gasolina')
 add(ids['Carrera A'],'Ingreso','Otros')
 add(ids['Carrera B'],'Gasto','Alojamiento')
 add('','Gasto','Supermercado')
 scoped=path+'?event='+ids['Carrera A']
 assert [row['id'] for row in director.get(scoped).json['records']]==[expense]
 assert len(director.get(path).json['records'])==4
 assert runner.get(scoped).status_code==403


def test_expense_budget_assignment_and_totals(env):
 _,_,login,_=env
 director,h=login('director')
 base='/api/modules/'
 part=director.post(base+'budget',json={'category':'Viajes','amount':10000},headers=h).json['id']
 payload={'direction':'Gasto','budget':part,'amount':2500}
 expense=director.post(base+'entry',json=payload,headers=h).json['id']
 assert director.get(base+'entry').json['records'][0]['budgetName']=='Viajes'
 assert director.get(base+'budget').json['records'][0]['spent']==2500
 assert director.post(base+'entry',json={**payload,'budget':'unknown'},headers=h).status_code==400
 assert director.post(base+'entry/'+expense,json={'direction':'Gasto','amount':3000},headers=h).status_code==200
 assert director.get(base+'budget').json['records'][0]['spent']==3000
 assert director.post(base+'entry/'+expense,json={**payload,'status':'Anulado'},headers=h).status_code==200
 assert director.get(base+'budget').json['records'][0]['spent']==0


def test_shop_charge_once_and_license_sides(env,monkeypatch):
 _,ids,login,_=env
 monkeypatch.delenv('RESEND_API_KEY',raising=False)
 director,h=login('director')
 runner,rh=login('runner')
 other,_=login('runner2')
 assert director.post('/api/shop/settings',json={'director':ids['director'],'prices':{'Maillot corto':3200}},headers=h).status_code==200
 payload={'token':'12345678-1234-1234-1234-123456789012','amount':6400,'items':[{'name':'Maillot corto','size':'S','quantity':2}]}
 for _ in range(2):
  response=runner.post('/api/shop/orders',json=payload,headers=rh)
  assert response.status_code==200,response.json
  assert response.json['emailStatus']=='Pendiente'
 assert len(runner.get('/api/modules/charge').json['records'])==1
 assert runner.get('/api/modules/charge').json['records'][0]['amount']==6400
 assert not other.get('/api/shop').json['orders']
 raw=io.BytesIO()
 Image.new('RGB',(30,30),'blue').save(raw,format='PNG')
 for kind in ('licencia','licencia_reverso'):
  assert runner.post('/api/documents/'+ids['runner'],data={'kind':kind,'file':(io.BytesIO(raw.getvalue()),'license.png')},headers=rh).status_code==200
 licenses={row['rider']:row for row in director.get('/api/modules/license').json['records']}
 assert set(licenses[ids['runner']]['photos'])=={'licencia','licencia_reverso'}
 assert licenses[ids['runner2']]['status']=='No aportada'
 assert other.get('/api/file/'+licenses[ids['runner']]['photos']['licencia']).status_code==403


def test_director_downloads_runner_license_as_private_pdf(env):
 from pypdf import PdfReader, PdfWriter

 app,ids,login,_=env
 director,_=login('director')
 limited,_=login('director_limited')
 runner,rh=login('runner')
 path='/api/licenses/'+ids['runner']+'/pdf'
 assert app.test_client().get(path).status_code==401
 assert limited.get(path).status_code==403
 assert runner.get(path).status_code==403
 assert director.get(path).status_code==404
 upload='/api/documents/'+ids['runner']
 image=io.BytesIO()
 Image.new('RGB',(800,500),'navy').save(image,format='JPEG')
 image.seek(0)
 assert runner.post(upload,data={'kind':'licencia','file':(image,'front.jpg')},headers=rh).status_code==200
 front=director.get(path)
 assert front.status_code==200
 assert len(PdfReader(io.BytesIO(front.data)).pages)==1
 pdf=io.BytesIO()
 original=PdfWriter()
 original.add_blank_page(width=350,height=220)
 original.write(pdf)
 pdf.seek(0)
 assert runner.post(upload,data={'kind':'licencia_reverso','file':(pdf,'back.pdf')},headers=rh).status_code==200
 result=director.get(path)
 assert result.status_code==200 and result.mimetype=='application/pdf'
 assert 'attachment; filename="Licencia_runner.pdf"'==result.headers['Content-Disposition']
 assert result.headers['Cache-Control']=='no-store'
 combined=PdfReader(io.BytesIO(result.data))
 assert len(combined.pages)==2
 assert [item.title for item in combined.outline]==['Anverso','Reverso']
 assert combined.pages[1].mediabox.width==350
 assert director.get('/api/licenses/'+ids['runner2']+'/pdf').status_code==404


def test_trip_share_conserves_cents_and_prevents_duplicate_charge(env):
 _,ids,login,_=env
 director,h=login('director')
 assert director.post('/api/events',json={'name':'Viaje'},headers=h).status_code==200
 event=director.get('/api/events').json['events'][0]['id']
 path='/api/events/'+event
 for role in ('runner','runner2'):
  rider,rh=login(role)
  assert rider.post(path+'/availability',json={'status':'Disponible'},headers=rh).status_code==200
 assert director.post(path+'/call',json={'users':[ids['runner'],ids['runner2']]},headers=h).status_code==200
 assert director.post(path+'/details',json={'callStatus':'Publicada'},headers=h).status_code==200
 expense=director.post('/api/modules/entry',json={'event':event,'direction':'Gasto','amount':1001},headers=h).json['id']
 payload={'expenses':[expense]}
 assert director.post(path+'/split-expenses',json=payload,headers=h).status_code==200
 assert director.post(path+'/split-expenses',json=payload,headers=h).status_code==409
 charges=director.get('/api/modules/charge').json['records']
 assert sorted(row['amount'] for row in charges)==[500,501]

def test_linked_expense_charges_the_published_runner_after_confirmation(env):
 _,ids,login,_=env
 director,h=login('director')
 runner,rh=login('runner')
 other,_=login('runner2')
 assert director.post('/api/events',json={'name':'Carrera de prueba'},headers=h).status_code==200
 event=director.get('/api/events').json['events'][0]['id']
 path='/api/events/'+event
 assert runner.post(path+'/availability',json={'status':'Disponible'},headers=rh).status_code==200
 assert director.post(path+'/call',json={'users':[ids['runner']]},headers=h).status_code==200
 expense=director.post('/api/modules/entry',json={'event':event,'direction':'Gasto','amount':2300},headers=h).json['id']
 charges='/api/modules/charge'
 payload={'expenses':[expense],'expectedRiders':[ids['runner']],'expectedTotal':2300}
 assert runner.get(charges).json['records']==[]
 assert director.post(path+'/split-expenses',json=payload,headers=h).status_code==400
 assert director.post(path+'/details',json={'callStatus':'Publicada'},headers=h).status_code==200
 assert director.post(path+'/split-expenses',json={**payload,'expectedRiders':[ids['runner2']]},headers=h).status_code==409
 assert director.post(path+'/split-expenses',json={**payload,'expectedTotal':2299},headers=h).status_code==409
 assert director.post(path+'/split-expenses',json=payload,headers=h).status_code==200
 assert director.post(path+'/split-expenses',json=payload,headers=h).status_code==409
 assert [row['amount'] for row in runner.get(charges).json['records']]==[2300]
 assert other.get(charges).json['records']==[]


def test_roster_registration_links_attach_to_existing_runner(env):
 app,ids,login,_=env
 director,h=login('director')
 limited,lh=login('director_limited')
 with app.extensions['db_sessions'].begin() as db:
  u=db.get(User,ids['runner'])
  u.email=u.password=u.mfa=None
 path='/api/roster/invites'
 payload={'riders':[ids['runner']]}
 assert limited.post(path,json=payload,headers=lh).status_code==403
 old=director.post(path,json=payload,headers=h).json['invitations'][0]['token']
 token=director.post(path,json=payload,headers=h).json['invitations'][0]['token']
 client=app.test_client()
 assert client.post('/api/activate/start',json={'token':old}).status_code==400
 assert client.post('/api/activate/start',json={'token':token}).json['chooseEmail']
 activation={'token':token,'email':'rider@example.test','password':'contraseña de prueba'}
 assert client.post('/api/activate/finish',json=activation).status_code==200
 assert client.post('/api/activate/finish',json=activation).status_code==400
 assert client.post('/api/login',json={k:activation[k] for k in ('email','password')}).status_code==200
 assert client.get('/api/me').json['user']['id']==ids['runner']

def test_direction_can_register_rider_directly(env):
 app,_,login,_=env
 director,h=login('director_limited')
 runner,rh=login('runner')
 path='/api/roster'
 data={'firstName':'Álex','surname':'De Prueba','invite':True}
 assert runner.post(path,json=data,headers=rh).status_code==403
 assert director.post(path,json={'firstName':'Álex'},headers=h).status_code==400
 created=director.post(path,json=data,headers=h)
 assert created.status_code==201,created.json
 rider=created.json['rider']
 assert rider in director.get(path).json['riders']
 duplicate=director.post(path,json={**data,'firstName':'alex','surname':'DE  PRUEBA'},headers=h)
 assert duplicate.status_code==409
 without_invite=director.post(path,json={'firstName':'Otro','surname':'Corredor'},headers=h)
 assert without_invite.status_code==201 and 'invitation' not in without_invite.json
 client=app.test_client()
 token=created.json['invitation']['token']
 assert client.post('/api/activate/start',json={'token':token}).json['chooseEmail']
 credentials={'email':'nuevo@test.invalid','password':'clave-de-prueba'}
 assert client.post('/api/activate/finish',json={**credentials,'token':token}).status_code==200
 assert client.post('/api/login',json=credentials).status_code==200
 assert client.get('/api/me').json['user']['id']==rider['id']
 assert client.get('/api/profile/'+rider['id']).json['profile']=={'firstName':'Álex','surname':'De Prueba'}


def test_club_contract_pdf_is_private_and_downloads_unchanged(env):
 _,ids,login,_=env
 runner,h=login('runner')
 director,_=login('director')
 limited,_=login('director_limited')
 other,_=login('runner2')
 pdf=io.BytesIO()
 Image.new('RGB',(24,24),'white').save(pdf,format='PDF')
 original=pdf.getvalue()
 path='/api/documents/'+ids['runner']
 assert runner.post(path,data={'kind':'contrato_club','file':(io.BytesIO(original),'contrato.pdf')},headers=h).status_code==200
 doc=runner.get(path).json['documents'][0]
 assert doc['kind']=='contrato_club'
 url='/api/file/'+doc['id']
 download=director.get(url)
 assert download.data==original
 assert download.mimetype=='application/pdf'
 assert 'contrato_club.pdf' in download.headers['Content-Disposition']
 assert limited.get(url).status_code==403
 assert other.get(url).status_code==403


def test_shared_direction_allows_three_concurrent_sessions(env):
 from direction_access import seed_direction_account
 app,_,login,_=env
 seed=generate_password_hash('shared-test-password',method='scrypt:32768:8:1')
 sessions=app.extensions['db_sessions']
 cipher=app.extensions['cipher']
 seed_direction_account(sessions,User,Record,cipher,seed)
 seed_direction_account(sessions,User,Record,cipher,generate_password_hash('different-password',method='scrypt:32768:8:1'))
 clients=[app.test_client() for _ in range(3)]
 for client in clients:
  assert client.post('/api/login',json={'email':'DIRECCION','password':'shared-test-password'}).status_code==200
 for client in clients:
  me=client.get('/api/me').json['user']
  assert me['role']=='director' and me['documents'] and not me['owner']
  assert client.get('/api/summary').status_code==200
 assert app.test_client().post('/api/login',json={'email':'direccion','password':'wrong'}).status_code==401
 personal,_=login('director')
 assert personal.get('/api/me').json['user']['owner']


def test_named_rider_accounts_use_real_login_and_existing_profile(env):
 from rider_accounts import provision_rider_accounts,verify_rider_accounts
 app,ids,login,_=env
 payload=json.dumps([dict(name='runner',username='test.rider',password='sample-pass')])
 sessions=app.extensions['db_sessions']
 cipher=app.extensions['cipher']
 result=provision_rider_accounts(sessions,User,Record,Invite,__import__('server').LoginSession,cipher,payload)
 assert result['created']==1 and result['existingAccounts']==1
 receipt=verify_rider_accounts(app,sessions,User,Record,cipher,payload,'https://portal.test')
 assert receipt['verified']==1
 second=provision_rider_accounts(sessions,User,Record,Invite,__import__('server').LoginSession,cipher,payload)
 assert second['verified']==1
 client=app.test_client()
 assert client.post('/api/login',json={'email':'TEST.RIDER','password':'sample-pass'}).status_code==200
 assert client.get('/api/me').json['user']['id']==ids['runner']


def test_private_hotel_pdf_contains_only_trip_guest_images(env):
 import re
 _,ids,login,_=env
 director,h=login('director')
 runner,rh=login('runner')
 other,oh=login('runner2')
 limited,_=login('director_limited')
 director.post('/api/events',json={'name':'Hotel PDF'},headers=h)
 event=director.get('/api/events').json['events'][0]['id']
 path='/api/events/'+event
 runner.post(path+'/availability',json={'status':'Disponible'},headers=rh)
 director.post(path+'/call',json={'users':[ids['runner']]},headers=h)
 director.post(path+'/details',json={'callStatus':'Publicada'},headers=h)
 raw=io.BytesIO()
 Image.new('RGB',(100,70),'blue').save(raw,format='PNG')
 for client,headers,rider in [(runner,rh,ids['runner']),(other,oh,ids['runner2'])]:
  assert client.post('/api/documents/'+rider,data={'kind':'dni','file':(io.BytesIO(raw.getvalue()),'dni.png')},headers=headers).status_code==200
 pdf_image=io.BytesIO()
 Image.new('RGB',(90,60),'green').save(pdf_image,format='PDF')
 assert runner.post('/api/documents/'+ids['runner'],data={'kind':'dni_reverso','file':(io.BytesIO(pdf_image.getvalue()),'dni.pdf')},headers=rh).status_code==200
 staff=director.post('/api/modules/staff',json={'name':'Técnico PDF'},headers=h).json['id']
 director.post('/api/modules/travel',json={'event':event,'staff':[staff]},headers=h)
 upload=path+'/hotel/staff/'+staff+'/photo'
 assert director.post(upload,data={'side':'front','file':(io.BytesIO(raw.getvalue()),'front.png')},headers=h).status_code==200
 assert limited.get(path+'/hotel/identity-pdf').status_code==403
 assert runner.get(path+'/hotel/identity-pdf').status_code==403
 pdf=director.get(path+'/hotel/identity-pdf')
 assert pdf.status_code==200
 assert pdf.data.startswith(b'%PDF-')
 from pypdf import PdfReader
 assert len(PdfReader(io.BytesIO(pdf.data)).pages)==4
 assert pdf.headers['Cache-Control']=='no-store'
 files=director.get(path+'/hotel/identity-files').json['guests']
 selected=next(guest for guest in files if guest['id']==ids['runner'])
 assert len(selected['files'])==2
 image_file=next(file for file in selected['files'] if file['format']=='PNG')
 assert director.get('/api/file/'+image_file['id']).data==raw.getvalue()
 assert all(guest['id']!=ids['runner2'] for guest in files)
 assert runner.get(path+'/hotel/identity-files').status_code==403



def test_resource_availability_restricts_assignments(env):
 _,_,login,_=env
 director,h=login('director')
 runner,rh=login('runner')
 director.post('/api/events',json={'name':'Matriz','date':'2027-03-01'},headers=h)
 event=director.get('/api/events').json['events'][0]['id']
 vehicle=director.post('/api/modules/vehicle',json={'name':'Furgo'},headers=h).json['id']
 payload={'event':event,'resource':vehicle,'status':'No disponible'}
 assert runner.post('/api/resource-availability',json=payload,headers=rh).status_code==403
 assert director.post('/api/resource-availability',json=payload,headers=h).status_code==200
 assert director.post('/api/modules/travel',json={'event':event,'vehicles':[vehicle]},headers=h).status_code==409
 assert director.post('/api/resource-availability',json={**payload,'status':'Disponible'},headers=h).status_code==200
 assert director.post('/api/modules/travel',json={'event':event,'vehicles':[vehicle]},headers=h).status_code==200
 assert director.post('/api/resource-availability',json=payload,headers=h).status_code==409


def test_rider_health_details_are_private(env):
 _,ids,login,_=env
 runner,h=login('runner')
 director,_=login('director')
 limited,lh=login('director_limited')
 path='/api/profile/'+ids['runner']
 data={'medicationStatus':'Sí','medicationDetails':'Ejemplo privado',
       'allergiesStatus':'No','allergiesDetails':'',
       'intolerancesStatus':'Sí','intolerancesDetails':'Ejemplo intolerancia'}
 assert runner.post(path,json=data,headers=h).status_code==200
 assert all(director.get(path).json['profile'][key]==value for key,value in data.items())
 assert not set(data).intersection(limited.get(path).json['profile'])
 assert limited.post(path,json=data,headers=lh).status_code==403
 assert runner.post(path,json={'medicationStatus':'Otro'},headers=h).status_code==400


def test_invoice_presentation_exports_match_expenses_and_attachments(env,tmp_path):
 from openpyxl import load_workbook
 from pypdf import PdfReader
 _,_,login,_=env
 director,h=login('director')
 rider,_=login('runner')
 base='/api/modules/entry'
 entry=director.post(base,json={'direction':'Gasto','date':'2027-03-02','amount':7743,'baseAmount':7039,
   'taxAmount':704,'counterparty':'Hotel de prueba','reference':'TEST-1'},headers=h).json['id']
 director.post(base,json={'direction':'Gasto','date':'2027-03-03','amount':1200},headers=h)
 director.post(base,json={'direction':'Ingreso','date':'2027-03-03','amount':99999},headers=h)
 director.post(base,json={'direction':'Gasto','date':'2027-04-01','amount':400},headers=h)
 scan=io.BytesIO()
 Image.new('RGB',(250,450),'white').save(scan,format='PNG')
 assert director.post('/api/invoices/'+entry,data={'file':(io.BytesIO(scan.getvalue()),'scan.png')},headers=h).status_code==200
 source=io.BytesIO()
 Image.new('RGB',(180,260),'blue').save(source,format='PDF')
 assert director.post('/api/invoices/'+entry,data={'file':(io.BytesIO(source.getvalue()),'scan.pdf')},headers=h).status_code==200
 period='?from=2027-03-01&to=2027-03-31'
 xlsx='/api/invoices/report.xlsx'+period
 pdf='/api/invoices/report.pdf'+period
 assert rider.get(xlsx).status_code==403
 assert rider.get(pdf).status_code==403
 excel=director.get(xlsx)
 sheet=load_workbook(io.BytesIO(excel.data)).active
 assert sheet['A2'].value=='G-'+entry[:12].upper()
 assert sheet['L2'].value==77.43
 assert sheet['N2'].value==2
 assert sheet['N3'].value=='Sin adjuntar'
 assert sheet['L4'].value=='=SUM(L2:L3)'
 response=director.get(pdf)
 assert response.status_code==200
 assert response.headers['Cache-Control']=='no-store'
 assert len(PdfReader(io.BytesIO(response.data)).pages)==2
 (tmp_path/'facturas-prueba.pdf').write_bytes(response.data)


def test_bank_xlsx_preview_and_expense_reconciliation(env):
 from openpyxl import Workbook
 _,_,login,_=env
 director,h=login('director')
 runner,rh=login('runner')
 book=Workbook()
 sheet=book.active
 sheet.append(['Extracto de prueba'])
 sheet.append(['Fecha operación','Descripción','Debe','Haber','Referencia'])
 sheet.append(['02/03/2027','Hotel','77,43',None,'HOTEL-1'])
 sheet.append(['03/03/2027','Gasolina','40,00',None,'GAS-1'])
 sheet.append(['04/03/2027','Ingreso',None,'100,00','IN-1'])
 file=io.BytesIO()
 book.save(file)
 preview=director.post('/api/bank/preview',data={'file':(io.BytesIO(file.getvalue()),'extracto.xlsx')},headers=h)
 assert preview.status_code==200,preview.json
 rows=preview.json['rows']
 assert [(row['amount'],row['direction']) for row in rows]==[(7743,'Gasto'),(4000,'Gasto'),(10000,'Ingreso')]
 assert director.post('/api/bank/import',json={'rows':rows},headers=h).json['imported']==3
 expense=director.post('/api/modules/entry',json={'direction':'Gasto','amount':7743,'counterparty':'Hotel'},headers=h).json['id']
 scan=io.BytesIO()
 Image.new('RGB',(20,20),'white').save(scan,format='PNG')
 assert director.post('/api/invoices/'+expense,data={'file':(io.BytesIO(scan.getvalue()),'factura.png')},headers=h).status_code==200
 endpoint='/api/bank/reconciliation'
 assert runner.get(endpoint).status_code==403
 movements={row['reference']:row for row in director.get(endpoint).json['movements']}
 assert set(movements)=={'HOTEL-1','GAS-1'}
 assert movements['HOTEL-1']['state']=='Coincidencia única'
 assert movements['GAS-1']['state']=='Sin factura'
 assert director.post(endpoint+'/'+movements['GAS-1']['id'],json={'invoice':expense},headers=h).status_code==400
 assert director.post(endpoint+'/'+movements['HOTEL-1']['id'],json={'invoice':expense},headers=h).status_code==200
 assert director.post('/api/bank/import',json={'rows':rows},headers=h).json['imported']==0
 assert any(row['state']=='Conciliado' for row in director.get(endpoint).json['movements'])
