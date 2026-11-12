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
from roster_import import normalize
from team_scope import NETKOM, OCCIDENT, TEAMS, NEW_TEAMS, configure_team_scope
from roster_import import OCCIDENT_CATEGORIES, import_roster

Base=declarative_base()
def uid(): return secrets.token_hex(16)
def digest(v): return hashlib.sha256(v.encode()).hexdigest()
class User(Base):
    team=Column(String,nullable=False,default=NETKOM,server_default=NETKOM)
    __tablename__='users'
    id=Column(String,primary_key=True,default=uid); email=Column(String,unique=True,nullable=True); name=Column(String,nullable=False)
    role=Column(String,nullable=False); password=Column(Text,nullable=True); mfa=Column(LargeBinary,nullable=True); last_step=Column(Integer,default=-1)
    active=Column(Boolean,default=True); documents=Column(Boolean,default=False); owner=Column(Boolean,default=False)
    profile=Column(LargeBinary,nullable=False)
class LoginSession(Base):
    team=Column(String,nullable=False,default=NETKOM,server_default=NETKOM)
    __tablename__='sessions'
    id=Column(String,primary_key=True); user_id=Column(String,ForeignKey('users.id')); csrf=Column(String); expires=Column(Integer); seen=Column(Integer); remember=Column(Boolean,default=False,nullable=False)
class Invite(Base):
    team=Column(String,nullable=False,default=NETKOM,server_default=NETKOM)
    __tablename__='invites'
    token=Column(String,primary_key=True); email=Column(String,nullable=False); name=Column(String,nullable=False); role=Column(String,nullable=False)
    documents=Column(Boolean,default=False); secret=Column(LargeBinary,nullable=False); expires=Column(Integer); used=Column(Boolean,default=False)
    reset_user=Column(String,nullable=True); owner=Column(Boolean,default=False)
class Record(Base):
    team=Column(String,nullable=False,default=NETKOM,server_default=NETKOM)
    __tablename__='records'
    id=Column(String,primary_key=True,default=uid); kind=Column(String,index=True); owner_id=Column(String,index=True); data=Column(LargeBinary,nullable=False)
class Document(Base):
    team=Column(String,nullable=False,default=NETKOM,server_default=NETKOM)
    __tablename__='documents'
    id=Column(String,primary_key=True,default=uid); owner_id=Column(String,ForeignKey('users.id')); kind=Column(String); size=Column(Integer); mime=Column(String)
    created=Column(Integer); content=Column(LargeBinary,nullable=False)
class Audit(Base):
    team=Column(String,nullable=False,default=NETKOM,server_default=NETKOM)
    __tablename__='audit'
    id=Column(String,primary_key=True,default=uid); user_id=Column(String); action=Column(String); target=Column(String); at=Column(Integer)
class Attempt(Base):
    __tablename__='attempts'
    id=Column(String,primary_key=True); count=Column(Integer,default=0); until=Column(Integer)

ROLES={'director','technician','runner','communication'}
FINE_TYPES=[('Falta de respeto leve',5),('Falta de respeto moderada',10),('Falta de respeto grave','Expulsión'),('Material en mal estado',5),('Llega 5 minutos tarde',5),('Llega 10 minutos tarde',10),('Llega 15 minutos tarde',15),('No trae ropa adecuada',5),('Otras · 5 €',5),('Otras · 10 €',10)]
CLOTHES=['Maillot corto','Maillot largo','Culote corto','Culote largo','Gava','Buzo','Chaleco','Pantalón largo','Pantalón corto','Camiseta','Polo','Sudadera','Plumas']
def clothing_quantities(profile):
    quantities={item:2 if item=='Camiseta' else 1 for item in CLOTHES}
    quantities.update({item:qty for item,qty in profile.get('quantities',{}).items() if item in CLOTHES})
    return quantities
PRIVATE_TYPES={'dni','dni_reverso','sepa','licencia','licencia_reverso','autorizacion','contrato_club'}
PHOTO_TYPES={'portrait','action'}

def create_app(test_config=None):
    app=Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=5*1024*1024,TESTING=False)
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
    dburl=urlunsplit(parts._replace(query=urlencode([(k,v) for k,v in parse_qsl(parts.query) if k in ('sslmode','sslrootcert','connect_timeout','application_name','options')])))
    engine=create_engine(dburl,pool_pre_ping=True,**({'connect_args':{'check_same_thread':False}} if dburl.startswith('sqlite') else {'pool_size':1,'max_overflow':1,'connect_args':{'prepare_threshold':None}}))
    if not dburl.startswith('sqlite'):
        try:
            with engine.begin() as connection:connection.execute(sql_text('CREATE SCHEMA IF NOT EXISTS mbb_private'))
        except Exception as exc:
            import re
            detail=str(getattr(exc,'orig',type(exc).__name__))
            detail=re.sub(r'postgres(?:ql)?://\S+', '[connection]', detail)
            print('DB_START_ERROR: '+detail[:700],flush=True)
            @app.get('/health')
            def unavailable_health():
                print('DB_CONNECT_DIAGNOSTIC: '+detail[:700],flush=True)
                return {'status':'database_unavailable','category':'connection'},503
            @app.get('/')
            def unavailable_page():return 'Conexión con la base de datos en configuración.',503
            return app
        engine=engine.execution_options(schema_translate_map={None:'mbb_private'})
    Base.metadata.create_all(engine)
    if not dburl.startswith('sqlite'):
        with engine.begin() as connection:
            connection.execute(sql_text('ALTER TABLE mbb_private.sessions ADD COLUMN IF NOT EXISTS remember BOOLEAN NOT NULL DEFAULT FALSE'))
            for table in ('users','sessions','invites','records','documents','audit'):
                connection.execute(sql_text(
                    f"ALTER TABLE mbb_private.{table} ADD COLUMN IF NOT EXISTS team VARCHAR NOT NULL DEFAULT 'netkom'"
                ))
            connection.execute(sql_text('ALTER TABLE mbb_private.users ALTER COLUMN email DROP NOT NULL, ALTER COLUMN password DROP NOT NULL, ALTER COLUMN mfa DROP NOT NULL'))
    Sessions=sessionmaker(bind=engine,expire_on_commit=False,info={'team':NETKOM})
    configure_team_scope(Sessions,(User,Invite,Document,Audit),Record)
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
        g.db=Sessions();g.user=None;g.login=None;g.team=NETKOM
        g.db.info.pop('team',None)
        if request.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
            expected=os.environ.get('PUBLIC_ORIGIN')
            if not app.testing:
                origin=request.headers.get('Origin','')
                if not expected or origin!=expected:abort(403,'Origen no permitido')
        token=request.cookies.get('__Host-mbb')
        if token:
            row=g.db.get(LoginSession,digest(token));now=int(time.time())
            if row and row.expires>now and (row.remember or row.seen>now-1800):
                u=g.db.get(User,row.user_id)
                if u and u.active:g.user=u;g.login=row;row.seen=now
        if g.user:
            g.team=g.login.team if g.user.id=='shared-direction' else g.user.team
            if request.path not in ('/api/activate/start','/api/activate/finish','/api/login'):
                g.db.info['team']=g.team
        if request.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS') and g.login:
            if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),g.login.csrf):abort(403,'Recarga la sesión')
    @app.after_request
    def after(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'wasm-unsafe-eval' https://cdn.jsdelivr.net; worker-src 'self' blob: https://cdn.jsdelivr.net; style-src 'self'; img-src 'self' blob:; connect-src 'self' https://cdn.jsdelivr.net; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if getattr(g,'organization_nonce',None):
            response.headers['X-Frame-Options']='SAMEORIGIN'
            response.headers['Content-Security-Policy']=(
                "default-src 'none'; script-src 'nonce-"+g.organization_nonce+"'; "
                "style-src 'unsafe-inline'; frame-ancestors 'self'; sandbox allow-scripts; "
                "base-uri 'none'; form-action 'none'")
        response.headers['Permissions-Policy']='camera=(self), microphone=(), geolocation=()'
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
    def health():
        g.db.execute(select(1))
        calendar_receipt=app.config.get('NETKOM_CALENDAR_RECEIPT')
        health_details={'netkomCalendar2027':calendar_receipt} if calendar_receipt else {}
        occident_receipt=app.config.get('OCCIDENT_ROSTER_IMPORT_RECEIPT')
        if occident_receipt:health_details['occidentRoster']= {key:occident_receipt[key] for key in ('total','added','updated','conflicts')}
        rider_receipt=app.config.get('RIDER_ACCOUNT_RECEIPT')
        if rider_receipt:return jsonify(status='ok',riderAccountsVerified=rider_receipt['verified'],existingAccounts=rider_receipt['existingAccounts'],**health_details)
        receipt=app.config.get('ROSTER_IMPORT_RECEIPT')
        return jsonify(status='ok',rosterImported=receipt['total'],**health_details) if receipt else jsonify(status='ok',**health_details)
    @app.get('/')
    def index():return render_template('index.html')
    @app.get('/organizacion')
    @require('director')
    def organization():
        g.organization_nonce=secrets.token_urlsafe(24)
        return render_template('organization.html',organization_nonce=g.organization_nonce,organization_empty=g.team!=NETKOM)

    @app.get('/api/me')
    def me():
        if not g.user:return jsonify(user=None)
        return jsonify(user={'id':g.user.id,'name':g.user.name,'email':g.user.email,'role':g.user.role,'documents':g.user.documents,'owner':g.user.owner},csrf=g.login.csrf,team=g.team,teams=TEAMS,canSwitchTeam=g.user.id=='shared-direction',canInviteUsers=g.user.owner or (g.user.id=='shared-direction' and g.team in NEW_TEAMS),clothes=CLOTHES,fines=FINE_TYPES)
    @app.post('/api/team')
    @require('director')
    def switch_team():
        if g.user.id!='shared-direction':abort(403)
        team=body().get('team')
        if not isinstance(team,str) or team not in TEAMS:abort(400)
        session=g.db.get(LoginSession,g.login.id,with_for_update=True,populate_existing=True)
        session.team=team
        session.csrf=secrets.token_urlsafe(32)
        audit('team_switched',team)
        return jsonify(ok=True)

    @app.post('/api/occident/administrator-invite')
    @require('director')
    def invite_occident_administrator():
        if g.user.id!='shared-direction' or g.team!=OCCIDENT:abort(403)
        username='occident.alextoledo'
        if g.db.get_bind().dialect.name=='postgresql':
            g.db.execute(sql_text('SELECT pg_advisory_xact_lock(20273009)'))
        existing=g.db.scalar(select(User.id).where(User.email==username)
                             .execution_options(shared_resource_lookup=True))
        if existing:abort(409,'Alex Toledo ya ha activado su acceso a Occident')
        g.db.execute(update(Invite).where(Invite.email==username,Invite.used==False).values(used=True))
        token=secrets.token_urlsafe(40)
        g.db.add(Invite(token=digest(token),email=username,name='Alex Toledo',role='director',
                        documents=True,owner=False,secret=seal(pyotp.random_base32()),
                        expires=int(time.time())+48*3600))
        audit('occident_administrator_invited',username)
        return jsonify(token=token,username=username)

    @app.post('/api/login')
    def login():
        d=body();email=text(d,'email',254).lower();password=text(d,'password',256);code=text(d,'code',10)
        throttle('login:'+email);throttle('ip:'+request.remote_addr,40)
        u=g.db.execute(select(User).where(User.email==email).with_for_update()).scalar_one_or_none()
        if not u:
            from rider_accounts import alias_key
            alias=g.db.get(Record,alias_key(email))
            if alias and alias.kind=='system:login-alias':
                u=g.db.get(User,alias.owner_id,with_for_update=True)
        valid=check_password_hash(u.password if u and u.password else dummy_password,password)
        if not u or not u.active or not valid:audit('login_failed');g.db.commit();abort(401,'Credenciales o código incorrectos')
        remember=d.get('remember') in (True,'on');lifetime=30*86400 if remember else 8*3600
        token=secrets.token_urlsafe(40);now=int(time.time());g.db.add(LoginSession(id=digest(token),user_id=u.id,team=u.team,csrf=secrets.token_urlsafe(32),expires=now+lifetime,seen=now,remember=remember))
        g.user=u;g.db.info['team']=u.team;audit('login',u.id);response=jsonify(ok=True)
        response.set_cookie('__Host-mbb',token,secure=True,httponly=True,samesite='Strict',path='/',max_age=lifetime if remember else None)
        return response
    @app.post('/api/logout')
    @require()
    def logout():
        g.db.delete(g.login);audit('logout');r=jsonify(ok=True);r.delete_cookie('__Host-mbb',secure=True,httponly=True,samesite='Strict');return r
    def get_invite(token,lock=True):
        query=select(Invite).where(Invite.token==digest(token))
        if lock:query=query.with_for_update().execution_options(populate_existing=True)
        invite=g.db.execute(query).scalar_one_or_none()
        if not invite or invite.used or invite.expires<int(time.time()):abort(400,'Enlace caducado o ya utilizado')
        return invite
    @app.post('/api/activate/start')
    def activate_start():
        d=body();token=text(d,'token',120);throttle('activation:'+request.remote_addr,30)
        bootstrap=os.environ.get('BOOTSTRAP_TOKEN_HASH','')
        if bootstrap and secrets.compare_digest(digest(token),bootstrap):
            # Transactional singleton lock, also prevents concurrent bootstrap administrators.
            if not g.db.get(Invite,bootstrap):
                email=os.environ['ADMIN_EMAIL'].lower()
                existing=g.db.scalar(select(User).where(User.email==email,User.owner==True))
                if g.db.scalar(select(func.count()).select_from(User)) and not existing:abort(400,'Cuenta responsable no encontrada')
                g.db.execute(update(Invite).where(Invite.email==email,Invite.used==False).values(used=True))
                if existing:
                    existing.password=generate_password_hash(secrets.token_urlsafe(48),method='scrypt:32768:8:1')
                    g.db.execute(delete(LoginSession).where(LoginSession.user_id==existing.id))
                g.db.add(Invite(token=bootstrap,email=email,name='Alex Álvarez',role='director',documents=True,owner=True,reset_user=existing.id if existing else None,secret=seal(pyotp.random_base32()),expires=int(os.environ['BOOTSTRAP_EXPIRES'])))
                g.db.flush()
        i=get_invite(token)
        secret=unseal(i.secret)
        return jsonify(email=i.email,name=i.name,role=i.role,chooseEmail=not i.email and bool(i.reset_user))
    @app.post('/api/activate/finish')
    def activate_finish():
        d=body();throttle('finish:'+request.remote_addr,20);token=text(d,'token',120)
        pending=get_invite(token,lock=False)
        roster_activation=not pending.email and bool(pending.reset_user)
        rider=g.db.get(User,pending.reset_user,with_for_update=True) if roster_activation else None
        i=get_invite(token)
        password=text(d,'password',256)
        if len(password)<6:abort(400,'La contraseña debe tener al menos 6 caracteres')
        u=rider if roster_activation else g.db.get(User,i.reset_user) if i.reset_user else None
        if roster_activation:
            import re
            if not u or u.role!='runner' or not u.active or u.email or u.password:abort(409,'La ficha ya tiene acceso o está desactivada')
            email=text(d,'email',254).lower()
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):abort(400,'Introduce un correo válido')
            if g.db.scalar(select(User.id).where(User.email==email)):abort(409,'Ese correo ya está registrado')
            u.email=email
            from sqlalchemy.exc import IntegrityError
            try:g.db.flush()
            except IntegrityError:
                g.db.rollback()
                abort(409,'Ese correo ya está registrado')
        if i.reset_user and (not u or not u.active):abort(400)
        if u:
            u.password=generate_password_hash(password,method='scrypt:32768:8:1');u.mfa=i.secret;u.last_step=int(time.time())//30
            g.db.execute(delete(LoginSession).where(LoginSession.user_id==u.id))
        else:
            if g.db.scalar(select(User.id).where(User.email==i.email)):abort(409,'Usuario existente')
            u=User(email=i.email,name=i.name,role=i.role,team=i.team,password=generate_password_hash(password,method='scrypt:32768:8:1'),mfa=i.secret,last_step=int(time.time())//30,documents=i.documents,owner=i.owner,profile=seal({}))
            g.db.add(u);g.db.flush()
        related=Invite.reset_user==u.id if roster_activation else Invite.email==i.email
        g.db.execute(update(Invite).where(related,Invite.used==False).values(used=True))
        i.used=True;g.db.info['team']=i.team;audit('account_activated',u.id);return jsonify(ok=True)
    def issue_rider_invite(rider, expires):
        token=secrets.token_urlsafe(40)
        g.db.add(Invite(token=digest(token),email='',name=rider.name,role='runner',reset_user=rider.id,secret=seal(pyotp.random_base32()),expires=expires))
        audit('rider_invited',rider.id)
        return dict(name=rider.name,token=token)

    @app.post('/api/roster/invites')
    @require('director')
    def roster_invites():
        if not g.user.owner:abort(403,'Solo la dirección responsable puede generar accesos')
        targets=body().get('riders')
        if not isinstance(targets,list) or not 1<=len(targets)<=100 or any(not isinstance(x,str) for x in targets):
            abort(400,'Selecciona al menos un corredor')
        riders=list(g.db.scalars(select(User).where(User.id.in_(set(targets))).order_by(User.id).with_for_update()))
        if len(riders)!=len(set(targets)) or any(not u.active or u.role!='runner' or u.email or u.password for u in riders):
            abort(409,'Selecciona solo corredores activos que aún no tengan acceso')
        expires=int(time.time())+7*86400
        invitations=[]
        for rider in riders:
            g.db.execute(update(Invite).where(Invite.reset_user==rider.id,Invite.email=='',Invite.used==False).values(used=True))
            invitations.append(issue_rider_invite(rider,expires))
        return jsonify(invitations=sorted(invitations,key=lambda item:item['name']),expires=expires)

    @app.get('/api/users')
    @require('director')
    def users():return jsonify(users=[{'id':u.id,'name':u.name,'email':u.email,'role':u.role,'active':u.active,'documents':u.documents,'owner':u.owner,'accountReady':bool(u.password)} for u in g.db.scalars(select(User).order_by(User.name))])
    @app.post('/api/staff/accounts')
    @require('director')
    def create_staff_accounts():
        if g.team!=NETKOM:abort(403,'Gestiona los accesos de técnicos compartidos desde Netkom')
        import re
        from rider_accounts import alias_key

        d=body()
        replace_all=d.get('replaceAll') is True
        if replace_all and not g.user.owner:abort(403,'Solo la cuenta responsable de Dirección puede cambiar las contraseñas existentes')
        if replace_all and ('name' in d or 'staffId' in d):abort(400)
        if g.db.get_bind().dialect.name=='postgresql':
            g.db.execute(sql_text('SELECT pg_advisory_xact_lock(20273004)'))
        staff=g.db.scalars(select(Record).where(Record.kind=='module:staff').order_by(Record.id).with_for_update()).all()
        individual='staffId' in d
        if individual:
            staff_id=text(d,'staffId',40)
            staff=[record for record in staff if record.id==staff_id]
            if not staff:abort(404,'Ficha de técnico no encontrada')
        technician_names={normalize(name) for name in g.db.scalars(select(User.name).where(User.role=='technician'))}
        if not individual and 'name' in d:
            name=' '.join(text(d,'name',150).split())
            if not name:abort(400,'Introduce el nombre y los apellidos')
            key=normalize(name)
            if key in technician_names or any(normalize(unseal(record.data)['name'])==key for record in staff):
                abort(409,'Ya existe un técnico con ese nombre. Revisa su ficha en Personal técnico.')
            record=Record(id=uid(),kind='module:staff',owner_id=g.user.id,data=seal(dict(name=name)))
            g.db.add(record)
            staff=[record]
        usernames=set(g.db.scalars(select(User.email).where(User.email.is_not(None))))
        accounts=[]; skipped=[]; processed_users=set()
        for record in staff:
            data=unseal(record.data)
            name=data['name']
            user=None
            if (individual or replace_all) and data.get('user'):
                user=g.db.get(User,data['user'],with_for_update=True)
                if not user or not user.active or user.role!='technician' or user.owner or user.documents:
                    if replace_all:
                        skipped.append(name)
                        continue
                    abort(409,'Revisa el usuario vinculado a esta ficha')
                if user.password and not g.user.owner:
                    abort(403,'Solo la cuenta responsable de Dirección puede cambiar una contraseña existente')
                if user.password and d.get('replace') is not True and not replace_all:
                    abort(409,'Confirma el cambio de contraseña')
            if not user and (data.get('user') or normalize(name) in technician_names):
                if individual:abort(409,'Ya existe una cuenta con ese nombre. Vincúlala desde Editar.')
                skipped.append(name)
                continue
            if user and user.id in processed_users:
                skipped.append(name)
                continue
            base='.'.join(re.findall(r'[a-z0-9]+',normalize(name).lower()))[:80].rstrip('.') or 'tecnico'
            username=user.email if user and user.email and '@' not in user.email else base
            alias=None
            if not user or username!=user.email:
                suffix=2
                while True:
                    alias=g.db.get(Record,alias_key(username))
                    if username not in usernames and (not alias or user and alias.owner_id==user.id):break
                    username=f'{base}.{suffix}'
                    suffix+=1
            password=''.join(secrets.choice('abcdefghjkmnpqrstuvwxyz23456789') for _ in range(8))
            if user:
                if username!=user.email and not alias:
                    g.db.add(Record(id=alias_key(username),kind='system:login-alias',owner_id=user.id,
                                    data=seal(dict(username=username))))
                g.db.execute(delete(LoginSession).where(LoginSession.user_id==user.id))
                g.db.execute(update(Invite).where(Invite.reset_user==user.id,Invite.used==False).values(used=True))
                audit('technician_password_changed',user.id)
            else:
                user=User(id=uid(),email=username,name=name,role='technician',profile=seal({}))
                g.db.add(user)
                data['user']=user.id
                record.data=seal(data)
                audit('technician_account_created',user.id)
            user.password=generate_password_hash(password,method='scrypt:32768:8:1')
            processed_users.add(user.id)
            usernames.add(username)
            technician_names.add(normalize(name))
            accounts.append(dict(name=name,username=username,password=password))
        return jsonify(accounts=sorted(accounts,key=lambda account:normalize(account['name'])),skipped=sorted(skipped))

    @app.post('/api/invites')
    @require('director')
    def invite():
        if not (g.user.owner or (g.user.id=='shared-direction' and g.team in NEW_TEAMS)):abort(403,'Solo la dirección responsable puede dar altas')
        d=body();email=text(d,'email',254).lower();name=text(d,'name',100);role=text(d,'role',20)
        if not name or '@' not in email or role not in ROLES:abort(400,'Revisa nombre, correo y perfil')
        if g.db.scalar(select(User.id).where(User.email==email)):abort(409,'Ese usuario ya existe')
        g.db.execute(delete(Invite).where(Invite.email==email,Invite.used==False))
        token=secrets.token_urlsafe(40);i=Invite(token=digest(token),email=email,name=name,role=role,documents=role=='director' and d.get('documents') is True,owner=False,secret=seal(pyotp.random_base32()),expires=int(time.time())+48*3600);g.db.add(i);audit('invite_created',email)
        return jsonify(token=token,expires=i.expires)
    @app.post('/api/invites/import')
    @require('director')
    def bulk_invites():
        if not g.user.owner:abort(403)
        rows=body().get('rows')
        if not isinstance(rows,list) or not 1<=len(rows)<=100:abort(400,'Entre 1 y 100 usuarios por archivo')
        checked=[];emails=set()
        for row in rows:
            if not isinstance(row,dict):abort(400)
            email=text(row,'email',254).lower();name=text(row,'name',100);role=text(row,'role',30)
            if not name or '@' not in email or role not in ROLES or email in emails:abort(400,'Revisa nombres, correos duplicados y perfiles')
            if g.db.scalar(select(User.id).where(User.email==email)):abort(409,'El usuario '+email+' ya existe')
            emails.add(email);checked.append((email,name,role))
        output=[]
        for email,name,role in checked:
            g.db.execute(delete(Invite).where(Invite.email==email,Invite.used==False))
            token=secrets.token_urlsafe(40);g.db.add(Invite(token=digest(token),email=email,name=name,role=role,documents=False,owner=False,secret=seal(pyotp.random_base32()),expires=int(time.time())+48*3600));output.append(dict(name=name,email=email,token=token))
        audit('bulk_invites_created',str(len(output)));return jsonify(invitations=output)
    @app.get('/api/roster/import-status')
    @require('director')
    def roster_import_status():
        if not g.user.owner:abort(403)
        return jsonify(imports=[unseal(r.data) for r in g.db.scalars(select(Record).where(Record.kind=='system:roster-import'))])
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
        if not u or not u.active or not u.email or not u.password:abort(404)
        g.db.execute(update(Invite).where(Invite.email==u.email,Invite.used==False).values(used=True));token=secrets.token_urlsafe(40);g.db.add(Invite(token=digest(token),email=u.email,name=u.name,role=u.role,documents=u.documents,reset_user=u.id,secret=seal(pyotp.random_base32()),expires=int(time.time())+3600));g.db.execute(delete(LoginSession).where(LoginSession.user_id==target));audit('reset_created',target);return jsonify(token=token)
    @app.get('/api/profile/<target>')
    @require('director','runner')
    def profile(target):
        u=runner_target(target);p=unseal(u.profile)
        if g.user.id!=target and not g.user.documents:p={k:v for k,v in p.items() if k in ('sizes','quantities','coach','club','photoConsent','bike','bikeSize','helmet','pedals','saddleHeight','saddleToBar','competitionDays2026')}
        audit('profile_read',target);return jsonify(profile=p)
    @app.post('/api/profile/<target>')
    @require('director','runner')
    def profile_save(target):
        u=runner_target(target);d=body();p=unseal(u.profile)
        allowed={'competitionDays2026','coach','club','sizes','photoConsent','bike','bikeSize','helmet','pedals','saddleHeight','saddleToBar'}
        if g.user.id==target or g.user.documents:allowed|={'phone','address','birth','guardian','guardianPhone','iban','bankHolder','guardianEmail','guardian2','guardianPhone2','guardianEmail2','city','zip','province','departureDefault','pickupPoint','firstName','surname','birthYear','dni','dniStatus','uciId','medicationStatus','medicationDetails','allergiesStatus','allergiesDetails','intolerancesStatus','intolerancesDetails'}
        if g.user.role=='director':allowed|={'quantities','category'}
        for k,v in d.items():
            if k not in allowed:abort(403)
            if k in ('sizes','quantities'):
                if not isinstance(v,dict) or any(key not in CLOTHES for key in v):abort(400)
                if k=='sizes' and any(val not in ['','XXS','XS','S','M','L','XL','XXL','XXXL'] for val in v.values()):abort(400)
                if k=='quantities' and any(type(val)!=int or val<0 or val>100 for val in v.values()):abort(400)
            elif k=='category':
                if not isinstance(v,str) or len(v)>80 or (g.team not in NEW_TEAMS and v not in ('',*OCCIDENT_CATEGORIES)):
                    abort(400,'Categoría no válida')
                v=v.strip()
            elif k=='uciId':
                if not isinstance(v,str) or (v and (len(v)!=11 or not v.isascii() or not v.isdigit())):abort(400,'El ID UCI debe tener 11 cifras')
            elif k=='competitionDays2026':
                if v!='' and (type(v)!=int or not 0<=v<=365):abort(400,'Días de competición: indica un entero entre 0 y 365')
            elif k in ('medicationStatus','allergiesStatus','intolerancesStatus'):
                if v not in ('','Sí','No'):abort(400,'Selecciona Sí o No')
            elif k=='photoConsent':
                if type(v)!=bool:abort(400)
            elif not isinstance(v,str) or len(v)>250:abort(400)
            p[k]=v
        u.profile=seal(p)
        if any(k in d for k in ['bike','bikeSize','helmet','pedals','saddleHeight','saddleToBar','coach','club']):
            sport={k:p.get(k,'') for k in ['bike','bikeSize','helmet','pedals','coach','club']}
            for k in ['saddleHeight','saddleToBar']:
                try:sport[k]=int(p.get(k) or 0)
                except (ValueError,TypeError):abort(400,'Medida no válida')
            sport.update(rider=target,notes='')
            rec=next((x for x in g.db.scalars(select(Record).where(Record.kind=='module:sport')) if unseal(x.data).get('rider')==target),None)
            if rec:rec.data=seal(sport)
            else:g.db.add(Record(kind='module:sport',owner_id=target,data=seal(sport)))
        audit('profile_updated',target);return jsonify(ok=True)
    @app.get('/api/documents/<target>')
    @require('director','runner','communication')
    def documents(target):
        u=g.db.get(User,target)
        if not u or u.role!='runner':abort(404)
        private=(g.user.id==target or (g.user.role=='director' and g.user.documents))
        photos=(g.user.role in ('director','communication') and unseal(u.profile).get('photoConsent')) or g.user.id==target
        return jsonify(documents=[{'id':d.id,'kind':d.kind,'size':d.size,'created':d.created} for d in g.db.scalars(select(Document).where(Document.owner_id==target)) if (d.kind in PRIVATE_TYPES and private) or (d.kind in PHOTO_TYPES and photos)])
    @app.post('/api/documents/<target>')
    @require('director','runner','communication')
    def upload(target):
        kind=request.form.get('kind');f=request.files.get('file')
        if g.user.role=='communication':
            target_user=g.db.get(User,target)
            if not target_user or target_user.role!='runner' or kind not in PHOTO_TYPES or not unseal(target_user.profile).get('photoConsent'):abort(403)
        else:
            runner_target(target)
            if g.user.id!=target and not g.user.documents and kind not in PHOTO_TYPES:abort(403)
        if kind in {'sepa','autorizacion'} and not app.testing and os.environ.get('DOCUMENT_UPLOADS_ENABLED')!='true':abort(503,'La carga de SEPA y autorizaciones está deshabilitada')
        if kind not in PRIVATE_TYPES|PHOTO_TYPES or not f:abort(400)
        raw=f.read(4*1024*1024+1)
        if not raw or len(raw)>4*1024*1024:abort(400,'Máximo 4 MB por archivo')
        mime='image/jpeg'
        if kind in PRIVATE_TYPES and raw.startswith(b'%PDF-'):
            if b'%%EOF' not in raw[-65536:]:abort(400,'El PDF parece incompleto')
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
            try:
                reader=PdfReader(io.BytesIO(raw))
                if reader.is_encrypted:abort(400,'El PDF tiene contraseña. Sube una copia sin contraseña')
                if not 1<=len(reader.pages)<=10:abort(400,'Máximo 10 páginas por documento')
            except (PdfReadError,ValueError,OSError):abort(400,'El PDF no se puede abrir')
            mime='application/pdf'
        else:
            if kind in PRIVATE_TYPES and not raw.startswith((b'\xff\xd8\xff',b'\x89PNG\r\n\x1a\n')):
                abort(400,'Usa PDF, JPG o PNG')
            try:
                Image.MAX_IMAGE_PIXELS=20_000_000
                im=Image.open(io.BytesIO(raw));im.load()
                from PIL import ImageOps
                im=ImageOps.exif_transpose(im)
                if im.width*im.height>20_000_000:abort(400)
                if kind in PRIVATE_TYPES:
                    mime='image/png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg'
                else:
                    out=io.BytesIO();im.convert('RGB').save(out,format='JPEG',quality=90);raw=out.getvalue()
            except HTTPException:raise
            except Exception:abort(400,'Imagen no válida')
        total=g.db.scalar(select(func.coalesce(func.sum(Document.size),0)))
        if total+len(raw)>400*1024*1024:abort(400,'Almacenamiento completo. Contacta con Dirección.')
        d=Document(owner_id=target,kind=kind,size=len(raw),mime=mime,created=int(time.time()),content=cipher.encrypt(raw));g.db.add(d);g.db.flush();audit('document_uploaded',d.id);return jsonify(ok=True)
    @app.get('/api/file/<file_id>')
    @require()
    def file(file_id):
        d=g.db.get(Document,file_id)
        if not d:abort(404)
        u=g.db.get(User,d.owner_id)
        allowed=g.user.id==d.owner_id or (g.user.role=='director' and (g.user.documents or d.kind in PHOTO_TYPES))
        if d.kind.startswith('staff-dni:'):allowed=g.user.role=='director' and g.user.documents
        if d.kind in PHOTO_TYPES and g.user.role=='communication':allowed=bool(unseal(u.profile).get('photoConsent'))
        if not allowed:abort(403)
        audit('document_downloaded',d.id)
        return send_file(io.BytesIO(cipher.decrypt(d.content)),mimetype=d.mime,as_attachment=True,download_name=d.kind+({'application/pdf':'.pdf','image/png':'.png'}.get(d.mime,'.jpg')))
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
        end_date=text(d,'endDate',10)
        category=text(d,'category',60) or 'Carrera'
        race_type=text(d,'type',80) if category=='Carrera' else ''
        if category not in ('Carrera','Concentración','Entrenamiento de equipo'):abort(400,'Selecciona el tipo de actividad')
        if race_type and race_type not in ('Euskaldun','Copa de España','Vueltas','Otras'):abort(400,'Selecciona la categoría de carrera')
        if not name:abort(400,'Indica el nombre')
        try:
            if date:date=datetime.date.fromisoformat(date).isoformat()
            if end_date:end_date=datetime.date.fromisoformat(end_date).isoformat()
        except ValueError:abort(400,'Revisa las fechas de la actividad')
        if end_date and (not date or end_date<date):
            abort(400,'La fecha de fin requiere una fecha de inicio y debe ser igual o posterior')
        r=Record(kind='event',owner_id=g.user.id,data=seal(dict(name=name,date=date,endDate=end_date,place=place,category=category,type=race_type,called=[])));g.db.add(r);audit('event_created');return jsonify(ok=True)
    @app.post('/api/events/<event_id>/availability')
    @require('runner','technician')
    def availability(event_id):
        event=g.db.get(Record,event_id,with_for_update=True)
        if not event or event.kind!='event':abort(404)
        d=body();status=text(d,'status',30)
        if status not in ['Por confirmar','Disponible','No disponible']:abort(400)
        if g.user.role=='runner' and status=='Por confirmar':abort(400,'Indica Disponible o No disponible')
        key=digest(event_id+':'+g.user.id);r=g.db.get(Record,key)
        data=seal({'user':g.user.id,'status':status})
        if r:r.data=data
        else:g.db.add(Record(id=key,kind='availability',owner_id=event_id,data=data))
        audit('availability_updated',event_id);return jsonify(ok=True)
    @app.post('/api/events/<event_id>/call')
    @require('director')
    def call(event_id):
        r=g.db.get(Record,event_id,with_for_update=True)
        if not r or r.kind!='event':abort(404)
        payload=body();states=payload.get('states');data=unseal(r.data)
        if states is not None:
            if not isinstance(states,dict) or len(states)>100:abort(400)
            if any(value not in ('No convocado','Preconvocado','Convocado') for value in states.values()):abort(400)
            ids=list(states)
        else:
            ids=payload.get('users')
        if not isinstance(ids,list) or len(ids)>100 or any(not isinstance(target,str) for target in ids):abort(400)
        for target in ids:
            u=g.db.get(User,target)
            if not u or not u.active or u.role!='runner':abort(400,'Selecciona un corredor activo')
        if states is not None:
            data['called']=[target for target,value in states.items() if value=='Convocado']
            data['precalled']=[target for target,value in states.items() if value=='Preconvocado']
            data['callStatus']='Publicada' if data['called'] else 'Borrador'
        else:
            data['called']=list(dict.fromkeys(ids));data['precalled']=[]
        r.data=seal(data);audit('call_updated',event_id);return jsonify(ok=True)
    @app.get('/api/roster')
    @require()
    def roster():
        # Never serialize ORM users: sensitive columns are deliberately excluded.
        inactive=request.args.get('status')=='inactive'
        if inactive and g.user.role!='director':abort(403)
        if g.user.role not in ('director','communication','technician'):
            return jsonify(riders=[{'id':g.user.id,'name':g.user.name}])
        riders=[]
        for u in g.db.scalars(select(User).where(User.role=='runner',User.active== (not inactive)).order_by(User.name)):
            item={'id':u.id,'name':u.name}
            if g.user.role=='director':
                profile=unseal(u.profile)
                year=str(profile.get('birthYear') or str(profile.get('birth') or '')[:4]).strip()
                item['birthYear']=year if len(year)==4 and year.isdigit() else ''
                if g.team!=NETKOM:item['category']=profile.get('category','')
            riders.append(item)
        return jsonify(riders=riders)
    @app.post('/api/roster/<target>/status')
    @require('director')
    def rider_status(target):
        active=body().get('active')
        if type(active)!=bool:abort(400)
        rider=g.db.get(User,target,with_for_update=True)
        if not rider or rider.role!='runner' or rider.owner:abort(404)
        rider.active=active
        if not active:
            g.db.execute(delete(LoginSession).where(LoginSession.user_id==target))
            g.db.execute(update(Invite).where(Invite.reset_user==target,Invite.used==False).values(used=True))
        audit('rider_reactivated' if active else 'rider_deactivated',target)
        return jsonify(ok=True)

    @app.post('/api/roster')
    @require('director')
    def create_rider():
        d=body()
        first=' '.join(text(d,'firstName',100).split())
        surname=' '.join(text(d,'surname',180).split())
        if not first or not surname:abort(400,'Introduce el nombre y los apellidos')
        name=f'{first} {surname}'
        if g.db.get_bind().dialect.name=='postgresql':
            # Share the roster import lock so both paths check for duplicates in turn.
            g.db.execute(sql_text('SELECT pg_advisory_xact_lock(20271818)'))
        key=normalize(name)
        names=g.db.scalars(select(User.name).where(User.role=='runner'))
        if any(normalize(existing)==key for existing in names):
            abort(409,'Ya existe una ficha con ese nombre y apellidos')
        rider=User(name=name,role='runner',profile=seal(dict(firstName=first,surname=surname)))
        g.db.add(rider)
        g.db.flush()
        audit('rider_created',rider.id)
        result=dict(rider=dict(id=rider.id,name=rider.name))
        if d.get('invite') is True:
            expires=int(time.time())+7*86400
            result.update(invitation=issue_rider_invite(rider,expires),expires=expires)
        return jsonify(result),201

    @app.get('/api/clothes')
    @require('director')
    def clothes():
        riders=[]
        for u in g.db.scalars(select(User).where(User.role=='runner',User.active==True).order_by(User.name,User.id)):
            profile=unseal(u.profile)
            riders.append(dict(id=u.id,name=u.name,sizes=profile.get('sizes',{}),quantities=clothing_quantities(profile)))
        return jsonify(riders=riders)
    @app.get('/api/clothes/mine')
    @require('runner')
    def my_clothes():
        profile=unseal(g.user.profile)
        return jsonify(sizes=profile.get('sizes',{}),quantities=clothing_quantities(profile))
    @app.get('/api/clothes/export')
    @require('director')
    def export():
        wb=Workbook();ws=wb.active;ws.title='Dotación por corredor';ws.append(['Corredor','Prenda','Talla','Cantidad']);total={}
        def safe(v):return "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v
        for u in g.db.scalars(select(User).where(User.role=='runner',User.active==True).order_by(User.name,User.id)):
            profile=unseal(u.profile)
            sizes=profile.get('sizes',{})
            quantities=clothing_quantities(profile)
            for item in CLOTHES:
                size=sizes.get(item)
                qty=quantities.get(item)
                size=size or 'Sin indicar'
                ws.append([safe(u.name),item,size,qty])
                if qty:
                    total[(item,size)]=total.get((item,size),0)+qty
        ws=wb.create_sheet('Resumen dotación');ws.append(['Prenda','Talla','Cantidad'])
        for (item,size),qty in sorted(total.items()):ws.append([item,size,qty])
        ws=wb.create_sheet('Total dotación');ws.append(['Prenda','Cantidad total'])
        for item in CLOTHES:
            ws.append([item,sum(qty for (prenda,size),qty in total.items() if prenda==item)])
        ws.append(['TOTAL UNIDADES',sum(total.values())])
        from settlements import clothing_orders
        extras=wb.create_sheet('Compras extra')
        extras.append(['Pedido','Fecha','Corredor','Prenda','Talla','Unidades','Precio unitario (€)','Importe (€)','Estado del cargo'])
        extra_totals={}
        for order in clothing_orders(g.db,Record,unseal):
            for item in order['items']:
                extras.append([safe(order['id']),safe(order['created']),safe(order['name']),safe(item['name']),safe(item['size']),
                               item['quantity'],item['price']/100,item['price']*item['quantity']/100,safe(order['paymentStatus'])])
                for cell in extras[extras.max_row][6:8]:cell.number_format='#,##0.00'
                if order['paymentStatus']!='Anulado':
                    key=(item['name'],item['size'])
                    extra_totals[key]=extra_totals.get(key,0)+item['quantity']
        extra_summary=wb.create_sheet('Resumen extras')
        extra_summary.append(['Prenda extra','Talla','Unidades'])
        for (item,size),qty in sorted(extra_totals.items()):extra_summary.append([safe(item),safe(size),qty])
        from openpyxl.styles import Font, PatternFill
        for sheet in wb:
            sheet.freeze_panes='A2'
            sheet.auto_filter.ref=f'A1:{sheet.cell(sheet.max_row,sheet.max_column).coordinate}' if sheet.title!='Total dotación' else f'A1:B{sheet.max_row-1}'
            for cell in sheet[1]:
                cell.font=Font(bold=True,color='FFFFFF')
                cell.fill=PatternFill('solid',fgColor='173047')
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
    shared_hash=os.environ.get('SHARED_DIRECTION_PASSWORD_HASH')
    if not app.testing and shared_hash:
        from direction_access import seed_direction_account
        seed_direction_account(Sessions,User,Record,cipher,shared_hash)
    roster_payload=os.environ.get('ROSTER_IMPORT_DATA')
    if not app.testing and roster_payload and roster_payload!='[]':
        app.config['ROSTER_IMPORT_RECEIPT']=import_roster(Sessions,Record,User,cipher,roster_payload)
    occident_roster=os.environ.get('OCCIDENT_ROSTER_IMPORT_DATA')
    if not app.testing and occident_roster and occident_roster!='[]':
        app.config['OCCIDENT_ROSTER_IMPORT_RECEIPT']=import_roster(Sessions,Record,User,cipher,occident_roster,OCCIDENT)
    if not app.testing:
        from calendar_seed import seed_calendar
        app.config['NETKOM_CALENDAR_RECEIPT']=seed_calendar(Sessions,Record,cipher)
    from settlements import register_settlements
    register_settlements(app,Record,User,CLOTHES,seal,unseal,audit,require,body)
    from account_summary import register_account_summary
    register_account_summary(app,User,Record,unseal,audit,require)
    from space_reservations import register_space_reservations
    register_space_reservations(app,Record,seal,unseal,audit,require,body)
    from resources import register_resources
    register_resources(app,Record,seal,unseal,audit,require,body)
    from modules import register_modules
    register_modules(app,Record,User,Document,seal,unseal,audit,require,body)
    from invoices import register_invoices
    register_invoices(app,Record,Document,cipher,seal,unseal,audit,require)
    from bank_reconciliation import register_bank_reconciliation
    register_bank_reconciliation(app,Record,Document,seal,unseal,audit,require,body)
    from laboral_kutxa import register_laboral_kutxa
    register_laboral_kutxa(app,Record,seal,unseal,audit,require,body)
    from invoice_exports import register_invoice_exports
    register_invoice_exports(app,Record,Document,cipher,unseal,audit,require)
    from calendar_exports import register_calendar_exports
    register_calendar_exports(app,Record,unseal,audit,require)
    rider_accounts=os.environ.get('RIDER_ACCOUNT_SETUP')
    if not app.testing and rider_accounts and rider_accounts!='[]':
        from rider_accounts import provision_rider_accounts,verify_rider_accounts
        provision_rider_accounts(Sessions,User,Record,Invite,LoginSession,cipher,rider_accounts)
        app.config['RIDER_ACCOUNT_RECEIPT']=verify_rider_accounts(app,Sessions,User,Record,cipher,rider_accounts,os.environ['PUBLIC_ORIGIN'])
    return app

if __name__=='__main__':
    create_app().run(host='127.0.0.1',port=5000)
