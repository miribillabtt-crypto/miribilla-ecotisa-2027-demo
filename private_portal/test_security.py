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

def test_mfa_replay_rejected(env):
 app,_,login,ss=env;login('runner');c=app.test_client()
 assert c.post('/api/login',json={'email':'runner@test.invalid','password':'un-password-seguro-de-prueba','code':pyotp.TOTP(ss['runner']).now()}).status_code==401

def test_invite_single_use_and_no_role_escalation(env):
 app,_,login,_=env;c,h=login('director');r=c.post('/api/invites',json={'name':'New Runner','email':'new@test.invalid','role':'runner','documents':True},headers=h);assert r.status_code==200
 token=r.json['token'];a=app.test_client();setup=a.post('/api/activate/start',json={'token':token});assert setup.status_code==200
 params={'token':token,'password':'new-user-password-12345','code':pyotp.TOTP(setup.json['secret']).now(),'role':'director'}
 assert a.post('/api/activate/finish',json=params).status_code==200
 assert a.post('/api/activate/finish',json=params).status_code==400
 with app.extensions['db_sessions']() as db:
  u=db.scalar(select(User).where(User.email=='new@test.invalid'));assert u.role=='runner' and not u.documents

def test_clothes_export_only_registered_quantities(env):
 _,ids,login,_=env;c,h=login('director')
 r=c.post('/api/profile/'+ids['runner'],json={'sizes':{'Maillot corto':'S'},'quantities':{'Maillot corto':2}},headers=h);assert r.status_code==200
 from openpyxl import load_workbook
 wb=load_workbook(io.BytesIO(c.get('/api/clothes/export').data));assert list(wb['Resumen proveedor'].values)==[('Prenda','Talla','Cantidad'),('Maillot corto','S',2)]

def test_call_requires_available_runner(env):
 app,ids,login,_=env;c,h=login('director');assert c.post('/api/events',json={'name':'Carrera','date':'2027-02-01','place':'Bilbao'},headers=h).status_code==200
 eid=c.get('/api/events').json['events'][0]['id'];assert c.post('/api/events/'+eid+'/call',json={'users':[ids['runner']]},headers=h).status_code==400
 r,rh=login('runner');assert r.post('/api/events/'+eid+'/availability',json={'status':'Disponible'},headers=rh).status_code==200
 assert c.post('/api/events/'+eid+'/call',json={'users':[ids['runner']]},headers=h).status_code==200

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
