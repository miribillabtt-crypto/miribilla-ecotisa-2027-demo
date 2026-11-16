import io
from test_security import env
from server import User
from PIL import Image
from werkzeug.security import generate_password_hash

def test_gestion(env):
    app,_,login,_=env
    with app.extensions['db_sessions'].begin() as db:
        db.add(User(id='shared-direction',email='direccion',name='Dirección',role='director',
                    documents=True,password=generate_password_hash('a-password-for-testing'),
                    profile=app.extensions['cipher'].encrypt(b'{}')))
    director,h=login('director')
    assert director.get('/api/gestion').json['rows']==[]
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
    mailer=app.test_client()
    assert mailer.post(mail,data=upload_data()).status_code==401
    key=browser.post('/api/gestion/mail-key',json={'account':'miribillabtt@gmail.com'},headers=headers)
    mail_headers={'Authorization':'Bearer '+key.json['key'],'X-Gestion-Mailbox':'miribillabtt@gmail.com'}
    assert mailer.post(mail,data=upload_data(),headers=dict(mail_headers,Authorization='Bearer incorrect')).status_code==401
    assert mailer.post(mail,data=upload_data(),headers={**mail_headers,'X-Gestion-Mailbox':'alex.alvarez@miribillacycling.com'}).status_code==401
    sent=mailer.post(mail,data=upload_data(),headers=mail_headers)
    assert sent.status_code==201,sent.json
    entry=sent.json['id']
    assert browser.post('/api/gestion/invoices',data=upload_data(),headers=headers).json['duplicate']
    source=next(row for row in browser.get('/api/gestion').json['rows'] if row['id']==entry)
    assert source['allocations']=={} and source['status']=='Pendiente de revisar'
    assert source['needsOCR'] and source['amount']==0
    review='/api/gestion/'+entry+'/review'
    values={'date':'2026-11-09','counterparty':'Proveedor','reference':'123','baseAmount':4959,'taxAmount':1041,'amount':6000}
    assert browser.post(review,json=values,headers=headers).status_code==200
    assert b';Proveedor;123;' not in browser.get('/api/gestion/export').data
    assert browser.post(review,json={**values,'approved':True},headers=headers).status_code==200
    assert b';Proveedor;123;' in browser.get('/api/gestion/export').data
    file='/api/gestion/file/'+source['files'][0]
    assert director.get(file).status_code==404
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
    archive='/api/gestion/'+entry+'/archive'
    csrf={'X-CSRF-Token':browser.get('/api/me').json['csrf']}
    assert director.post(archive,json={},headers=h).status_code==403
    assert browser.post(archive,json={},headers=csrf).status_code==200
    overview=browser.get('/api/gestion').json
    assert entry not in [row['id'] for row in overview['rows']]
    assert entry in [row['id'] for row in overview['archived']]
    assert b';Proveedor;123;' not in browser.get('/api/gestion/export').data
    assert browser.get('/api/gestion/team').json['rows']==[]
    assert browser.get(file).status_code==200
    assert browser.post('/api/gestion/'+entry+'/restore',json={},headers=csrf).status_code==200
    assert b';Proveedor;123;' in browser.get('/api/gestion/export').data

    image=io.BytesIO()
    Image.new('RGB',(8,8),'white').save(image,format='JPEG')
    original=image.getvalue()
    def scan_data():
        return {'file':(io.BytesIO(original),'ticket.jpg'),'concept':'Gasolina del equipo'}
    uploaded=browser.post('/api/gestion/invoices',data=scan_data(),headers=csrf)
    assert uploaded.status_code==201,uploaded.json
    rows=browser.get('/api/gestion').json['rows']
    scan=next(row for row in rows if row['id']==uploaded.json['id'])
    assert scan['team']=='occident' and scan['concept']=='Gasolina del equipo' and scan['needsOCR']
    assert director.post('/api/gestion/invoices',data=scan_data(),headers=h).json['duplicate']
    assert all(row['team']=='netkom' for row in director.get('/api/gestion').json['rows'])
    scan_file='/api/gestion/file/'+scan['files'][0]
    assert director.get(scan_file).status_code==404
    downloaded=browser.get(scan_file)
    assert downloaded.mimetype=='image/jpeg' and downloaded.data==original
    assert browser.post('/api/gestion/'+scan['id']+'/review',json={**values,'reference':'scan-1',
                         'concept':scan['concept'],'approved':True},headers=csrf).status_code==200
    assert browser.post('/api/gestion/'+scan['id']+'/allocation',json={'amounts':{'common':6000}},headers=csrf).status_code==200
    assert director.get('/api/gestion/export').status_code==403
    assert 'Occident;Proveedor;scan-1;Gasolina del equipo' in browser.get('/api/gestion/export').get_data(as_text=True)
