"""Private team portal. No legacy demo credentials or public data imports."""
import os, io, json, hashlib, secrets, time, datetime, logging
from functools import wraps
from flask import Flask, request, jsonify, g, send_file, render_template, abort
from sqlalchemy import text as sql_text, create_engine, Column, String, Integer, Boolean, LargeBinary, Text, ForeignKey, select, func, delete, update
from sqlalchemy.orm import declarative_base, sessionmaker
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
import pyotp
from openpyxl import Workbook
from PIL import Image

Base=declarative_base()
def uid(): return secrets.token_hex(16)
def digest(v): return hashlib.sha256(v.encode()).hexdigest()
class User(Base):
    __tablename__='users'
    id=Column(String,primary_key=True,default=uid); email=Column(String,unique=True,nullable=False); name=Column(String,nullable=False)
    role=Column(String,nullable=False); password=Column(Text,nullable=False); mfa=Column(LargeBinary,nullable=False); last_step=Column(Integer,default=-1)
    active=Column(Boolean,default=True); documents=Column(Boolean,default=False); owner=Column(Boolean,default=False)
    profile=Column(LargeBinary,nullable=False)
class LoginSession(Base):
    __tablename__='sessions'
    id=Column(String,primary_key=True); user_id=Column(String,ForeignKey('users.id')); csrf=Column(String); expires=Column(Integer); seen=Column(Integer)
class Invite(Base):
    __tablename__='invites'
    token=Column(String,primary_key=True); email=Column(String,nullable=False); name=Column(String,nullable=False); role=Column(String,nullable=False)
    documents=Column(Boolean,default=False); secret=Column(LargeBinary,nullable=False); expires=Column(Integer); used=Column(Boolean,default=False)
    reset_user=Column(String,nullable=True); owner=Column(Boolean,default=False)
class Record(Base):
    __tablename__='records'
    id=Column(String,primary_key=True,default=uid); kind=Column(String,index=True); owner_id=Column(String,index=True); data=Column(LargeBinary,nullable=False)
class Document(Base):
    __tablename__='documents'
    id=Column(String,primary_key=True,default=uid); owner_id=Column(String,ForeignKey('users.id')); kind=Column(String); size=Column(Integer); mime=Column(String)
    created=Column(Integer); content=Column(LargeBinary,nullable=False)
class Audit(Base):
    __tablename__='audit'
    id=Column(String,primary_key=True,default=uid); user_id=Column(String); action=Column(String); target=Column(String); at=Column(Integer)
class Attempt(Base):
    __tablename__='attempts'
    id=Column(String,primary_key=True); count=Column(Integer,default=0); until=Column(Integer)

ROLES={'director','technician','runner','communication'}
FINE_TYPES=[('Falta de respeto leve',5),('Falta de respeto moderada',10),('Falta de respeto grave','Expulsión'),('Material en mal estado',5),('Llega 5 minutos tarde',5),('Llega 10 minutos tarde',10),('Llega 15 minutos tarde',15),('No trae ropa adecuada',5),('Otras · 5 €',5),('Otras · 10 €',10)]
CLOTHES=['Maillot corto','Maillot largo','Culote corto','Culote largo','Gava','Buzo','Pantalón largo','Pantalón corto','Camiseta','Polo','Sudadera','Plumas']
PRIVATE_TYPES={'dni','sepa','licencia','autorizacion'}
PHOTO_TYPES={'portrait','action'}

def create_app(test_config=None):
    app=Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=9*1024*1024,TESTING=False)
    if test_config: app.config.update(test_config)
    key=app.config.get('ENCRYPTION_KEY') or os.environ.get('ENCRYPTION_KEY')
    if not key: raise RuntimeError('ENCRYPTION_KEY required')
    cipher=Fernet(key)
    dburl=app.config.get('DATABASE_URL') or os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
    if not dburl: raise RuntimeError('DATABASE_URL required')
    if dburl.startswith('postgres://'): dburl=dburl.replace('postgres://','postgresql+psycopg://',1)
    elif dburl.startswith('postgresql://'): dburl=dburl.replace('postgresql://','postgresql+psycopg://',1)
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    parts=urlsplit(dburl)
    dburl=urlunsplit(parts._replace(query=urlencode([(k,v) for k,v in parse_qsl(parts.query) if k not in ('pgbouncer','connection_limit')])))
    engine=create_engine(dburl,pool_pre_ping=True,**({'connect_args':{'check_same_thread':False}} if dburl.startswith('sqlite') else {'pool_size':1,'max_overflow':1,'connect_args':{'prepare_threshold':None}}))
    if not dburl.startswith('sqlite'):
        try:
            with engine.begin() as connection:connection.execute(sql_text('CREATE SCHEMA IF NOT EXISTS mbb_private'))
        except Exception as exc:
            import re
            detail=str(getattr(exc,'orig',type(exc).__name__))
            detail=re.sub(r'postgres(?:ql)?://\S+', '[connection]', detail)
            print('DB_START_ERROR: '+detail[:700],flush=True)
            raise
        engine=engine.execution_options(schema_translate_map={None:'mbb_private'})
    Base.metadata.create_all(engine); Sessions=sessionmaker(bind=engine,expire_on_commit=False)
    app.extensions['db_sessions']=Sessions; app.extensions['cipher']=cipher
    dummy_password=generate_password_hash(secrets.token_urlsafe(32),method='scrypt:32768:8:1')
    def seal(v): return cipher.encrypt(json.dumps(v,ensure_ascii=False).encode())
    def unseal(v): return json.loads(cipher.decrypt(v))
    def audit(action,target=''): g.db.add(Audit(user_id=getattr(g,'user',None).id if getattr(g,'user',None) else None,action=action,target=target,at=int(time.time())))
    def body():
        d=request.get_json(silent=True)
        if not isinstance(d,dict): abort(400,'Datos no válidos')
        return d
    def text(d,k,maxlen=200):
        v=d.get(k,'')
        if not isinstance(v,str) or len(v)>maxlen: abort(400,'Campo no válido: '+k)
        return v.strip()
    def require(*roles):
        def dec(fn):
            @wraps(fn)
            def inner(*a,**kw):
                if not g.user: abort(401,'Inicia sesión')
                if roles and g.user.role not in roles: abort(403,'Sin permiso')
                return fn(*a,**kw)
            return inner
        return dec
    def runner_target(target):
        u=g.db.get(User,target)
        if not u or u.role!='runner': abort(404)
        if g.user.id!=target and g.user.role!='director': abort(403)
        return u
    def throttle(label,limit=8):
        now=int(time.time()); name=digest(label)
        # Lock one counter across workers. No raw identifiers are kept in throttle keys.
        a=g.db.execute(select(Attempt).where(Attempt.id==name).with_for_update()).scalar_one_or_none()
        if not a: a=Attempt(id=name,count=0,until=now+900);g.db.add(a)
        if a.until<=now:a.count=0;a.until=now+900
        if a.count>=limit: abort(429,'Demasiados intentos. Espera 15 minutos.')
        a.count+=1;g.db.commit()
    def mfa_check(u,code):
        if not code.isdigit() or len(code)!=6:return False
        step=int(time.time())//30
        secret=unseal(u.mfa)
        for current in [step,step-1,step+1]:
            if current>u.last_step and secrets.compare_digest(pyotp.TOTP(secret).at(current*30),code):
                u.last_step=current;return True
        return False
    @app.before_request
    def before():
        g.db=Sessions();g.user=None;g.login=None
        if request.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
            expected=os.environ.get('PUBLIC_ORIGIN')
            if not app.testing:
                origin=request.headers.get('Origin','')
                if not expected or origin!=expected:abort(403,'Origen no permitido')
        token=request.cookies.get('__Host-mbb')
        if token:
            row=g.db.get(LoginSession,digest(token));now=int(time.time())
            if row and row.expires>now and row.seen>now-1800:
                u=g.db.get(User,row.user_id)
                if u and u.active:g.user=u;g.login=row;row.seen=now
        if request.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS') and g.login:
            if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),g.login.csrf):abort(403,'Recarga la sesión')
    @app.after_request
    def after(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        if not app.testing:response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        if hasattr(g,'db'):
            if response.status_code<400:g.db.commit()
            else:g.db.rollback()
        return response
    @app.teardown_request
    def close(exc):
        if hasattr(g,'db'):g.db.close()
    @app.errorhandler(HTTPException)
    def http_error(e):return jsonify(error=e.description),e.code
    @app.errorhandler(Exception)
    def error(e):
        app.logger.error('request failed: %s',type(e).__name__)
        return jsonify(error='No se pudo completar la operación'),500
    @app.get('/health')
    def health():g.db.execute(select(1));return jsonify(status='ok')
    @app.get('/')
    def index():return render_template('index.html')
    @app.get('/api/me')
    def me():
        if not g.user:return jsonify(user=None)
        return jsonify(user={'id':g.user.id,'name':g.user.name,'email':g.user.email,'role':g.user.role,'documents':g.user.documents,'owner':g.user.owner},csrf=g.login.csrf,clothes=CLOTHES,fines=FINE_TYPES)
    @app.post('/api/login')
    def login():
        d=body();email=text(d,'email',254).lower();password=text(d,'password',256);code=text(d,'code',10)
        throttle('login:'+email);throttle('ip:'+request.remote_addr,40)
        u=g.db.execute(select(User).where(User.email==email).with_for_update()).scalar_one_or_none()
        valid=check_password_hash(u.password if u else dummy_password,password)
        if not u or not u.active or not valid or not mfa_check(u,code):audit('login_failed');g.db.commit();abort(401,'Credenciales o código incorrectos')
        token=secrets.token_urlsafe(40);now=int(time.time());g.db.add(LoginSession(id=digest(token),user_id=u.id,csrf=secrets.token_urlsafe(32),expires=now+8*3600,seen=now))
        g.user=u;audit('login',u.id);response=jsonify(ok=True)
        response.set_cookie('__Host-mbb',token,secure=True,httponly=True,samesite='Strict',path='/',max_age=8*3600)
        return response
    @app.post('/api/logout')
    @require()
    def logout():
        g.db.delete(g.login);audit('logout');r=jsonify(ok=True);r.delete_cookie('__Host-mbb',secure=True,httponly=True,samesite='Strict');return r
    def get_invite(token):
        invite=g.db.execute(select(Invite).where(Invite.token==digest(token)).with_for_update()).scalar_one_or_none()
        if not invite or invite.used or invite.expires<int(time.time()):abort(400,'Enlace caducado o ya utilizado')
        return invite
    @app.post('/api/activate/start')
    def activate_start():
        d=body();token=text(d,'token',120);throttle('activation:'+request.remote_addr,30)
        bootstrap=os.environ.get('BOOTSTRAP_TOKEN_HASH','')
        if bootstrap and secrets.compare_digest(digest(token),bootstrap):
            # Transactional singleton lock, also prevents concurrent bootstrap administrators.
            if not g.db.get(Invite,bootstrap):
                if g.db.scalar(select(func.count()).select_from(User)):abort(400,'Administración ya activada')
                g.db.add(Invite(token=bootstrap,email=os.environ['ADMIN_EMAIL'].lower(),name='Alex Álvarez',role='director',documents=True,owner=True,secret=seal(pyotp.random_base32()),expires=int(os.environ['BOOTSTRAP_EXPIRES'])))
                g.db.flush()
        i=get_invite(token)
        secret=unseal(i.secret)
        return jsonify(email=i.email,name=i.name,role=i.role,secret=secret,uri=pyotp.TOTP(secret).provisioning_uri(i.email,issuer_name='Miribilla Ecotisa'))
    @app.post('/api/activate/finish')
    def activate_finish():
        d=body();throttle('finish:'+request.remote_addr,20);i=get_invite(text(d,'token',120))
        password=text(d,'password',256);code=text(d,'code',10)
        if len(password)<14:abort(400,'La contraseña debe tener al menos 14 caracteres')
        if not pyotp.TOTP(unseal(i.secret)).verify(code,valid_window=1):abort(400,'Código de autenticación incorrecto')
        u=g.db.get(User,i.reset_user) if i.reset_user else None
        if i.reset_user and (not u or not u.active):abort(400)
        if u:
            u.password=generate_password_hash(password,method='scrypt:32768:8:1');u.mfa=i.secret;u.last_step=int(time.time())//30
            g.db.execute(delete(LoginSession).where(LoginSession.user_id==u.id))
        else:
            if g.db.scalar(select(User.id).where(User.email==i.email)):abort(409,'Usuario existente')
            u=User(email=i.email,name=i.name,role=i.role,password=generate_password_hash(password,method='scrypt:32768:8:1'),mfa=i.secret,last_step=int(time.time())//30,documents=i.documents,owner=i.owner,profile=seal({}))
            g.db.add(u);g.db.flush()
        g.db.execute(update(Invite).where(Invite.email==i.email,Invite.used==False).values(used=True));i.used=True;audit('account_activated',u.id);return jsonify(ok=True)
    @app.get('/api/users')
    @require('director')
    def users():return jsonify(users=[{'id':u.id,'name':u.name,'email':u.email,'role':u.role,'active':u.active,'documents':u.documents,'owner':u.owner} for u in g.db.scalars(select(User).order_by(User.name))])
    @app.post('/api/invites')
    @require('director')
    def invite():
        if not g.user.owner:abort(403,'Solo la dirección responsable puede dar altas')
        d=body();email=text(d,'email',254).lower();name=text(d,'name',100);role=text(d,'role',20)
        if not name or '@' not in email or role not in ROLES:abort(400,'Revisa nombre, correo y perfil')
        if g.db.scalar(select(User.id).where(User.email==email)):abort(409,'Ese usuario ya existe')
        g.db.execute(delete(Invite).where(Invite.email==email,Invite.used==False))
        token=secrets.token_urlsafe(40);i=Invite(token=digest(token),email=email,name=name,role=role,documents=role=='director' and d.get('documents') is True,owner=False,secret=seal(pyotp.random_base32()),expires=int(time.time())+48*3600);g.db.add(i);audit('invite_created',email)
        return jsonify(token=token,expires=i.expires)
    @app.post('/api/users/<target>/disable')
    @require('director')
    def disable(target):
        if not g.user.owner or target==g.user.id:abort(403)
        u=g.db.get(User,target)
        if not u or u.owner:abort(403)
        u.active=False;g.db.execute(delete(LoginSession).where(LoginSession.user_id==target));audit('user_disabled',target);return jsonify(ok=True)
    @app.post('/api/users/<target>/reset')
    @require('director')
    def reset(target):
        if not g.user.owner:abort(403)
        u=g.db.get(User,target)
        if not u or not u.active:abort(404)
        g.db.execute(update(Invite).where(Invite.email==u.email,Invite.used==False).values(used=True));token=secrets.token_urlsafe(40);g.db.add(Invite(token=digest(token),email=u.email,name=u.name,role=u.role,documents=u.documents,reset_user=u.id,secret=seal(pyotp.random_base32()),expires=int(time.time())+3600));g.db.execute(delete(LoginSession).where(LoginSession.user_id==target));audit('reset_created',target);return jsonify(token=token)
    @app.get('/api/profile/<target>')
    @require('director','runner')
    def profile(target):
        u=runner_target(target);p=unseal(u.profile)
        if g.user.id!=target and not g.user.documents:p={k:v for k,v in p.items() if k in ('sizes','quantities','coach','club','photoConsent')}
        audit('profile_read',target);return jsonify(profile=p)
    @app.post('/api/profile/<target>')
    @require('director','runner')
    def profile_save(target):
        u=runner_target(target);d=body();p=unseal(u.profile)
        allowed={'coach','club','sizes','photoConsent'}
        if g.user.id==target or g.user.documents:allowed|={'phone','address','birth','guardian','guardianPhone','iban','bankHolder'}
        if g.user.role=='director':allowed|={'quantities'}
        for k,v in d.items():
            if k not in allowed:abort(403)
            if k in ('sizes','quantities'):
                if not isinstance(v,dict) or any(key not in CLOTHES for key in v):abort(400)
                if k=='sizes' and any(val not in ['','XXS','XS','S','M','L','XL','XXL','XXXL'] for val in v.values()):abort(400)
                if k=='quantities' and any(type(val)!=int or val<0 or val>100 for val in v.values()):abort(400)
            elif k=='photoConsent':
                if type(v)!=bool:abort(400)
            elif not isinstance(v,str) or len(v)>250:abort(400)
            p[k]=v
        u.profile=seal(p);audit('profile_updated',target);return jsonify(ok=True)
    @app.get('/api/documents/<target>')
    @require('director','runner','communication')
    def documents(target):
        u=g.db.get(User,target)
        if not u or u.role!='runner':abort(404)
        private=(g.user.id==target or (g.user.role=='director' and g.user.documents))
        photos=(g.user.role in ('director','communication') and unseal(u.profile).get('photoConsent')) or g.user.id==target
        return jsonify(documents=[{'id':d.id,'kind':d.kind,'size':d.size,'created':d.created} for d in g.db.scalars(select(Document).where(Document.owner_id==target)) if (d.kind in PRIVATE_TYPES and private) or (d.kind in PHOTO_TYPES and photos)])
    @app.post('/api/documents/<target>')
    @require('director','runner')
    def upload(target):
        runner_target(target)
        if not app.testing and os.environ.get('DOCUMENT_UPLOADS_ENABLED')!='true':abort(503,'Carga documental pendiente de activación por Dirección')
        if g.user.id!=target and not g.user.documents:abort(403)
        kind=request.form.get('kind');f=request.files.get('file')
        if kind not in PRIVATE_TYPES|PHOTO_TYPES or not f:abort(400)
        raw=f.read(8*1024*1024+1)
        if not raw or len(raw)>8*1024*1024:abort(400,'Máximo 8 MB por archivo')
        if kind in PRIVATE_TYPES:
            # Image-only first release: decoded and re-encoded, no executable PDF content.
            if not (raw.startswith(b'\xff\xd8\xff') or raw.startswith(b'\x89PNG\r\n\x1a\n')):abort(400,'Usa una imagen JPG o PNG. PDF aún no está habilitado.')
        try:
            Image.MAX_IMAGE_PIXELS=20_000_000
            im=Image.open(io.BytesIO(raw));im.load()
            if im.width*im.height>20_000_000:abort(400)
            out=io.BytesIO();im.convert('RGB').save(out,format='JPEG',quality=90);raw=out.getvalue()
        except HTTPException:raise
        except Exception:abort(400,'Imagen no válida')
        total=g.db.scalar(select(func.coalesce(func.sum(Document.size),0)))
        if total+len(raw)>400*1024*1024:abort(400,'Almacenamiento completo. Contacta con Dirección.')
        d=Document(owner_id=target,kind=kind,size=len(raw),mime='image/jpeg',created=int(time.time()),content=cipher.encrypt(raw));g.db.add(d);g.db.flush();audit('document_uploaded',d.id);return jsonify(ok=True)
    @app.get('/api/file/<file_id>')
    @require()
    def file(file_id):
        d=g.db.get(Document,file_id)
        if not d:abort(404)
        u=g.db.get(User,d.owner_id)
        allowed=g.user.id==d.owner_id or (g.user.role=='director' and (g.user.documents or d.kind in PHOTO_TYPES))
        if d.kind in PHOTO_TYPES and g.user.role=='communication':allowed=bool(unseal(u.profile).get('photoConsent'))
        if not allowed:abort(403)
        audit('document_downloaded',d.id)
        return send_file(io.BytesIO(cipher.decrypt(d.content)),mimetype=d.mime,as_attachment=True,download_name=d.kind+'.jpg')
    @app.post('/api/file/<file_id>/delete')
    @require('director','runner')
    def delete_file(file_id):
        d=g.db.get(Document,file_id)
        if not d:abort(404)
        if d.owner_id!=g.user.id and not(g.user.role=='director' and g.user.documents):abort(403)
        g.db.delete(d);audit('document_deleted',file_id);return jsonify(ok=True)
    @app.get('/api/events')
    @require()
    def events():
        rows=[]
        for r in g.db.scalars(select(Record).where(Record.kind=='event')):
            data=unseal(r.data);responses=list(g.db.scalars(select(Record).where(Record.kind=='availability',Record.owner_id==r.id)))
            available={unseal(x.data)['user']:unseal(x.data)['status'] for x in responses}
            data.update(id=r.id,myStatus=available.get(g.user.id,'Por confirmar'))
            if g.user.role=='director':data['responses']=available
            rows.append(data)
        return jsonify(events=rows)
    @app.post('/api/events')
    @require('director')
    def new_event():
        d=body();name=text(d,'name',150);date=text(d,'date',10);place=text(d,'place',150)
        if not name:abort(400,'Indica el nombre')
        if date:
            try:datetime.date.fromisoformat(date)
            except ValueError:abort(400)
        r=Record(kind='event',owner_id=g.user.id,data=seal(dict(name=name,date=date,place=place,called=[])));g.db.add(r);audit('event_created');return jsonify(ok=True)
    @app.post('/api/events/<event_id>/availability')
    @require('runner','technician')
    def availability(event_id):
        event=g.db.get(Record,event_id)
        if not event or event.kind!='event':abort(404)
        d=body();status=text(d,'status',30)
        if status not in ['Por confirmar','Disponible','No disponible']:abort(400)
        key=digest(event_id+':'+g.user.id);r=g.db.get(Record,key)
        data=seal({'user':g.user.id,'status':status})
        if r:r.data=data
        else:g.db.add(Record(id=key,kind='availability',owner_id=event_id,data=data))
        audit('availability_updated',event_id);return jsonify(ok=True)
    @app.post('/api/events/<event_id>/call')
    @require('director')
    def call(event_id):
        r=g.db.get(Record,event_id)
        if not r or r.kind!='event':abort(404)
        ids=body().get('users')
        if not isinstance(ids,list) or len(ids)>100:abort(400)
        for target in ids:
            u=g.db.get(User,target);a=g.db.get(Record,digest(event_id+':'+target))
            if not u or not u.active or u.role!='runner' or not a or unseal(a.data)['status']!='Disponible':abort(400,'Solo corredores disponibles')
        data=unseal(r.data);data['called']=list(dict.fromkeys(ids));r.data=seal(data);audit('call_updated',event_id);return jsonify(ok=True)
    @app.get('/api/roster')
    @require()
    def roster():
        # Never serialize ORM users: sensitive columns are deliberately excluded.
        return jsonify(riders=[{'id':u.id,'name':u.name} for u in g.db.scalars(select(User).where(User.role=='runner',User.active==True).order_by(User.name))] if g.user.role in ('director','communication','technician') else [{'id':g.user.id,'name':g.user.name}])
    @app.get('/api/clothes')
    @require('director')
    def clothes():return jsonify(riders=[{'id':u.id,'name':u.name,'sizes':unseal(u.profile).get('sizes',{}),'quantities':unseal(u.profile).get('quantities',{})} for u in g.db.scalars(select(User).where(User.role=='runner',User.active==True))])
    @app.get('/api/clothes/export')
    @require('director')
    def export():
        wb=Workbook();ws=wb.active;ws.title='Por corredor';ws.append(['Corredor','Prenda','Talla','Cantidad']);total={}
        def safe(v):return "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v
        for u in g.db.scalars(select(User).where(User.role=='runner',User.active==True)):
            p=unseal(u.profile)
            for item,qty in p.get('quantities',{}).items():
                if qty>0:
                    size=p.get('sizes',{}).get(item,'Sin indicar');ws.append([safe(u.name),item,size,qty]);total[(item,size)]=total.get((item,size),0)+qty
        ws=wb.create_sheet('Resumen proveedor');ws.append(['Prenda','Talla','Cantidad'])
        for (item,size),qty in sorted(total.items()):ws.append([item,size,qty])
        for sheet in wb:
            sheet.freeze_panes='A2'
            for col in sheet.columns:sheet.column_dimensions[col[0].column_letter].width=25
        stream=io.BytesIO();wb.save(stream);stream.seek(0);audit('clothes_exported');return send_file(stream,as_attachment=True,download_name='Pedido_ropa_Miribilla_Ecotisa.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    @app.get('/api/fines')
    @require('director','runner')
    def fines():
        q=select(Record).where(Record.kind=='fine')
        if g.user.role=='runner':q=q.where(Record.owner_id==g.user.id)
        return jsonify(fines=[dict(unseal(r.data),id=r.id,user=r.owner_id) for r in g.db.scalars(q)])
    @app.post('/api/fines')
    @require('director')
    def new_fine():
        d=body();target=text(d,'user',40);runner_target(target);kind=d.get('type');note=text(d,'note',300)
        if type(kind)!=int or not 0<=kind<len(FINE_TYPES):abort(400)
        reason,amount=FINE_TYPES[kind]
        g.db.add(Record(kind='fine',owner_id=target,data=seal(dict(reason=reason,amount=amount,note=note,date=datetime.date.today().isoformat(),status='Pendiente de decisión' if isinstance(amount,str) else 'Pendiente'))));audit('fine_recorded',target);return jsonify(ok=True)
    @app.get('/api/audit')
    @require('director')
    def audits():
        if not g.user.owner:abort(403)
        return jsonify(entries=[{'user':r.user_id,'action':r.action,'target':r.target,'at':r.at} for r in g.db.scalars(select(Audit).order_by(Audit.at.desc()).limit(100))])
    return app

if __name__=='__main__':
    create_app().run(host='127.0.0.1',port=5000)
