import io
from test_security import env
from server import User
from werkzeug.security import generate_password_hash

def test_gestion(env,monkeypatch):
    app,_,login,_=env
    with app.extensions['db_sessions'].begin() as db:
        db.add(User(id='shared-direction',email='direccion',name='Dirección',role='director',
                    documents=True,password=generate_password_hash('a-password-for-testing'),
                    profile=app.extensions['cipher'].encrypt(b'{}')))
    director,h=login('director')
    assert director.get('/api/gestion').status_code==403
    browser=app.test_client()
    assert browser.post('/api/login',json={'email':'direccion','password':'a-password-for-testing'}).status_code==200
    headers={'X-CSRF-Token':browser.get('/api/me').json['csrf']}
    assert director.post('/api/modules/entry',json={'direction':'Gasto','date':'2026-11-01','amount':100,
                                                   'concept':'Netkom'},headers=h).status_code==200
    assert len(browser.get('/api/gestion').json['rows'])==1
    def upload_data():
        return {'file':(io.BytesIO(b'%PDF-1.7\n%%EOF'),'factura.pdf'),'supplier':'Proveedor',
                'reference':'123','date':'2026-11-09','base':'4959','tax':'1041','amount':'6000'}
    mail='/api/gestion/mail-intake'
    token='a'*40
    assert app.test_client().post(mail,data=upload_data()).status_code==401
    monkeypatch.setenv('GESTION_MAIL_TOKEN',token)
    mailer=app.test_client()
    assert mailer.post(mail,data=upload_data(),headers={'Authorization':'Bearer incorrect'}).status_code==401
    sent=mailer.post(mail,data=upload_data(),headers={'Authorization':'Bearer '+token})
    assert sent.status_code==201,sent.json
    entry=sent.json['id']
    assert browser.post('/api/gestion/invoices',data=upload_data(),headers=headers).json['duplicate']
    source=next(row for row in browser.get('/api/gestion').json['rows'] if row['id']==entry)
    assert source['allocations']=={} and source['status']=='Pendiente de revisar'
    file='/api/gestion/file/'+source['files'][0]
    assert director.get(file).status_code==403
    assert browser.get(file).data==b'%PDF-1.7\n%%EOF'
    split='/api/gestion/'+entry+'/allocation'
    assert browser.post(split,json={'amounts':{'occident':3000}},headers=headers).status_code==400
    assert browser.post(split,json={'amounts':{'occident':3000,'common':3000}},headers=headers).status_code==200
    assert director.get('/api/gestion/team').json['rows']==[]
    assert browser.post('/api/team',json={'team':'occident'},headers=headers).status_code==200
    assert browser.get('/api/gestion/team').json['rows'][0]['amount']==3000
    assert browser.get('/api/gestion/export?month=2026-11').status_code==200

    with app.extensions['db_sessions'].begin() as db:
        db.add(User(email='alex.alvarez@miribillacycling.com',name='Alex Álvarez',role='director',
                    password=generate_password_hash('a-password-for-testing'),
                    profile=app.extensions['cipher'].encrypt(b'{}')))
    alex=app.test_client()
    assert alex.post('/api/login',json={'email':'alex.alvarez@miribillacycling.com',
                                       'password':'a-password-for-testing'}).status_code==200
    access=alex.get('/api/me').json
    assert access['canManageGestion'] and not access['canSwitchTeam']
    assert alex.get('/api/gestion').status_code==200
