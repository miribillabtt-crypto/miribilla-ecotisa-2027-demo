from datetime import date,timedelta
from test_security import env
from server import User, Record, Invite, digest
import json
import time
from werkzeug.security import generate_password_hash

def seed_record(app, team, kind, data):
    with app.extensions['db_sessions'].begin() as db:
        row=Record(team=team,kind=kind,data=app.extensions['cipher'].encrypt(json.dumps(data).encode()))
        db.add(row)
        db.flush()
        return row.id

def test_occident_isolated_and_shared(env):
    app,ids,login,_=env
    db=app.extensions['db_sessions']()
    profile=app.extensions['cipher'].encrypt(b'{}')
    db.add(User(id='shared-direction',email='direccion',name='Dirección',role='director',documents=True,
                password=generate_password_hash('a-password-for-testing'),profile=profile))
    db.commit()
    db.close()
    director,h=login('director')
    assert director.post('/api/team',json={'team':'occident'},headers=h).status_code==403
    day=(date.today()+timedelta(days=30)).isoformat()
    client=app.test_client()
    assert client.post('/api/login',json={'email':'direccion','password':'a-password-for-testing'}).status_code==200
    current=client.get('/api/me').json
    assert current['team']=='netkom' and current['canSwitchTeam']
    headers={'X-CSRF-Token':current['csrf']}
    vehicle=client.post('/api/modules/vehicle',json={'name':'Furgo común'},headers=headers).json['id']
    staff=client.post('/api/modules/staff',json={'name':'Técnico común'},headers=headers).json['id']
    created=client.post('/api/events',json={'name':'Carrera privada de Netkom','date':day},headers=headers)
    assert created.status_code==200,created.json
    event=client.get('/api/events').json['events'][0]['id']
    assert client.post('/api/modules/travel',json={'event':event,'vehicles':[vehicle],'staff':[staff]},headers=headers).status_code==200
    reservation=dict(space='Gela',date=day,start='18:00',end='19:00',title='Entrenamiento Netkom')
    booking=client.post('/api/space-reservations',json=reservation,headers=headers)
    assert booking.status_code==201,booking.json
    assert client.post('/api/team',json={'team':'occident'},headers=headers).status_code==200
    assert client.get('/api/events').json['events']==[]
    assert client.get('/api/roster').json['riders']==[]
    assert client.get('/api/modules/travel').json['records']==[]
    assert client.get('/api/profile/'+ids['runner']).status_code==404
    assert client.get('/api/modules/vehicle').json['records'][0]['id']==vehicle
    assert client.get('/api/modules/staff').json['records'][0]['id']==staff
    assert client.post('/api/events',json={'name':'stale'},headers=headers).status_code==403
    headers={'X-CSRF-Token':client.get('/api/me').json['csrf']}
    assert client.post('/api/events/'+event+'/details',json={'name':'changed'},headers=headers).status_code==403
    assert client.post('/api/space-reservations',json=reservation,headers=headers).status_code==403
    assert client.get('/api/space-reservations?date='+day).json['reservations'][0]['team']=='netkom'
    assert client.post('/api/events',json={'name':'Carrera Occident','date':day},headers=headers).status_code==403
    seed_record(app,'occident','event',dict(name='Carrera Occident',date=day,called=[]))
    token='existing-occident-invite'
    with app.extensions['db_sessions'].begin() as db:
        db.add(Invite(team='occident',token=digest(token),email='occident.alextoledo',name='Alex Toledo',
                      role='director',documents=True,secret=profile,expires=int(time.time())+3600))
    alex=app.test_client()
    assert alex.post('/api/activate/start',json={'token':token}).json['name']=='Alex Toledo'
    password='another-password-for-testing'
    activated=alex.post('/api/activate/finish',json={'token':token,'password':password})
    assert activated.status_code==200,activated.json
    assert alex.post('/api/login',json={'email':'occident.alextoledo','password':password}).status_code==200
    info=alex.get('/api/me').json
    assert info['team']=='occident' and not info['canSwitchTeam']
    assert alex.get('/api/events').json['events'][0]['name']=='Carrera Occident'
    assert alex.get('/api/users').json['users'][0]['name']=='Alex Toledo'
    assert alex.post('/api/team',json={'team':'netkom'},headers={'X-CSRF-Token':info['csrf']}).status_code==403
    alex_headers={'X-CSRF-Token':info['csrf']}
    assert alex.post('/api/modules/vehicle/'+vehicle,json={'name':'Furgo revisada'},headers=alex_headers).status_code==200
    assert director.get('/api/modules/vehicle').json['records'][0]['name']=='Furgo revisada'
    assert director.post('/api/modules/staff/'+staff,json={'name':'Técnico común','user':'original-link'},headers=h).status_code==200
    assert alex.post('/api/modules/staff/'+staff,json={'name':'Técnico revisado'},headers=alex_headers).status_code==200
    updated=director.get('/api/modules/staff').json['records'][0]
    assert (updated['name'],updated['user'])==('Técnico revisado','original-link')
    assert alex.post('/api/modules/staff/'+staff,json={'name':'Técnico revisado','user':'other-link'},headers=alex_headers).status_code==403
    assert alex.post('/api/modules/staff',json={'name':'Técnico Occident'},headers=alex_headers).status_code==200
    assert alex.post('/api/modules/vehicle/'+vehicle+'/archive',json={},headers=alex_headers).status_code==403
    assert director.get('/api/events').json['events'][0]['name']=='Carrera privada de Netkom'

def test_vehicle_bookings_are_shared_even_without_a_matching_activity(env):
    app,_,_,_=env
    with app.extensions['db_sessions'].begin() as db:
        db.add(User(id='shared-direction',email='direccion',name='Dirección',role='director',
                    documents=True,password=generate_password_hash('a-password-for-testing'),
                    profile=app.extensions['cipher'].encrypt(b'{}')))
    client=app.test_client()
    assert client.post('/api/login',json={'email':'direccion','password':'a-password-for-testing'}).status_code==200

    def post(path,data):
        return client.post('/api/'+path,json=data,headers={'X-CSRF-Token':client.get('/api/me').json['csrf']})

    def activity(name, date, end=''):
        assert post('events',{'name':name,'date':date,'endDate':end}).status_code==200
        return next(e['id'] for e in client.get('/api/events').json['events'] if e['name']==name)

    vehicle=post('modules/vehicle',{'name':'Furgo'}).json['id']
    assert post('team',{'team':'occident'}).status_code==200
    occident=seed_record(app,'occident','event',dict(name='Privada Occident',date='2027-03-01',endDate='2027-03-03',called=[]))
    reserve={'event':occident,'resource':vehicle,'status':'Reservado'}
    assert post('resource-availability',reserve).status_code==403
    booking=seed_record(app,'occident','system:resource-availability',reserve)

    assert post('team',{'team':'netkom'}).status_code==200
    assert client.get('/api/events').json['events']==[]
    shared=client.get('/api/resource-availability').json['vehicleBookings']
    assert shared==[{'team':'occident','event':None,'date':'2027-03-01','endDate':'2027-03-03','vehicles':[vehicle]}]
    netkom=activity('Privada Netkom','2027-03-03')
    assert post('resource-availability',dict(reserve,event=netkom)).status_code==409
    assert post('modules/travel',{'event':netkom,'vehicles':[vehicle]}).status_code==409

    assert post('team',{'team':'occident'}).status_code==200
    assert post('resource-availability',dict(reserve,status='Libre')).status_code==403
    with app.extensions['db_sessions'].begin() as db:
        db.info['team']='occident'
        db.delete(db.get(Record,booking))
    assert post('team',{'team':'netkom'}).status_code==200
    assert client.get('/api/resource-availability').json['vehicleBookings']==[]
    assert post('modules/travel',{'event':netkom,'vehicles':[vehicle],'hotel':'Hotel de prueba'}).status_code==200
    assert post('team',{'team':'occident'}).status_code==200
    assert client.get('/api/resource-availability').json['vehicleBookings']==[
        {'team':'netkom','event':None,'date':'2027-03-03','endDate':'2027-03-03','vehicles':[vehicle]}]
    assert post('vehicle-availability',reserve).status_code==409
    assert post('vehicle-availability',dict(reserve,event=netkom)).status_code==404
    assert post('team',{'team':'netkom'}).status_code==200
    assert post('vehicle-availability',dict(reserve,event=netkom,status='Libre')).status_code==200
    trip=client.get('/api/modules/travel').json['records'][0]
    assert trip['vehicles']==[] and trip['hotel']=='Hotel de prueba'
    assert post('vehicle-availability',dict(reserve,event=netkom)).status_code==200
    assert client.get('/api/modules/travel').json['records'][0]['vehicles']==[vehicle]
    assert post('vehicle-availability',dict(reserve,event=netkom,status='Libre')).status_code==200
    assert post('team',{'team':'occident'}).status_code==200
    assert post('vehicle-availability',reserve).status_code==200
    assert post('team',{'team':'netkom'}).status_code==200
    assert client.get('/api/resource-availability').json['vehicleBookings']==shared
    assert post('team',{'team':'occident'}).status_code==200
    assert post('vehicle-availability',dict(reserve,status='Libre')).status_code==200
    assert client.get('/api/resource-availability').json['vehicleBookings']==[]

def test_vehicle_reservation_without_activity_blocks_both_teams(env):
    app,_,login,_=env
    with app.extensions['db_sessions'].begin() as db:
        db.add(User(id='shared-direction',email='direccion',name='Dirección',role='director',
                    documents=True,password=generate_password_hash('a-password-for-testing'),
                    profile=app.extensions['cipher'].encrypt(b'{}')))
    client=app.test_client()
    assert client.post('/api/login',json={'email':'direccion','password':'a-password-for-testing'}).status_code==200

    def change(method,path,data=None):
        return client.open('/api/'+path,method=method,json=data,
                           headers={'X-CSRF-Token':client.get('/api/me').json['csrf']})

    vehicle=change('POST','modules/vehicle',{'name':'Furgo'}).json['id']
    draft={'vehicle':vehicle,'date':'2027-05-01','endDate':'2027-05-02','reason':'Taller','usage':'trabajo'}
    assert change('POST','vehicle-reservations',dict(draft,endDate='2027-04-30')).status_code==400
    assert change('POST','vehicle-reservations',dict(draft,usage='')).status_code==400
    created=change('POST','vehicle-reservations',draft)
    assert created.status_code==201
    path='vehicle-reservations/'+created.json['id']
    assert change('PUT',path,dict(draft,reason='Modificada')).status_code==200
    own=client.get('/api/resource-availability').json['vehicleBookings'][0]
    assert own['id']==created.json['id'] and own['reason']=='Modificada' and own['usage']=='trabajo'
    assert change('POST','team',{'team':'occident'}).status_code==200
    shared=client.get('/api/resource-availability').json['vehicleBookings']
    assert shared==[{'team':'netkom','event':None,'date':'2027-05-01','endDate':'2027-05-02',
                    'vehicles':[vehicle],'direct':True,'usage':'trabajo'}]
    assert change('DELETE',path).status_code==404
    assert change('PUT',path,draft).status_code==403
    assert change('POST','team',{'team':'netkom'}).status_code==200
    assert change('POST','vehicle-reservations',dict(draft,date='2027-05-02')).status_code==409
    assert change('POST','events',{'name':'Carrera','date':'2027-05-02'}).status_code==200
    event=client.get('/api/events').json['events'][0]['id']
    trip={'event':event,'vehicles':[vehicle]}
    assert change('POST','modules/travel',trip).status_code==409
    technician,h=login('technician')
    assert technician.post('/api/vehicle-reservations',json=draft,headers=h).status_code==403
    assert change('DELETE',path).status_code==200
    assert change('POST','modules/travel',trip).status_code==200
    assert change('POST','vehicle-reservations',draft).status_code==409
    assert change('POST','vehicle-reservations',dict(draft,date='2027-05-03',endDate='')).status_code==201

def test_school_and_surne_start_separate_and_share_fleet(env):
    app,_,login,_=env
    with app.extensions['db_sessions'].begin() as db:
        db.add(User(id='shared-direction',email='direccion',name='Dirección',role='director',
                    documents=True,password=generate_password_hash('a-password-for-testing'),
                    profile=app.extensions['cipher'].encrypt(b'{}')))
    client=app.test_client()
    assert client.post('/api/login',json={'email':'direccion','password':'a-password-for-testing'}).status_code==200
    assert set(client.get('/api/me').json['teams'])=={'netkom','occident','escuela','surne'}

    def post(path,data):
        return client.post('/api/'+path,json=data,headers={'X-CSRF-Token':client.get('/api/me').json['csrf']})

    vehicle=post('modules/vehicle',{'name':'Furgo'}).json['id']
    draft={'vehicle':vehicle,'date':'2027-07-01','usage':'trabajo'}
    staff=post('modules/staff',{'name':'Técnico común'}).json['id']
    assert post('vehicle-reservations',draft).status_code==201
    with app.extensions['db_sessions'].begin() as db:
        profile=app.extensions['cipher'].encrypt(b'{"category":"Infantil"}')
        db.add(User(id='escuela-rider',team='escuela',name='Deportista Escuela',role='runner',profile=profile))
    seed_record(app,'escuela','event',dict(name='Actividad de Escuela',date=draft['date'],called=[]))
    for team in ['escuela','surne','occident','netkom']:
        assert post('team',{'team':team}).status_code==200
        assert client.get('/api/me').json['team']==team
        assert client.get('/api/modules/staff').json['records'][0]['id']==staff
        assert client.get('/api/modules/vehicle').json['records'][0]['id']==vehicle
        events=client.get('/api/events').json['events']
        if team=='escuela':
            assert events[0]['name']=='Actividad de Escuela'
            assert client.get('/api/roster').json['riders'][0]['category']=='Infantil'
        else:
            assert events==[]
            assert client.get('/api/profile/escuela-rider').status_code==404
        assert client.get('/api/resource-availability').json['vehicleBookings'][0]['team']=='netkom'
        assert post('vehicle-reservations',draft).status_code==(409 if team=='netkom' else 403)
    director,h=login('director')
    assert director.post('/api/team',json={'team':'surne'},headers=h).status_code==403
